import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="PO Dashboard",
    layout="wide"
)

st.title("PO Dashboard")

# --------------------------------------------------
# GOOGLE AUTH
# --------------------------------------------------
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

# --------------------------------------------------
# GOOGLE SHEET
# --------------------------------------------------
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

st.header("PO List & Payment Schedule")

st.write("Raw Rows Loaded:", len(po_records))

# Header row = Row 2
po_headers = po_records[1]

# Only load till row 367
po_data = po_records[2:367]

# Clean headers
clean_headers = []

for i, col in enumerate(po_headers):

    col = str(col).strip()

    if col == "":
        col = f"Unnamed_{i}"

    clean_headers.append(col)

df_po = pd.DataFrame(
    po_data,
    columns=clean_headers
)

# Fill merged-cell blanks
df_po = df_po.ffill()

# --------------------------------------------------
# DIAGNOSTICS
# --------------------------------------------------

st.subheader("PO Sheet Shape")

st.write(df_po.shape)

st.subheader("PO Sheet Columns")

for idx, col in enumerate(df_po.columns):
    st.write(idx, ":", col)

st.subheader("First Record")

try:
    st.json(df_po.iloc[0].to_dict())
except:
    st.write(df_po.iloc[0].to_dict())

st.subheader("Last Record")

try:
    st.json(df_po.iloc[-1].to_dict())
except:
    st.write(df_po.iloc[-1].to_dict())

# ==================================================
# SHEET 2 : PO TO BE ISSUED
# ==================================================

ws_plan = spreadsheet.worksheet(
    "PO to be issued"
)

plan_records = ws_plan.get_all_values()

st.header("PO To Be Issued")

st.write("Raw Rows Loaded:", len(plan_records))

# Header row = Row 2
plan_headers = plan_records[1]

# Data starts Row 3
plan_data = plan_records[2:]

# Clean headers
clean_plan_headers = []

for i, col in enumerate(plan_headers):

    col = str(col).strip()

    if col == "":
        col = f"Unnamed_{i}"

    clean_plan_headers.append(col)

df_plan = pd.DataFrame(
    plan_data,
    columns=clean_plan_headers
)

st.subheader("Plan Sheet Shape")

st.write(df_plan.shape)

st.subheader("Plan Sheet Columns")

for idx, col in enumerate(df_plan.columns):
    st.write(idx, ":", col)

st.subheader("First Record")

try:
    st.json(df_plan.iloc[0].to_dict())
except:
    st.write(df_plan.iloc[0].to_dict())

st.subheader("Last Record")

try:
    st.json(df_plan.iloc[-1].to_dict())
except:
    st.write(df_plan.iloc[-1].to_dict())
