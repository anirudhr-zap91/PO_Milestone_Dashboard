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
# HELPER: CLEAN NUMERIC COLUMNS
# ==================================================
def clean_amount(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.strip(),
        errors="coerce"
    )

# ==================================================
# HELPER: PARSE "MONTH YEAR" STRINGS (handles "Jun 2026" and "June 2026")
# ==================================================
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

# Forward-fill merged-cell columns (PO-level info repeated across payment rows)
ffill_cols = [
    "Sr no.", "Package Description", "SPOC", "Vendor", "PO", "PO Date",
    "PO Value (excld GST)", "PO Value (incld GST)", "Payment Terms",
    "Currency", "Head", "Sub Head", "Value"
]
for col in ffill_cols:
    if col in df_po.columns:
        df_po[col] = df_po[col].replace("", pd.NA).ffill()

# Remove fully blank rows
df_po = df_po.replace("", pd.NA)
df_po = df_po.dropna(how="all")

# Numeric conversion
df_po["Outflow Amount"] = clean_amount(df_po["Outflow Amount"])
df_po["Value"] = clean_amount(df_po["Value"])

# Convert raw ₹ to Cr (1 Cr = 1,00,00,000) to match "PO to be issued" sheet units
df_po["Outflow Amount"] = df_po["Outflow Amount"] / 1e7
df_po["Value"] = df_po["Value"] / 1e7

# Parse Outflow Month -> datetime
df_po["Outflow_Month_Date"] = parse_month(df_po["Outflow Month"])

# Drop rows with no usable outflow amount or month
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
plan_data = plan_records[2:68]   # rows 3 to 68 (covers all categories incl. PMC & Stat)

df_plan = pd.DataFrame(plan_data, columns=plan_headers)

required_plan_cols = [
    "Category", "Sub-Category", "Estimates/back quotes value",
    "% Breakup", "Amount", "Month Outflow", "Total %", "Total Value"
]
available_plan_cols = [c for c in required_plan_cols if c in df_plan.columns]
df_plan = df_plan[available_plan_cols]

# Forward-fill merged Category / Sub-Category cells
df_plan["Category"] = df_plan["Category"].replace("", pd.NA).ffill()
df_plan["Sub-Category"] = df_plan["Sub-Category"].replace("", pd.NA).ffill()

# Drop summary/total rows
df_plan = df_plan[~df_plan["Category"].isin(["Subtotal", ""])]
df_plan = df_plan[df_plan["Sub-Category"] != "Total"]

# Numeric conversions
df_plan["Amount"] = clean_amount(df_plan["Amount"])

# Parse Month Outflow -> datetime
df_plan["Month_Date"] = parse_month(df_plan["Month Outflow"])

# Keep only rows with a real amount and a valid month
df_plan = df_plan[
    (df_plan["Amount"] > 0)
    & (df_plan["Month_Date"].notna())
]

# ==================================================
# CURRENT + NEXT MONTH (auto-updates based on today's date)
# ==================================================
today = pd.Timestamp.today()
current_month = pd.Timestamp(year=today.year, month=today.month, day=1)
next_month = current_month + pd.DateOffset(months=1)

target_months = [current_month, next_month]
target_month_labels = [m.strftime("%B %Y") for m in target_months]

st.header(f"PO Requirement: {target_month_labels[0]} & {target_month_labels[1]}")

# ==================================================
# PLAN: FILTER TO CURRENT + NEXT MONTH
# ==================================================
plan_window = df_plan[df_plan["Month_Date"].isin(target_months)].copy()

# ==================================================
# ACTUAL PO: FILTER TO CURRENT + NEXT MONTH
# ==================================================
po_window = df_po[df_po["Outflow_Month_Date"].isin(target_months)].copy()

# ==================================================
# TOTAL PLANNED REQUIREMENT
# ==================================================
total_planned = plan_window["Amount"].sum()
total_actual = po_window["Outflow Amount"].sum()

col1, col2 = st.columns(2)
with col1:
    st.metric(f"Planned Requirement ({target_month_labels[0]} + {target_month_labels[1]})", f"₹ {total_planned:.2f} Cr")
with col2:
    st.metric(f"Actual PO Outflow ({target_month_labels[0]} + {target_month_labels[1]})", f"₹ {total_actual:,.0f}")

# ==================================================
# PLANNED REQUIREMENT TABLE (by Category / Sub-Category / Month)
# ==================================================
st.subheader("Planned PO Requirement (Category / Sub-Category)")

plan_table = (
    plan_window
    .groupby(["Category", "Sub-Category", "Month Outflow"], as_index=False)["Amount"]
    .sum()
    .sort_values(["Month Outflow", "Category", "Sub-Category"])
)

st.dataframe(plan_table, use_container_width=True, hide_index=True)

# ==================================================
# MATCH PLAN SUB-CATEGORY <-> PO LIST SUB HEAD
# Aggregate actual PO outflow by Sub Head + Month + Week
# ==================================================
st.subheader("Actual PO Outflow (matched to Sub-Category, by Week)")

actual_breakdown = (
    po_window
    .groupby(["Sub Head", "Outflow Month", "Outflow Week"], as_index=False)["Outflow Amount"]
    .sum()
)

actual_breakdown["Outflow Week"] = actual_breakdown["Outflow Week"].replace("", "N/A")

st.dataframe(actual_breakdown, use_container_width=True, hide_index=True)

# ==================================================
# COMBINED VIEW: PLANNED vs ACTUAL PER SUB-CATEGORY/SUB HEAD
# ==================================================
st.subheader("Planned vs Actual (by Sub-Category / Sub Head)")

planned_by_sub = (
    plan_window
    .groupby(["Sub-Category", "Month Outflow"], as_index=False)["Amount"]
    .sum()
    .rename(columns={"Sub-Category": "Sub Head", "Month Outflow": "Month", "Amount": "Planned (Cr)"})
)

actual_by_sub = (
    po_window
    .groupby(["Sub Head", "Outflow Month"], as_index=False)["Outflow Amount"]
    .sum()
    .rename(columns={"Outflow Month": "Month", "Outflow Amount": "Actual (₹)"})
)

comparison = pd.merge(
    planned_by_sub,
    actual_by_sub,
    on=["Sub Head", "Month"],
    how="outer"
)

comparison = comparison.sort_values(["Month", "Sub Head"])

st.dataframe(comparison, use_container_width=True, hide_index=True)

# ==================================================
# WEEKLY BREAKDOWN CHART
# ==================================================
st.subheader("Weekly Outflow Breakdown")

weekly = (
    po_window
    .groupby(["Outflow Month", "Outflow Week", "Sub Head"], as_index=False)["Outflow Amount"]
    .sum()
)
weekly["Outflow Week"] = weekly["Outflow Week"].replace("", "N/A")

st.dataframe(weekly, use_container_width=True, hide_index=True)
