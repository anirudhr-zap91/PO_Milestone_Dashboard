import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(page_title="PO Dashboard", layout="wide")

# ==================================================
# GLOBAL CSS
# ==================================================
st.markdown("""
    <style>
        .main { padding: 20px 30px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
        th { background-color: #1a3c5e !important; color: white !important;
             padding: 10px !important; text-align: left !important; }
        td { padding: 8px 10px !important; border-bottom: 1px solid #e8ecef; }
        tr:hover td { background-color: #f5f9fd; }
    </style>
""", unsafe_allow_html=True)

# ==================================================
# HEADER BANNER
# ==================================================
st.markdown("""
    <div style="background: linear-gradient(90deg, #1a3c5e, #2980b9);
                padding: 20px 30px; border-radius: 10px; margin-bottom: 20px">
        <h1 style="color: white; margin: 0; font-size: 2rem">📋 PO Dashboard</h1>
        <p style="color: #cce4f7; margin: 5px 0 0 0; font-size: 0.95rem">
            Purchase Order Tracking & Cash Flow Overview
        </p>
    </div>
""", unsafe_allow_html=True)

# ==================================================
# SECTION HEADER HELPER
# ==================================================
def section_header(title, icon=""):
    st.markdown(f"""
        <div style="margin: 30px 0 10px 0; padding-bottom: 8px;
                    border-bottom: 2px solid #2980b9">
            <h3 style="margin:0; color:#1a3c5e">{icon} {title}</h3>
        </div>
    """, unsafe_allow_html=True)

# ==================================================
# GOOGLE AUTH
# ==================================================
creds_dict = json.loads(st.secrets["google_credentials"])

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

SHEET_ID = "1Wyw9IonVmLpiL2yoiVe2bSa9IgLhSCcO_h4Y_2gSgHU"
spreadsheet = client.open_by_key(SHEET_ID)

# ==================================================
# HELPERS
# ==================================================
def clean_amount(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.strip(),
        errors="coerce"
    )

def parse_month(series):
    parsed = pd.to_datetime(series, format="%b %Y", errors="coerce")
    mask = parsed.isna()
    parsed.loc[mask] = pd.to_datetime(series[mask], format="%B %Y", errors="coerce")
    return parsed

# ==================================================
# SHEET 1 : PO LIST & PAYMENT SCHEDULE
# ==================================================
ws_po = spreadsheet.worksheet("PO List & Payment schedule")
po_records = ws_po.get_all_values()

po_headers = [str(c).strip() for c in po_records[1]]
po_data = po_records[2:]

df_po = pd.DataFrame(po_data, columns=po_headers)

required_po_cols = [
    "Sr no.", "Package Description", "SPOC", "Vendor", "PO", "PO Date",
    "PO Value (excld GST)", "PO Value (incld GST)", "Payment Terms",
    "Outflow Amount", "Outflow Month", "Outflow Week", "Payment Type",
    "Payment Status", "Total %", "Total Value", "Currency",
    "Head", "Sub Head", "Value"
]
available_po_cols = [c for c in required_po_cols if c in df_po.columns]
df_po = df_po[available_po_cols]

ffill_cols = [
    "Sr no.", "Package Description", "SPOC", "Vendor", "PO", "PO Date",
    "PO Value (excld GST)", "PO Value (incld GST)", "Payment Terms",
    "Currency", "Head", "Sub Head", "Value"
]
for col in ffill_cols:
    if col in df_po.columns:
        df_po[col] = df_po[col].replace("", pd.NA).ffill()

df_po = df_po.replace("", pd.NA)
df_po = df_po.dropna(how="all")

df_po["Outflow Amount"] = clean_amount(df_po["Outflow Amount"])
df_po["Value"] = clean_amount(df_po["Value"])

df_po["Outflow Amount"] = df_po["Outflow Amount"] / 1e7
df_po["Value"] = df_po["Value"] / 1e7

df_po["Outflow_Month_Date"] = parse_month(df_po["Outflow Month"])

df_po = df_po[
    df_po["Outflow Amount"].notna()
    & df_po["Outflow_Month_Date"].notna()
]

# ==================================================
# SHEET 2 : PO TO BE ISSUED
# ==================================================
ws_plan = spreadsheet.worksheet("PO to be issued")
plan_records = ws_plan.get_all_values()

plan_headers = [str(c).strip() for c in plan_records[1]]
plan_data = plan_records[2:68]

df_plan = pd.DataFrame(plan_data, columns=plan_headers)

required_plan_cols = [
    "Category", "Sub-Category", "Estimates/back quotes value",
    "% Breakup", "Amount", "Month Outflow", "Total %", "Total Value"
]
available_plan_cols = [c for c in required_plan_cols if c in df_plan.columns]
df_plan = df_plan[available_plan_cols]

df_plan["Category"] = df_plan["Category"].replace("", pd.NA).ffill()
df_plan["Sub-Category"] = df_plan["Sub-Category"].replace("", pd.NA).ffill()

df_plan = df_plan[~df_plan["Category"].isin(["Subtotal", ""])]
df_plan = df_plan[df_plan["Sub-Category"] != "Total"]

df_plan["Amount"] = clean_amount(df_plan["Amount"])
df_plan["Month_Date"] = parse_month(df_plan["Month Outflow"])

df_plan = df_plan[
    (df_plan["Amount"] > 0)
    & (df_plan["Month_Date"].notna())
]

# ==================================================
# CURRENT MONTH
# ==================================================
today = pd.Timestamp.today()
current_month = pd.Timestamp(year=today.year, month=today.month, day=1)
current_month_label = current_month.strftime("%B %Y")

st.markdown(f"""
    <h2 style="color:#1a3c5e; margin: 10px 0 20px 0">
        📅 PO Requirement: {current_month_label}
    </h2>
""", unsafe_allow_html=True)

# ==================================================
# FILTER TO CURRENT MONTH
# ==================================================
plan_window = df_plan[df_plan["Month_Date"] == current_month].copy()
po_window = df_po[df_po["Outflow_Month_Date"] == current_month].copy()

# ==================================================
# KPI CARDS
# ==================================================
total_planned = plan_window["Amount"].sum()
total_actual = po_window["Outflow Amount"].sum()
total_expected = total_planned + total_actual

st.markdown(f"""
    <div style="display: flex; gap: 20px; margin: 20px 0">
        <div style="flex:1; background:#eaf4fb; border-left: 5px solid #2980b9;
                    padding: 20px; border-radius: 8px">
            <p style="margin:0; color:#555; font-size:0.85rem">Actual PO Outflow</p>
            <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_actual:.2f} Cr</h2>
            <p style="margin:0; color:#888; font-size:0.8rem">{current_month_label}</p>
        </div>
        <div style="flex:1; background:#fef9e7; border-left: 5px solid #f39c12;
                    padding: 20px; border-radius: 8px">
            <p style="margin:0; color:#555; font-size:0.85rem">Planned New PO Requirement</p>
            <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_planned:.2f} Cr</h2>
            <p style="margin:0; color:#888; font-size:0.8rem">{current_month_label}</p>
        </div>
        <div style="flex:1; background:#eafaf1; border-left: 5px solid #27ae60;
                    padding: 20px; border-radius: 8px">
            <p style="margin:0; color:#555; font-size:0.85rem">Total Expected Outflow</p>
            <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_expected:.2f} Cr</h2>
            <p style="margin:0; color:#888; font-size:0.8rem">{current_month_label}</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# ==================================================
# PLANNED PO REQUIREMENT TABLE
# ==================================================
section_header("Planned PO Requirement", "📌")

plan_table = (
    plan_window
    .groupby(["Category", "Sub-Category"], as_index=False)["Amount"]
    .sum()
    .sort_values(["Category", "Sub-Category"])
)

display_plan_table = plan_table.copy()
display_plan_table["Category"] = display_plan_table["Category"].where(
    display_plan_table["Category"] != display_plan_table["Category"].shift(), ""
)

def style_plan_table(row):
    if row["Category"] != "":
        return ["font-weight: bold; background-color: #eaf4fb; color: #1a3c5e"] * len(row)
    return [""] * len(row)

styled_plan = (
    display_plan_table.style
    .apply(style_plan_table, axis=1)
    .hide(axis="index")
    .format({"Amount": "{:.2f}"})
)

st.markdown(styled_plan.to_html(), unsafe_allow_html=True)

# ==================================================
# ACTUAL PO OUTFLOW
# ==================================================
section_header("Actual PO Outflow by Sub-Head & Week", "💰")

actual_breakdown = (
    po_window
    .groupby(["Sub Head", "Outflow Week"], as_index=False)["Outflow Amount"]
    .sum()
    .sort_values(["Sub Head", "Outflow Week"])
)
actual_breakdown["Outflow Week"] = actual_breakdown["Outflow Week"].replace("", "N/A")

st.dataframe(actual_breakdown, use_container_width=True, hide_index=True)

# ==================================================
# WEEKLY BREAKDOWN
# ==================================================
section_header("Weekly Outflow Breakdown", "📅")

po_window["Settlement"] = po_window["Payment Status"].apply(
    lambda x: "Settled" if str(x).strip() in ["Completed", "LC issued"] else "Pending"
)

weekly = (
    po_window
    .groupby(["Outflow Week", "Sub Head", "Settlement"], as_index=False)["Outflow Amount"]
    .sum()
)
weekly["Outflow Week"] = weekly["Outflow Week"].replace("", "N/A")

weekly_totals = weekly.groupby(["Outflow Week", "Settlement"], as_index=False)["Outflow Amount"].sum()
weekly_totals["Sub Head"] = "TOTAL"

weekly["__order"] = 0
weekly_totals["__order"] = 1

weekly_combined = pd.concat([weekly, weekly_totals], ignore_index=True)
weekly_combined = weekly_combined.sort_values(["Outflow Week", "__order", "Sub Head"])
weekly_combined = weekly_combined.drop(columns="__order")

weekly_pivot = weekly_combined.pivot_table(
    index=["Outflow Week", "Sub Head"],
    columns="Settlement",
    values="Outflow Amount",
    aggfunc="sum"
).reset_index()

weekly_pivot.columns.name = None
weekly_pivot = weekly_pivot.rename_axis(None, axis=1)

for col in ["Settled", "Pending"]:
    if col not in weekly_pivot.columns:
        weekly_pivot[col] = 0.0

weekly_pivot["Settled"] = weekly_pivot["Settled"].fillna(0)
weekly_pivot["Pending"] = weekly_pivot["Pending"].fillna(0)
weekly_pivot["Total"] = weekly_pivot["Settled"] + weekly_pivot["Pending"]

display_weekly = weekly_pivot.copy()
display_weekly["Outflow Week"] = display_weekly["Outflow Week"].where(
    display_weekly["Outflow Week"] != display_weekly["Outflow Week"].shift(), ""
)

def style_weekly(row):
    is_total = row["Sub Head"] == "TOTAL"
    base = "font-weight: bold; " if is_total else ""
    return [
        base,
        base,
        base + "color: #27ae60",
        base + "color: #c0392b",
        base
    ]

styled_weekly = (
    display_weekly.style
    .apply(style_weekly, axis=1)
    .hide(axis="index")
    .format({"Settled": "{:.2f}", "Pending": "{:.2f}", "Total": "{:.2f}"})
)

st.markdown(styled_weekly.to_html(), unsafe_allow_html=True)
