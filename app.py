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
total_project_value = df_po.drop_duplicates(subset=["PO"])["Value"].sum()

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

elif page == "📋 This Month Detail":

    st.markdown(f"""
        <h2 style="color:#1a3c5e; margin: 10px 0 20px 0">
            📋 This Month Detail: {current_month_label}
        </h2>
    """, unsafe_allow_html=True)

    # ----------------------------------------------
    # TAB LAYOUT: Planned | Actual | Weekly
    # ----------------------------------------------
    tab1, tab2, tab3 = st.tabs(["📌 Planned PO Requirement", "💰 Actual PO Outflow", "📅 Weekly Breakdown"])

    # ==================
    # TAB 1: PLANNED
    # ==================
    with tab1:
        section_header("Planned PO Requirement", "📌")

        if plan_window.empty:
            st.info("No planned POs found for this month.")
        else:
            col_left, col_right = st.columns(2)

            with col_left:
                # Table
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
                        return [
                            "font-weight: bold; background-color: #eaf4fb; color: #1a3c5e",
                            "",
                            ""
                        ]
                    return ["", "", ""]

                styled_plan = (
                    display_plan_table.style
                    .apply(style_plan_table, axis=1)
                    .hide(axis="index")
                    .format({"Amount": "{:.2f}"})
                )
                st.markdown(styled_plan.to_html(), unsafe_allow_html=True)

                # Category total below table
                st.markdown(f"""
                    <div style="margin-top:12px; padding: 10px 14px;
                                background:#eafaf1; border-radius:6px;
                                border-left: 4px solid #27ae60">
                        <strong style="color:#1a3c5e">
                            Total Planned: ₹ {total_planned:.2f} Cr
                        </strong>
                    </div>
                """, unsafe_allow_html=True)

            with col_right:
                # Donut chart by Category
                plan_cat = (
                    plan_window
                    .groupby("Category")["Amount"]
                    .sum()
                    .reset_index()
                )

                fig_plan_donut = go.Figure(data=[go.Pie(
                    labels=plan_cat["Category"],
                    values=plan_cat["Amount"],
                    hole=0.5,
                    textinfo="label+percent",
                    hovertemplate="%{label}<br>₹ %{value:.2f} Cr<extra></extra>"
                )])
                fig_plan_donut.update_layout(
                    title=dict(
                        text="Planned Requirement by Category",
                        font=dict(color="#1a3c5e", size=15)
                    ),
                    height=420,
                    margin=dict(t=50, b=20, l=20, r=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", y=-0.15)
                )
                st.plotly_chart(fig_plan_donut, use_container_width=True)

    # ==================
    # TAB 2: ACTUAL
    # ==================
    with tab2:
        section_header("Actual PO Outflow", "💰")

        if po_window.empty:
            st.info("No actual PO outflow found for this month.")
        else:
            col_left, col_right = st.columns(2)

            with col_left:
                # Table: Sub Head + Outflow Week + Amount
                actual_table = (
                    po_window
                    .groupby(["Head", "Sub Head"], as_index=False)["Outflow Amount"]
                    .sum()
                    .sort_values(["Head", "Sub Head"])
                )

                display_actual = actual_table.copy()
                display_actual["Head"] = display_actual["Head"].where(
                    display_actual["Head"] != display_actual["Head"].shift(), ""
                )

                def style_actual_table(row):
                    if row["Head"] != "":
                        return [
                            "font-weight: bold; background-color: #eaf4fb; color: #1a3c5e",
                            "",
                            ""
                        ]
                    return ["", "", ""]

                styled_actual = (
                    display_actual.style
                    .apply(style_actual_table, axis=1)
                    .hide(axis="index")
                    .format({"Outflow Amount": "{:.2f}"})
                )
                st.markdown(styled_actual.to_html(), unsafe_allow_html=True)

                st.markdown(f"""
                    <div style="margin-top:12px; padding: 10px 14px;
                                background:#eaf4fb; border-radius:6px;
                                border-left: 4px solid #2980b9">
                        <strong style="color:#1a3c5e">
                            Total Actual Outflow: ₹ {total_actual:.2f} Cr
                        </strong>
                    </div>
                """, unsafe_allow_html=True)

            with col_right:
                # Donut chart by Head
                actual_head = (
                    po_window
                    .groupby("Head")["Outflow Amount"]
                    .sum()
                    .reset_index()
                )

                fig_actual_donut = go.Figure(data=[go.Pie(
                    labels=actual_head["Head"],
                    values=actual_head["Outflow Amount"],
                    hole=0.5,
                    textinfo="label+percent",
                    hovertemplate="%{label}<br>₹ %{value:.2f} Cr<extra></extra>"
                )])
                fig_actual_donut.update_layout(
                    title=dict(
                        text="Actual Outflow by Head",
                        font=dict(color="#1a3c5e", size=15)
                    ),
                    height=420,
                    margin=dict(t=50, b=20, l=20, r=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", y=-0.15)
                )
                st.plotly_chart(fig_actual_donut, use_container_width=True)

    # ==================
    # TAB 3: WEEKLY
    # ==================
    with tab3:
        section_header("Weekly Outflow Breakdown", "📅")

        if po_window.empty:
            st.info("No outflow data found for this month.")
        else:
            po_window["Settlement"] = po_window["Payment Status"].apply(
                lambda x: "Settled" if str(x).strip() in ["Completed", "LC issued"] else "Pending"
            )

            weekly = (
                po_window
                .groupby(["Outflow Week", "Sub Head", "Settlement"], as_index=False)["Outflow Amount"]
                .sum()
            )
            weekly["Outflow Week"] = weekly["Outflow Week"].replace("", "N/A")

            weekly_totals = weekly.groupby(
                ["Outflow Week", "Settlement"], as_index=False
            )["Outflow Amount"].sum()
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

            for col in ["Settled", "Pending"]:
                if col not in weekly_pivot.columns:
                    weekly_pivot[col] = 0.0

            weekly_pivot["Settled"] = weekly_pivot["Settled"].fillna(0)
            weekly_pivot["Pending"] = weekly_pivot["Pending"].fillna(0)
            weekly_pivot["Total"] = weekly_pivot["Settled"] + weekly_pivot["Pending"]

            # Add blank separator row between weeks
            weeks_list = weekly_pivot["Outflow Week"].unique().tolist()
            separated = []
            for week in weeks_list:
                week_rows = weekly_pivot[weekly_pivot["Outflow Week"] == week]
                separated.append(week_rows)
                blank = pd.DataFrame([["", "", 0.0, 0.0, 0.0]], columns=weekly_pivot.columns)
                separated.append(blank)

            weekly_pivot = pd.concat(separated, ignore_index=True)

            col_left, col_right = st.columns(2)

            with col_left:
                display_weekly = weekly_pivot.copy()
                display_weekly["Outflow Week"] = display_weekly["Outflow Week"].where(
                    display_weekly["Outflow Week"] != display_weekly["Outflow Week"].shift(), ""
                )

                def style_weekly(row):
                    if row["Sub Head"] == "":
                        return [""] * len(row)
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

            with col_right:
                # Stacked bar: Settled + Pending per week
                # Exclude blank and TOTAL rows for chart
                weekly_chart = weekly_pivot[
                    (weekly_pivot["Sub Head"] != "TOTAL") &
                    (weekly_pivot["Sub Head"] != "")
                ].copy()

                week_summary = (
                    weekly_chart
                    .groupby("Outflow Week")[["Settled", "Pending"]]
                    .sum()
                    .reset_index()
                )

                fig_weekly = go.Figure()
                fig_weekly.add_trace(go.Bar(
                    name="Settled",
                    x=week_summary["Outflow Week"],
                    y=week_summary["Settled"],
                    marker_color="#27ae60",
                    text=week_summary["Settled"].apply(lambda x: f"{x:.2f}"),
                    textposition="inside"
                ))
                fig_weekly.add_trace(go.Bar(
                    name="Pending",
                    x=week_summary["Outflow Week"],
                    y=week_summary["Pending"],
                    marker_color="#c0392b",
                    text=week_summary["Pending"].apply(lambda x: f"{x:.2f}"),
                    textposition="inside"
                ))
                fig_weekly.update_layout(
                    barmode="stack",
                    title=dict(
                        text="Settled vs Pending by Week",
                        font=dict(color="#1a3c5e", size=15)
                    ),
                    xaxis_title="Week",
                    yaxis_title="Amount (Cr)",
                    height=420,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend_title="",
                    yaxis=dict(showgrid=True, gridcolor="#e8ecef")
                )
                st.plotly_chart(fig_weekly, use_container_width=True)
                
elif page == "📅 Upcoming Month":

    next_month = current_month + pd.DateOffset(months=1)
    next_month_label = next_month.strftime("%B %Y")

    st.markdown(f"""
        <h2 style="color:#1a3c5e; margin: 10px 0 20px 0">
            📅 Upcoming Month: {next_month_label}
        </h2>
    """, unsafe_allow_html=True)

    # Filter both sheets to next month
    plan_next = df_plan[df_plan["Month_Date"] == next_month].copy()
    po_next = df_po[df_po["Outflow_Month_Date"] == next_month].copy()

    total_planned_next = plan_next["Amount"].sum()
    total_actual_next = po_next["Outflow Amount"].sum()
    total_expected_next = total_planned_next + total_actual_next

    # ----------------------------------------------
    # KPI CARDS
    # ----------------------------------------------
    st.markdown(f"""
        <div style="display: flex; gap: 20px; margin: 20px 0">
            <div style="flex:1; background:#eaf4fb; border-left: 5px solid #2980b9;
                        padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                <p style="margin:0; color:#555; font-size:0.85rem">Actual PO Outflow</p>
                <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_actual_next:.2f} Cr</h2>
                <p style="margin:0; color:#888; font-size:0.8rem">Already committed & due {next_month_label}</p>
            </div>
            <div style="flex:1; background:#fef9e7; border-left: 5px solid #f39c12;
                        padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                <p style="margin:0; color:#555; font-size:0.85rem">Planned New PO Requirement</p>
                <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_planned_next:.2f} Cr</h2>
                <p style="margin:0; color:#888; font-size:0.8rem">New POs to be issued {next_month_label}</p>
            </div>
            <div style="flex:1; background:#fef9e7; border-left: 5px solid #f39c12;
                            padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                    <p style="margin:0; color:#555; font-size:0.85rem">Total Expected Outflow</p>
                    <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_expected_next:.2f} Cr</h2>
                    <p style="margin:0; color:#888; font-size:0.8rem">Actual + Planned combined</p>
                </div>
            </div>
    """, unsafe_allow_html=True)

    # ----------------------------------------------
    # TABS
    # ----------------------------------------------
    tab1, tab2, tab3 = st.tabs(["📌 Planned PO Requirement", "💰 Actual PO Outflow", "📅 Weekly Breakdown"])

    # ==================
    # TAB 1: PLANNED
    # ==================
    with tab1:
        section_header("Planned PO Requirement", "📌")

        if plan_next.empty:
            st.info(f"No planned POs found for {next_month_label}.")
        else:
            col_left, col_right = st.columns(2)

            with col_left:
                plan_table_next = (
                    plan_next
                    .groupby(["Category", "Sub-Category"], as_index=False)["Amount"]
                    .sum()
                    .sort_values(["Category", "Sub-Category"])
                )

                display_plan_next = plan_table_next.copy()
                display_plan_next["Category"] = display_plan_next["Category"].where(
                    display_plan_next["Category"] != display_plan_next["Category"].shift(), ""
                )

                def style_plan_next(row):
                    if row["Category"] != "":
                        return [
                            "font-weight: bold; background-color: #eaf4fb; color: #1a3c5e",
                            "",
                            ""
                        ]
                    return ["", "", ""]

                styled_plan_next = (
                    display_plan_next.style
                    .apply(style_plan_next, axis=1)
                    .hide(axis="index")
                    .format({"Amount": "{:.2f}"})
                )
                st.markdown(styled_plan_next.to_html(), unsafe_allow_html=True)

                st.markdown(f"""
                    <div style="margin-top:12px; padding: 10px 14px;
                                background:#eafaf1; border-radius:6px;
                                border-left: 4px solid #27ae60">
                        <strong style="color:#1a3c5e">
                            Total Planned: ₹ {total_planned_next:.2f} Cr
                        </strong>
                    </div>
                """, unsafe_allow_html=True)

            with col_right:
                plan_cat_next = (
                    plan_next
                    .groupby("Category")["Amount"]
                    .sum()
                    .reset_index()
                )

                fig_plan_next = go.Figure(data=[go.Pie(
                    labels=plan_cat_next["Category"],
                    values=plan_cat_next["Amount"],
                    hole=0.5,
                    textinfo="label+percent",
                    hovertemplate="%{label}<br>₹ %{value:.2f} Cr<extra></extra>"
                )])
                fig_plan_next.update_layout(
                    title=dict(
                        text=f"Planned Requirement by Category ({next_month_label})",
                        font=dict(color="#1a3c5e", size=15)
                    ),
                    height=420,
                    margin=dict(t=50, b=20, l=20, r=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", y=-0.15)
                )
                st.plotly_chart(fig_plan_next, use_container_width=True)

    # ==================
    # TAB 2: ACTUAL
    # ==================
    with tab2:
        section_header("Actual PO Outflow", "💰")

        if po_next.empty:
            st.info(f"No actual PO outflow found for {next_month_label}.")
        else:
            col_left, col_right = st.columns(2)

            with col_left:
                actual_table_next = (
                    po_next
                    .groupby(["Head", "Sub Head"], as_index=False)["Outflow Amount"]
                    .sum()
                    .sort_values(["Head", "Sub Head"])
                )

                display_actual_next = actual_table_next.copy()
                display_actual_next["Head"] = display_actual_next["Head"].where(
                    display_actual_next["Head"] != display_actual_next["Head"].shift(), ""
                )

                def style_actual_next(row):
                    if row["Head"] != "":
                        return [
                            "font-weight: bold; background-color: #eaf4fb; color: #1a3c5e",
                            "",
                            ""
                        ]
                    return ["", "", ""]

                styled_actual_next = (
                    display_actual_next.style
                    .apply(style_actual_next, axis=1)
                    .hide(axis="index")
                    .format({"Outflow Amount": "{:.2f}"})
                )
                st.markdown(styled_actual_next.to_html(), unsafe_allow_html=True)

                st.markdown(f"""
                    <div style="margin-top:12px; padding: 10px 14px;
                                background:#eaf4fb; border-radius:6px;
                                border-left: 4px solid #2980b9">
                        <strong style="color:#1a3c5e">
                            Total Actual Outflow: ₹ {total_actual_next:.2f} Cr
                        </strong>
                    </div>
                """, unsafe_allow_html=True)

            with col_right:
                actual_head_next = (
                    po_next
                    .groupby("Head")["Outflow Amount"]
                    .sum()
                    .reset_index()
                )

                fig_actual_next = go.Figure(data=[go.Pie(
                    labels=actual_head_next["Head"],
                    values=actual_head_next["Outflow Amount"],
                    hole=0.5,
                    textinfo="label+percent",
                    hovertemplate="%{label}<br>₹ %{value:.2f} Cr<extra></extra>"
                )])
                fig_actual_next.update_layout(
                    title=dict(
                        text=f"Actual Outflow by Head ({next_month_label})",
                        font=dict(color="#1a3c5e", size=15)
                    ),
                    height=420,
                    margin=dict(t=50, b=20, l=20, r=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", y=-0.15)
                )
                st.plotly_chart(fig_actual_next, use_container_width=True)

    # ==================
    # TAB 3: WEEKLY
    # ==================
    with tab3:
        section_header("Weekly Outflow Breakdown", "📅")

        if po_next.empty:
            st.info(f"No outflow data found for {next_month_label}.")
        else:
            po_next["Settlement"] = po_next["Payment Status"].apply(
                lambda x: "Settled" if str(x).strip() in ["Completed", "LC issued"] else "Pending"
            )

            weekly_n = (
                po_next
                .groupby(["Outflow Week", "Sub Head", "Settlement"], as_index=False)["Outflow Amount"]
                .sum()
            )
            weekly_n["Outflow Week"] = weekly_n["Outflow Week"].replace("", "N/A")

            weekly_totals_n = weekly_n.groupby(
                ["Outflow Week", "Settlement"], as_index=False
            )["Outflow Amount"].sum()
            weekly_totals_n["Sub Head"] = "TOTAL"

            weekly_n["__order"] = 0
            weekly_totals_n["__order"] = 1

            weekly_combined_n = pd.concat([weekly_n, weekly_totals_n], ignore_index=True)
            weekly_combined_n = weekly_combined_n.sort_values(["Outflow Week", "__order", "Sub Head"])
            weekly_combined_n = weekly_combined_n.drop(columns="__order")

            weekly_pivot_n = weekly_combined_n.pivot_table(
                index=["Outflow Week", "Sub Head"],
                columns="Settlement",
                values="Outflow Amount",
                aggfunc="sum"
            ).reset_index()

            weekly_pivot_n.columns.name = None

            for col in ["Settled", "Pending"]:
                if col not in weekly_pivot_n.columns:
                    weekly_pivot_n[col] = 0.0

            weekly_pivot_n["Settled"] = weekly_pivot_n["Settled"].fillna(0)
            weekly_pivot_n["Pending"] = weekly_pivot_n["Pending"].fillna(0)
            weekly_pivot_n["Total"] = weekly_pivot_n["Settled"] + weekly_pivot_n["Pending"]

            weekly_pivot_n["__order"] = weekly_pivot_n["Sub Head"].apply(
                lambda x: 1 if x == "TOTAL" else 0
            )
            weekly_pivot_n = weekly_pivot_n.sort_values(
                ["Outflow Week", "__order", "Sub Head"]
            ).drop(columns="__order").reset_index(drop=True)

            weeks_list_n = weekly_pivot_n["Outflow Week"].unique().tolist()
            separated_n = []
            for week in weeks_list_n:
                week_rows = weekly_pivot_n[weekly_pivot_n["Outflow Week"] == week]
                separated_n.append(week_rows)
                blank = pd.DataFrame(
                    [["", "", 0.0, 0.0, 0.0]],
                    columns=weekly_pivot_n.columns
                )
                separated_n.append(blank)

            weekly_pivot_n = pd.concat(separated_n, ignore_index=True)

            col_left, col_right = st.columns(2)

            with col_left:
                display_weekly_n = weekly_pivot_n.copy()
                display_weekly_n["Outflow Week"] = display_weekly_n["Outflow Week"].where(
                    display_weekly_n["Outflow Week"] != display_weekly_n["Outflow Week"].shift(), ""
                )

                def style_weekly_n(row):
                    if row["Sub Head"] == "":
                        return [""] * len(row)
                    is_total = row["Sub Head"] == "TOTAL"
                    base = "font-weight: bold; " if is_total else ""
                    return [
                        base,
                        base,
                        base + "color: #27ae60",
                        base + "color: #c0392b",
                        base
                    ]

                styled_weekly_n = (
                    display_weekly_n.style
                    .apply(style_weekly_n, axis=1)
                    .hide(axis="index")
                    .format({"Settled": "{:.2f}", "Pending": "{:.2f}", "Total": "{:.2f}"})
                )
                st.markdown(styled_weekly_n.to_html(), unsafe_allow_html=True)

            with col_right:
                weekly_chart_n = weekly_pivot_n[
                    (weekly_pivot_n["Sub Head"] != "TOTAL") &
                    (weekly_pivot_n["Sub Head"] != "")
                ].copy()

                week_summary_n = (
                    weekly_chart_n
                    .groupby("Outflow Week")[["Settled", "Pending"]]
                    .sum()
                    .reset_index()
                )

                fig_weekly_n = go.Figure()
                fig_weekly_n.add_trace(go.Bar(
                    name="Settled",
                    x=week_summary_n["Outflow Week"],
                    y=week_summary_n["Settled"],
                    marker_color="#27ae60",
                    text=week_summary_n["Settled"].apply(lambda x: f"{x:.2f}"),
                    textposition="inside"
                ))
                fig_weekly_n.add_trace(go.Bar(
                    name="Pending",
                    x=week_summary_n["Outflow Week"],
                    y=week_summary_n["Pending"],
                    marker_color="#c0392b",
                    text=week_summary_n["Pending"].apply(lambda x: f"{x:.2f}"),
                    textposition="inside"
                ))
                fig_weekly_n.update_layout(
                    barmode="stack",
                    title=dict(
                        text=f"Settled vs Pending by Week ({next_month_label})",
                        font=dict(color="#1a3c5e", size=15)
                    ),
                    xaxis_title="Week",
                    yaxis_title="Amount (Cr)",
                    height=420,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend_title="",
                    yaxis=dict(showgrid=True, gridcolor="#e8ecef")
                )
                st.plotly_chart(fig_weekly_n, use_container_width=True)
elif page == "📈 Historical Data":

    st.markdown("""
        <h2 style="color:#1a3c5e; margin: 10px 0 20px 0">
            📈 Historical Data
        </h2>
    """, unsafe_allow_html=True)

    # Filter to all months strictly before current month
    df_hist = df_po[df_po["Outflow_Month_Date"] < current_month].copy()

    if df_hist.empty:
        st.info("No historical data found before the current month.")
    else:
        # ----------------------------------------------
        # KPI CARDS
        # ----------------------------------------------
        total_hist = df_hist["Outflow Amount"].sum()
        total_settled_hist = df_hist[
            df_hist["Payment Status"].isin(["Completed", "LC issued"])
        ]["Outflow Amount"].sum()
        total_funds_required = total_project_value - total_settled_hist

        st.markdown(f"""
            <div style="display: flex; gap: 20px; margin: 20px 0">
                <div style="flex:1; background:#eaf4fb; border-left: 5px solid #2980b9;
                            padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                    <p style="margin:0; color:#555; font-size:0.85rem">Total Historical Outflow</p>
                    <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_hist:.2f} Cr</h2>
                    <p style="margin:0; color:#888; font-size:0.8rem">All months before {current_month_label}</p>
                </div>
                <div style="flex:1; background:#eafaf1; border-left: 5px solid #27ae60;
                            padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                    <p style="margin:0; color:#555; font-size:0.85rem">Total Settled</p>
                    <h2 style="margin:5px 0; color:#27ae60">₹ {total_settled_hist:.2f} Cr</h2>
                    <p style="margin:0; color:#888; font-size:0.8rem">Completed + LC Issued</p>
                </div>
                <div style="flex:1; background:#fdf2f2; border-left: 5px solid #c0392b;
                            padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                    <p style="margin:0; color:#555; font-size:0.85rem">Funds Required to Complete Project</p>
                    <h2 style="margin:5px 0; color:#c0392b">₹ {total_funds_required:.2f} Cr</h2>
                    <p style="margin:0; color:#888; font-size:0.8rem">Total Project Value − Settled So Far</p>
                </div>
                <div style="flex:1; background:#fef9e7; border-left: 5px solid #f39c12;
                            padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.06)">
                    <p style="margin:0; color:#555; font-size:0.85rem">Total Project Value (POs Issued)</p>
                    <h2 style="margin:5px 0; color:#1a3c5e">₹ {total_project_value:.2f} Cr</h2>
                    <p style="margin:0; color:#888; font-size:0.8rem">Total contracted value across all POs</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # ----------------------------------------------
        # TABS
        # ----------------------------------------------
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Monthly Overview",
            "💳 Payment Status",
            "🏗️ Head Breakdown",
            "🏢 Vendor Analysis"
        ])

        # ==================
        # TAB 1: MONTHLY OVERVIEW
        # ==================
        with tab1:
            section_header("Month-wise Outflow", "📊")

            monthly = (
                df_hist
                .groupby("Outflow_Month_Date", as_index=False)["Outflow Amount"]
                .sum()
                .sort_values("Outflow_Month_Date")
            )
            monthly["Month Label"] = monthly["Outflow_Month_Date"].dt.strftime("%b %Y")
            monthly["Cumulative"] = monthly["Outflow Amount"].cumsum()

            # Combined bar + line chart
            fig_monthly = go.Figure()

            fig_monthly.add_trace(go.Bar(
                x=monthly["Month Label"],
                y=monthly["Outflow Amount"],
                name="Monthly Outflow",
                marker_color="#2980b9",
                text=monthly["Outflow Amount"].apply(lambda x: f"{x:.2f}"),
                textposition="outside",
                yaxis="y1"
            ))

            fig_monthly.add_trace(go.Scatter(
                x=monthly["Month Label"],
                y=monthly["Cumulative"],
                name="Cumulative Outflow",
                mode="lines+markers",
                line=dict(color="#f39c12", width=2),
                marker=dict(size=6),
                yaxis="y2"
            ))

            fig_monthly.update_layout(
                title=dict(
                    text="Monthly vs Cumulative Outflow",
                    font=dict(color="#1a3c5e", size=15)
                ),
                xaxis=dict(title="Month"),
                yaxis=dict(
                    title="Monthly Outflow (Cr)",
                    showgrid=True,
                    gridcolor="#e8ecef"
                ),
                yaxis2=dict(
                    title="Cumulative Outflow (Cr)",
                    overlaying="y",
                    side="right",
                    showgrid=False
                ),
                height=450,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=-0.2),
                barmode="group"
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

            # Summary table below chart
            section_header("Month-wise Summary Table", "📋")
            summary_table = monthly[["Month Label", "Outflow Amount", "Cumulative"]].copy()
            summary_table = summary_table.rename(columns={
                "Month Label": "Month",
                "Outflow Amount": "Outflow (Cr)",
                "Cumulative": "Cumulative (Cr)"
            })
            st.dataframe(
                summary_table.style
                .format({"Outflow (Cr)": "{:.2f}", "Cumulative (Cr)": "{:.2f}"})
                .hide(axis="index"),
                use_container_width=True
            )

        # ==================
        # TAB 2: PAYMENT STATUS
        # ==================
        with tab2:
            section_header("Payment Status Breakdown", "💳")

            col_left, col_right = st.columns(2)

            with col_left:
                # Month-wise stacked bar: Settled vs Pending
                df_hist["Settlement"] = df_hist["Payment Status"].apply(
                    lambda x: "Settled" if str(x).strip() in ["Completed", "LC issued"] else "Pending"
                )

                monthly_status = (
                    df_hist
                    .groupby(["Outflow_Month_Date", "Settlement"], as_index=False)["Outflow Amount"]
                    .sum()
                    .sort_values("Outflow_Month_Date")
                )
                monthly_status["Month Label"] = monthly_status["Outflow_Month_Date"].dt.strftime("%b %Y")

                fig_status = px.bar(
                    monthly_status,
                    x="Month Label",
                    y="Outflow Amount",
                    color="Settlement",
                    barmode="stack",
                    color_discrete_map={"Settled": "#27ae60", "Pending": "#c0392b"},
                    labels={"Outflow Amount": "Amount (Cr)", "Month Label": "Month"},
                    title="Monthly Settled vs Pending",
                    text_auto=".2f"
                )
                fig_status.update_layout(
                    height=420,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend_title="",
                    title_font=dict(color="#1a3c5e", size=15),
                    yaxis=dict(showgrid=True, gridcolor="#e8ecef")
                )
                st.plotly_chart(fig_status, use_container_width=True)

            with col_right:
                # Overall payment status donut
                status_overall = (
                    df_hist
                    .groupby("Payment Status")["Outflow Amount"]
                    .sum()
                    .reset_index()
                )
                status_overall = status_overall[status_overall["Outflow Amount"] > 0]

                fig_status_donut = go.Figure(data=[go.Pie(
                    labels=status_overall["Payment Status"],
                    values=status_overall["Outflow Amount"],
                    hole=0.5,
                    textinfo="label+percent",
                    hovertemplate="%{label}<br>₹ %{value:.2f} Cr<extra></extra>"
                )])
                fig_status_donut.update_layout(
                    title=dict(
                        text="Overall Payment Status (All History)",
                        font=dict(color="#1a3c5e", size=15)
                    ),
                    height=420,
                    margin=dict(t=50, b=20, l=20, r=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", y=-0.15)
                )
                st.plotly_chart(fig_status_donut, use_container_width=True)

        # ==================
        # TAB 3: HEAD BREAKDOWN
        # ==================
        with tab3:
            section_header("Outflow by Head Over Time", "🏗️")

            # Month-wise stacked bar by Head
            monthly_head = (
                df_hist
                .groupby(["Outflow_Month_Date", "Head"], as_index=False)["Outflow Amount"]
                .sum()
                .sort_values("Outflow_Month_Date")
            )
            monthly_head["Month Label"] = monthly_head["Outflow_Month_Date"].dt.strftime("%b %Y")

            fig_head = px.bar(
                monthly_head,
                x="Month Label",
                y="Outflow Amount",
                color="Head",
                barmode="stack",
                labels={"Outflow Amount": "Amount (Cr)", "Month Label": "Month"},
                title="Month-wise Outflow by Head",
                text_auto=".2f"
            )
            fig_head.update_layout(
                height=450,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend_title="Head",
                title_font=dict(color="#1a3c5e", size=15),
                yaxis=dict(showgrid=True, gridcolor="#e8ecef")
            )
            st.plotly_chart(fig_head, use_container_width=True)

            # Summary table: total per Head
            section_header("Total Outflow per Head", "📋")
            head_summary = (
                df_hist
                .groupby("Head", as_index=False)["Outflow Amount"]
                .sum()
                .sort_values("Outflow Amount", ascending=False)
                .rename(columns={"Outflow Amount": "Total Outflow (Cr)"})
            )

            col_left, col_right = st.columns(2)
            with col_left:
                st.dataframe(
                    head_summary.style
                    .format({"Total Outflow (Cr)": "{:.2f}"})
                    .hide(axis="index"),
                    use_container_width=True
                )
            with col_right:
                fig_head_bar = go.Figure(go.Bar(
                    x=head_summary["Total Outflow (Cr)"],
                    y=head_summary["Head"],
                    orientation="h",
                    marker_color="#2980b9",
                    text=head_summary["Total Outflow (Cr)"].apply(lambda x: f"₹ {x:.2f} Cr"),
                    textposition="outside"
                ))
                fig_head_bar.update_layout(
                    title=dict(
                        text="Total Outflow by Head",
                        font=dict(color="#1a3c5e", size=15)
                    ),
                    height=380,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=True, gridcolor="#e8ecef")
                )
                st.plotly_chart(fig_head_bar, use_container_width=True)

        # ==================
        # TAB 4: VENDOR ANALYSIS
        # ==================
        with tab4:
            section_header("Vendor-wise Outflow", "🏢")

            col_left, col_right = st.columns(2)

            with col_left:
                # Top 10 vendors by total outflow
                vendor_summary = (
                    df_hist
                    .groupby("Vendor", as_index=False)["Outflow Amount"]
                    .sum()
                    .sort_values("Outflow Amount", ascending=False)
                    .head(10)
                    .rename(columns={"Outflow Amount": "Total Outflow (Cr)"})
                )

                fig_vendor = go.Figure(go.Bar(
                    x=vendor_summary["Total Outflow (Cr)"],
                    y=vendor_summary["Vendor"],
                    orientation="h",
                    marker_color="#2980b9",
                    text=vendor_summary["Total Outflow (Cr)"].apply(lambda x: f"₹ {x:.2f} Cr"),
                    textposition="outside"
                ))
                fig_vendor.update_layout(
                    title=dict(
                        text="Top 10 Vendors by Outflow",
                        font=dict(color="#1a3c5e", size=15)
                    ),
                    height=450,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=True, gridcolor="#e8ecef"),
                    yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig_vendor, use_container_width=True)

            with col_right:
                # Settled vs Pending per vendor (top 10)
                vendor_status = (
                    df_hist[df_hist["Vendor"].isin(vendor_summary["Vendor"])]
                    .groupby(["Vendor", "Settlement"], as_index=False)["Outflow Amount"]
                    .sum()
                )

                fig_vendor_status = px.bar(
                    vendor_status,
                    x="Outflow Amount",
                    y="Vendor",
                    color="Settlement",
                    orientation="h",
                    barmode="stack",
                    color_discrete_map={"Settled": "#27ae60", "Pending": "#c0392b"},
                    labels={"Outflow Amount": "Amount (Cr)", "Vendor": ""},
                    title="Settled vs Pending (Top 10 Vendors)"
                )
                fig_vendor_status.update_layout(
                    height=450,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend_title="",
                    title_font=dict(color="#1a3c5e", size=15),
                    xaxis=dict(showgrid=True, gridcolor="#e8ecef"),
                    yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig_vendor_status, use_container_width=True)

            # Vendor detail table
            section_header("Vendor Detail Table", "📋")
            vendor_detail = (
                df_hist
                .groupby(["Vendor", "Settlement"], as_index=False)["Outflow Amount"]
                .sum()
                .pivot_table(
                    index="Vendor",
                    columns="Settlement",
                    values="Outflow Amount",
                    aggfunc="sum"
                ).reset_index()
            )
            vendor_detail.columns.name = None

            for col in ["Settled", "Pending"]:
                if col not in vendor_detail.columns:
                    vendor_detail[col] = 0.0

            vendor_detail["Settled"] = vendor_detail["Settled"].fillna(0)
            vendor_detail["Pending"] = vendor_detail["Pending"].fillna(0)
            vendor_detail["Total"] = vendor_detail["Settled"] + vendor_detail["Pending"]
            vendor_detail = vendor_detail.sort_values("Total", ascending=False)

            st.dataframe(
                vendor_detail.style
                .format({"Settled": "{:.2f}", "Pending": "{:.2f}", "Total": "{:.2f}"})
                .hide(axis="index"),
                use_container_width=True
            )
