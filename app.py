import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# ==================================================
# PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="PO Dashboard",
    layout="wide"
)

st.title("PO Dashboard")

# ==================================================
# GOOGLE AUTH
# ==================================================

creds_dict = json.loads(
    st.secrets["google_credentials"]
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=SCOPES,
)

client = gspread.authorize(creds)

# ==================================================
# OPEN SHEET
# ==================================================

SHEET_ID = "1Wyw9IonVmLpiL2yoiVe2bSa9IgLhSCcO_h4Y_2gSgHU"

spreadsheet = client.open_by_key(SHEET_ID)

st.success("Connected Successfully!")

# ==================================================
# SHEET 1 : PO LIST & PAYMENT SCHEDULE
# ==================================================

ws_po = spreadsheet.worksheet(
    "PO List & Payment schedule"
)

po_records = ws_po.get_all_values()

# Header row
po_headers = [
    str(col).strip()
    for col in po_records[1]
]

# Row 3 to Row 367
po_data = po_records[2:367]

df_po = pd.DataFrame(
    po_data,
    columns=po_headers
)

# Fill merged-cell blanks
df_po = df_po.ffill()

required_po_cols = [
    "Sr no.",
    "Package Description",
    "SPOC",
    "Vendor",
    "PO",
    "PO Date",
    "PO Value (excld GST)",
    "PO Value (incld GST)",
    "Payment Terms",
    "Outflow Amount",
    "Outflow Month",
    "Outflow Week",
    "Payment Type",
    "Payment Status",
    "Total %",
    "Total Value",
    "Currency",
    "Head",
    "Sub Head",
    "Value"
]

available_po_cols = [
    col
    for col in required_po_cols
    if col in df_po.columns
]

df_po = df_po[available_po_cols]

# Remove fully blank rows
df_po = df_po.replace("", pd.NA)

df_po = df_po.dropna(
    how="all"
)

# ==================================================
# NUMERIC CONVERSION
# ==================================================

def clean_amount(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.strip(),
        errors="coerce"
    )

df_po["Outflow Amount"] = clean_amount(
    df_po["Outflow Amount"]
)

df_po["PO Value (incld GST)"] = clean_amount(
    df_po["PO Value (incld GST)"]
)

df_po["Total Value"] = clean_amount(
    df_po["Total Value"]
)

df_po["Value"] = clean_amount(
    df_po["Value"]
)

# ==================================================
# SHEET 2 : PO TO BE ISSUED
# ==================================================

ws_plan = spreadsheet.worksheet(
    "PO to be issued"
)

plan_records = ws_plan.get_all_values()

plan_headers = [
    str(col).strip()
    for col in plan_records[1]
]

# Row 3 to Row 67
plan_data = plan_records[2:67]

df_plan = pd.DataFrame(
    plan_data,
    columns=plan_headers
)

required_plan_cols = [
    "Category",
    "Sub-Category",
    "Estimates/back quotes value",
    "% Breakup",
    "Amount",
    "Month Outflow",
    "Total %",
    "Total Value"
]

available_plan_cols = [
    col
    for col in required_plan_cols
    if col in df_plan.columns
]

df_plan = df_plan[
    available_plan_cols
]

df_plan = df_plan.replace(
    "",
    pd.NA
)

df_plan = df_plan.dropna(
    how="all"
)
df_plan["Amount"] = clean_amount(
    df_plan["Amount"]
)

df_plan["Total Value"] = clean_amount(
    df_plan["Total Value"]
)

df_plan["Estimates/back quotes value"] = clean_amount(
    df_plan["Estimates/back quotes value"]
)

# ==================================================
# KPI CALCULATIONS
# ==================================================

total_po_value = df_po["Value"].max()

completed_payment = (
    df_po[
        df_po["Payment Status"] == "Completed"
    ]["Outflow Amount"].sum()
)

pending_payment = (
    df_po[
        df_po["Payment Status"] != "Completed"
    ]["Outflow Amount"].sum()
)

planned_value = (
    df_plan["Amount"].sum()
)
# ==================================================
# KPI DISPLAY
# ==================================================

st.header("Dashboard Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total PO Value",
        f"₹ {total_po_value:,.0f}"
    )

with col2:
    st.metric(
        "Completed Payments",
        f"₹ {completed_payment:,.0f}"
    )

with col3:
    st.metric(
        "Pending Payments",
        f"₹ {pending_payment:,.0f}"
    )

with col4:
    st.metric(
        "Planned Value",
        f"₹ {planned_value:,.0f}"
    )
# ==================================================
# DEBUG INFO
# ==================================================

st.header("Debug Information")

col1, col2 = st.columns(2)

with col1:

    st.subheader(
        "PO Sheet"
    )

    st.write(
        "Shape:",
        df_po.shape
    )

    st.write(
        "Columns Found:"
    )

    st.write(
        list(df_po.columns)
    )

with col2:

    st.subheader(
        "Plan Sheet"
    )

    st.write(
        "Shape:",
        df_plan.shape
    )

    st.write(
        "Columns Found:"
    )

    st.write(
        list(df_plan.columns)
    )

# ==================================================
# DISPLAY DATA
# ==================================================

tab1, tab2 = st.tabs(
    [
        "PO Data",
        "Planned Data"
    ]
)

with tab1:

    st.subheader(
        "PO List & Payment Schedule"
    )

    st.write(
        f"Rows : {len(df_po)}"
    )

    st.dataframe(
        df_po.head(50),
        use_container_width=True
    )

with tab2:

    st.subheader(
        "PO To Be Issued"
    )

    st.write(
        f"Rows : {len(df_plan)}"
    )

    st.dataframe(
        df_plan.head(50),
        use_container_width=True
    )
