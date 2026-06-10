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
# SHEET 1
# PO LIST & PAYMENT SCHEDULE
# ==================================================

ws_po = spreadsheet.worksheet(
    "PO List & Payment schedule"
)

po_records = ws_po.get_all_values()

# Header Row = Row 2
po_headers = po_records[1]

# Data Row = Row 3 onwards
# Only till row 367
po_data = po_records[2:367]

df_po = pd.DataFrame(
    po_data,
    columns=po_headers
)

# Fill merged-cell blanks
df_po = df_po.ffill()

# Keep only required columns
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

df_po = df_po[required_po_cols]

# Remove completely blank rows
df_po = df_po.dropna(how="all")

# Remove useless trailing rows
df_po = df_po[
    ~(
        (df_po["PO"] == "") &
        (df_po["Outflow Amount"] == "")
    )
]

# ==================================================
# SHEET 2
# PO TO BE ISSUED
# ==================================================

ws_plan = spreadsheet.worksheet(
    "PO to be issued"
)

plan_records = ws_plan.get_all_values()

# Header Row = Row 2
plan_headers = plan_records[1]

# Data Row = Row 3 onwards
# Only till row 67
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

df_plan = df_plan[required_plan_cols]

df_plan = df_plan.dropna(how="all")

# ==================================================
# DISPLAY
# ==================================================

tab1, tab2 = st.tabs(
    [
        "PO List & Payment Schedule",
        "PO To Be Issued"
    ]
)

with tab1:

    st.subheader("Cleaned PO Data")

    st.write(
        f"Rows: {len(df_po)} | Columns: {len(df_po.columns)}"
    )

    st.dataframe(
        df_po,
        use_container_width=True
    )

with tab2:

    st.subheader("Cleaned Planned Data")

    st.write(
        f"Rows: {len(df_plan)} | Columns: {len(df_plan.columns)}"
    )

    st.dataframe(
        df_plan,
        use_container_width=True
    )

# ==================================================
# DEBUG
# ==================================================

st.divider()

st.subheader("Dataset Summary")

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "PO Rows",
        len(df_po)
    )

with col2:
    st.metric(
        "Plan Rows",
        len(df_plan)
    )
