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

# Header row = Row 2
po_headers = po_records[1]

# Data starts from Row 3
po_data = po_records[2:]

df_po = pd.DataFrame(
    po_data,
    columns=po_headers
)

# Fill merged-cell blanks
df_po = df_po.ffill()

st.success("Connected Successfully!")

st.header("Cleaned PO Data")

st.write("Rows Loaded:", len(df_po))

st.dataframe(df_po.head(20))
# -----------------------------
# Load Sheet 2
# -----------------------------
ws_plan = spreadsheet.worksheet(
    "PO to be issued"
)

plan_records = ws_plan.get_all_values()

# Header row = Row 2
plan_headers = plan_records[1]

# Data starts from Row 3
plan_data = plan_records[2:]

df_plan = pd.DataFrame(
    plan_data,
    columns=plan_headers
)

st.header("Cleaned Planned PO Data")

st.write("Rows Loaded:", len(df_plan))

st.dataframe(df_plan.head(20))

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
