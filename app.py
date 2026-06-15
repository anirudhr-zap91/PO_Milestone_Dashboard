import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(page_title="PO Dashboard", layout="wide")
st.title("PO Dashboard")

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

# Numeric conversions
df_po["Outflow Amount"] = clean_amount(df_po["Outflow Amount"])
df_po["Value"] = clean_amount(df_po["Value"])

# Convert raw ₹ to Cr to match plan sheet units
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
# CURRENT MONTH ONLY (auto-updates based on today's date)
# ==================================================
today = pd.Timestamp.today()
current_month = pd.Timestamp(year=today.year, month=today.month, day=1)
current_month_label = current_month.strftime("%B %Y")

st.header(f"PO Requirement: {current_month_label}")

# ==================================================
# PLAN: FILTER TO CURRENT MONTH
# ==================================================
plan_window = df_plan[df_plan["Month_Date"] == current_month].copy()

# ==================================================
# ACTUAL PO: FILTER TO CURRENT MONTH
# ==================================================
po_window = df_po[df_po["Outflow_Month_Date"] == current_month].copy()

# ==================================================
# TOTAL PLANNED REQUIREMENT
# ==================================================
total_planned = plan_window["Amount"].sum()
total_actual = po_window["Outflow Amount"].sum()

col1, col2 = st.columns(2)
with col1:
    st.metric(f"Planned Requirement ({current_month_label})", f"₹ {total_planned:.2f} Cr")
with col2:
    st.metric(f"Actual PO Outflow ({current_month_label})", f"₹ {total_actual:.2f} Cr")

# ==================================================
# PLANNED REQUIREMENT TABLE (Category shown once, grouped)
# ==================================================
st.subheader("Planned PO Requirement (Category / Sub-Category)")

plan_table = (
    plan_window
    .groupby(["Category", "Sub-Category"], as_index=False)["Amount"]
    .sum()
    .sort_values(["Category", "Sub-Category"])
)

# Blank out repeated Category values so it's shown only once per group
display_plan_table = plan_table.copy()
display_plan_table["Category"] = display_plan_table["Category"].where(
    display_plan_table["Category"] != display_plan_table["Category"].shift(), ""
)

st.dataframe(display_plan_table, use_container_width=True, hide_index=True)

# ==================================================
# ACTUAL PO OUTFLOW (by Sub Head, Week)
# ==================================================
st.subheader("Actual PO Outflow (matched to Sub-Category, by Week)")

actual_breakdown = (
    po_window
    .groupby(["Sub Head", "Outflow Month", "Outflow Week"], as_index=False)["Outflow Amount"]
    .sum()
    .sort_values(["Sub Head", "Outflow Week"])
)
actual_breakdown["Outflow Week"] = actual_breakdown["Outflow Week"].replace("", "N/A")

st.dataframe(actual_breakdown, use_container_width=True, hide_index=True)

# ==================================================
# PLANNED vs ACTUAL (by Sub-Category / Sub Head)
# ==================================================
st.subheader("Planned vs Actual (by Sub-Category / Sub Head)")

planned_by_sub = (
    plan_window
    .groupby("Sub-Category", as_index=False)["Amount"]
    .sum()
    .rename(columns={"Sub-Category": "Sub Head", "Amount": "Planned (Cr)"})
)

actual_by_sub = (
    po_window
    .groupby("Sub Head", as_index=False)["Outflow Amount"]
    .sum()
    .rename(columns={"Outflow Amount": "Actual (Cr)"})
)

comparison = pd.merge(planned_by_sub, actual_by_sub, on="Sub Head", how="outer")
comparison = comparison.sort_values("Sub Head")

st.dataframe(comparison, use_container_width=True, hide_index=True)

# ==================================================
# WEEKLY BREAKDOWN
# ==================================================
st.subheader("Weekly Outflow Breakdown")

weekly = (
    po_window
    .groupby(["Outflow Week", "Sub Head"], as_index=False)["Outflow Amount"]
    .sum()
    .sort_values(["Outflow Week", "Sub Head"])
)
weekly["Outflow Week"] = weekly["Outflow Week"].replace("", "N/A")

# Blank out repeated week values so each week is shown only once
display_weekly = weekly.copy()
display_weekly["Outflow Week"] = display_weekly["Outflow Week"].where(
    display_weekly["Outflow Week"] != display_weekly["Outflow Week"].shift(), ""
)

st.dataframe(display_weekly, use_container_width=True, hide_index=True)

totals = weekly.groupby("Outflow Week", as_index=False)["Outflow Amount"].sum()
totals["Sub Head"] = "Total"

weekly_with_totals = pd.concat([weekly, totals]).sort_values(["Outflow Week", "Sub Head"])
