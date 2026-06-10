import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="PO Dashboard", layout="wide")

st.title("PO Dashboard")

# -----------------------------
# Google Authentication
# -----------------------------
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

# -----------------------------
# Open Spreadsheet
# -----------------------------
SHEET_ID = "1Wyw9IonVmLpiL2yoiVe2bSa9IgLhSCcO_h4Y_2gSgHU"

spreadsheet = client.open_by_key(SHEET_ID)

# -----------------------------
# Load Sheet 1
# -----------------------------
ws_po = spreadsheet.worksheet(
    "PO List & Payment schedule"
)

po_records = ws_po.get_all_values()

st.success("Connected Successfully!")

st.header("Sheet 1 : PO List & Payment schedule")

st.write("Rows Loaded:", len(po_records))

# Display first 20 raw rows
st.subheader("Raw Data Preview")
st.dataframe(pd.DataFrame(po_records[:20]))

# Display detected headers
if len(po_records) > 1:

    po_headers = po_records[1]

    st.subheader("Detected Headers")

    header_df = pd.DataFrame({
        "Column Number": list(range(len(po_headers))),
        "Header Name": po_headers
    })

    st.dataframe(header_df)

# -----------------------------
# Load Sheet 2
# -----------------------------
ws_plan = spreadsheet.worksheet(
    "PO to be issued"
)

plan_records = ws_plan.get_all_values()

st.header("Sheet 2 : PO to be issued")

st.write("Rows Loaded:", len(plan_records))

# Display first 20 rows
st.subheader("Raw Data Preview")

st.dataframe(
    pd.DataFrame(plan_records[:20])
)

# Display header row candidates
if len(plan_records) > 0:

    st.subheader("First 10 Rows")

    for i in range(min(10, len(plan_records))):
        st.write(f"Row {i+1}")
        st.write(plan_records[i])

# -----------------------------
# Debug Information
# -----------------------------
st.header("Debug Information")

st.write(
    "PO Sheet Columns:",
    len(po_records[1]) if len(po_records) > 1 else 0
)

st.write(
    "PO To Be Issued Rows:",
    len(plan_records)
)
