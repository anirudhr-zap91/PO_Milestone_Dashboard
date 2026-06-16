import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
        [data-testid="stSidebar"] {background-color: #1a3c5e;}
        [data-testid="stSidebar"] * {color: white !important;}
        [data-testid="stSidebar"] .stRadio label {
            font-size: 1rem; padding: 8px 0; display: block;
        }
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
# LOAD SHEET 1 : PO LIST & PAYMENT SCHEDULE
# ==================================================
ws_po = spreadsheet.worksheet("PO List & Payment schedule")
po_records = ws_po.get_all_values()
po_headers = [str(c).strip() for c in po_records[1]]
df_po = pd.DataFrame(po_records[2:], columns=po_headers)

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

df_po = df_po.replace("", pd.NA).dropna(how="all")
df_po["Outflow Amount"] = clean_amount(df_po["Outflow Amount"]) / 1e7
df_po["Value"] = clean_amount(df_po["Value"]) / 1e7
df_po["Outflow_Month_Date"] = parse_month(df_po["Outflow Month"])
df_po = df_po[df_po["Outflow Amount"].notna() & df_po["Outflow_Month_Date"].notna()]

# ==================================================
# LOAD SHEET 2 : PO TO BE ISSUED
# ==================================================
ws_plan = spreadsheet.worksheet("PO to be issued")
plan_records = ws_plan.get_all_values()
plan_headers = [str(c).strip() for c in plan_records[1]]
df_plan = pd.DataFrame(plan_records[2:68], columns=plan_headers)

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
df_plan = df_plan[(df_plan["Amount"] > 0) & (df_plan["Month_Date"].notna())]

# ==================================================
# CURRENT MONTH
# ==================================================
today = pd.Timestamp.today()
current_month = pd.Timestamp(year=today.year, month=today.month, day=1)
current_month_label = current_month.strftime("%B %Y")

plan_window = df_plan[df_plan["Month_Date"] == current_month].copy()
po_window = df_po[df_po["Outflow_Month_Date"] == current_month].copy()

total_planned = plan_window["Amount"].sum()
total_actual = po_window["Outflow Amount"].sum()
total_expected = total_planned + total_actual

# ==================================================
# SIDEBAR NAVIGATION
# ==================================================
page = st.sidebar.radio(
    "Navigate",
    ["📊 Overview", "📋 This Month Detail", "📅 Upcoming Month", "📈 Historical Data"],
    label_visibility="collapsed"
)

# ==================================================
# PAGE 1: OVERVIEW
# ==================================================
if page == "📊 Overview":

    st.markdown(f"""
        <h2 style="color:#1a3c5e; margin: 10px 0 20px 0">
            📅 Current Month: {current_month_label}
        </h2>
    """, unsafe_allow_html=True)

    # ----------------------------------------------
    # KPI CARDS
    # ----------------------------------------------
    st.markdown(f"""
        <div style="display: flex; gap: 20px; margin: 20px 0">
            <div style="flex:1; background:#eaf4fb; border-left: 5px solid #2980b9;
                        padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                <p style="margin:0; color:#555; font-size:0.85rem">Actual PO Outflow</p>
                <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_actual:.2f} Cr</h2>
                <p style="margin:0; color:#888; font-size:0.8rem">Already committed & due {current_month_label}</p>
            </div>
            <div style="flex:1; background:#fef9e7; border-left: 5px solid #f39c12;
                        padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                <p style="margin:0; color:#555; font-size:0.85rem">Planned New PO Requirement</p>
                <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_planned:.2f} Cr</h2>
                <p style="margin:0; color:#888; font-size:0.8rem">New POs to be issued {current_month_label}</p>
            </div>
            <div style="flex:1; background:#eafaf1; border-left: 5px solid #27ae60;
                        padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                <p style="margin:0; color:#555; font-size:0.85rem">Total Expected Outflow</p>
                <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_expected:.2f} Cr</h2>
                <p style="margin:0; color:#888; font-size:0.8rem">Actual + Planned combined</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ----------------------------------------------
    # CHARTS ROW 1: Donut + Bar side by side
    # ----------------------------------------------
    section_header("Outflow Breakdown", "📊")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        # Donut: actual outflow by Head
        donut_data = (
            po_window
            .groupby("Head")["Outflow Amount"]
            .sum()
            .reset_index()
        )
        donut_data = donut_data[donut_data["Outflow Amount"] > 0]

        fig_donut = go.Figure(data=[go.Pie(
            labels=donut_data["Head"],
            values=donut_data["Outflow Amount"],
            hole=0.5,
            textinfo="label+percent",
            hovertemplate="%{label}<br>₹ %{value:.2f} Cr<extra></extra>"
        )])
        fig_donut.update_layout(
            title=dict(text="Actual Outflow by Head", font=dict(color="#1a3c5e", size=15)),
            showlegend=True,
            height=380,
            margin=dict(t=50, b=20, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.1)
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with chart_col2:
        # Bar: planned requirement by Category
        bar_data = (
            plan_window
            .groupby("Category")["Amount"]
            .sum()
            .reset_index()
            .sort_values("Amount", ascending=True)
        )

        fig_bar = go.Figure(go.Bar(
            x=bar_data["Amount"],
            y=bar_data["Category"],
            orientation="h",
            marker_color="#2980b9",
            text=bar_data["Amount"].apply(lambda x: f"₹ {x:.2f} Cr"),
            textposition="outside",
            hovertemplate="%{y}<br>₹ %{x:.2f} Cr<extra></extra>"
        ))
        fig_bar.update_layout(
            title=dict(text="Planned Requirement by Category", font=dict(color="#1a3c5e", size=15)),
            xaxis_title="Amount (Cr)",
            height=380,
            margin=dict(t=50, b=20, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="#e8ecef")
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ----------------------------------------------
    # CHARTS ROW 2: Settlement status + Pipeline
    # ----------------------------------------------
    section_header("Payment & Pipeline Status", "🔍")
    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        # Bar: Settled vs Pending for current month
        po_window["Settlement"] = po_window["Payment Status"].apply(
            lambda x: "Settled" if str(x).strip() in ["Completed", "LC issued"] else "Pending"
        )

        settlement_data = (
            po_window
            .groupby(["Head", "Settlement"])["Outflow Amount"]
            .sum()
            .reset_index()
        )

        fig_settle = px.bar(
            settlement_data,
            x="Head",
            y="Outflow Amount",
            color="Settlement",
            barmode="group",
            color_discrete_map={"Settled": "#27ae60", "Pending": "#c0392b"},
            labels={"Outflow Amount": "Amount (Cr)", "Head": ""},
            title="Settled vs Pending by Head",
            text_auto=".2f"
        )
        fig_settle.update_layout(
            height=380,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title="",
            title_font=dict(color="#1a3c5e", size=15),
            yaxis=dict(showgrid=True, gridcolor="#e8ecef")
        )
        st.plotly_chart(fig_settle, use_container_width=True)

   
