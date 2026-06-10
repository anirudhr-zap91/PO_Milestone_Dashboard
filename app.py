import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

st.title("PO Dashboard")

# Read credentials from Streamlit Secrets
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

# Replace with your actual Google Sheet ID
SHEET_ID = "1Wyw9IonVmLpiL2yoiVe2bSa9IgLhSCcO_h4Y_2gSgHU"

spreadsheet = client.open_by_key(SHEET_ID)

ws1 = spreadsheet.worksheet("PO List & Payment schedule")

data = ws1.get_all_records()

df = pd.DataFrame(data)

st.success("Connected Successfully!")

st.write("Rows Loaded:", len(df))

st.dataframe(df.head(10))
