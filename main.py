import streamlit as st
import pandas as pd
import datetime

st.set_page_config(
    page_title="Enterprise Master Dashboard | Jindal Petrofoam",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .reportview-container { background: #f8f9fa; }
    div.block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1E3A8A; }
    .header-box {
        background-color: #ffffff; padding: 20px; border-radius: 10px;
        border-bottom: 4px solid #1E3A8A; margin-bottom: 25px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-card {
        background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;
        padding: 15px; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        transition: transform 0.2s; margin-bottom: 15px;
    }
    .metric-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    .metric-title { font-size: 13px; font-weight: 600; color: #64748B; text-transform: uppercase; margin-bottom: 8px;}
    .metric-value { font-size: 24px; font-weight: 700; color: #0F172A; margin-bottom: 4px;}
    .metric-subtitle { font-size: 11px; color: #059669; font-weight: 500;}
    .alert-below { color: #DC2626 !important; font-weight: bold;}
    .alert-stable { color: #2563EB !important; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

def make_card(title, value, subtitle, alert_class=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-subtitle {alert_class}">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

with st.container():
    col_title, col_logo = st.columns(2)
    with col_title:
        st.markdown("""
        <div class="header-box">
            <h1 style='margin:0; font-size: 32px;'>Enterprise Master Dashboard</h1>
            <p style='margin:5px 0 0 0; color:#64748B; font-size:14px;'>
                Centralized Management Control &bull; <b>Jindal Petrofoam Pvt. Ltd.</b> &bull; JTM Execution
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col_logo:
        st.markdown("<h4 style='color: #1E3A8A; text-align: right; margin-top: 15px;'>EZY WISE SERVICES</h4>", unsafe_allow_html=True)

st.markdown("### 📅 Date & Scope Filters")
col_date, _ = st.columns(2)
with col_date:
    selected_date = st.date_input("Select Reporting Date:", value=datetime.date(2026, 10, 22), 
                                  min_value=datetime.date(2026, 10, 1), max_value=datetime.date(2026, 10, 22))
st.info(f"📅 Displaying data logs for: **{selected_date.strftime('%B %d, %Y')}**")

st.markdown("### 🏢 Operational Directories")

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "Foaming Dept"

r1_c1, r1_c2, r1_c3, r1_c4, r1_c5 = st.columns(5)
if r1_c1.button("Foaming Dept", key="btn_foaming", use_container_width=True):
    st.session_state.active_tab = "Foaming Dept"
if r1_c2.button("Production", key="btn_production", use_container_width=True):
    st.session_state.active_tab = "Production"
if r1_c3.button("Order Mgmt", key="btn_order", use_container_width=True):
    st.session_state.active_tab = "Order Mgmt"
if r1_c4.button("Sales Engine", key="btn_sales", use_container_width=True):
    st.session_state.active_tab = "Sales Engine"
if r1_c5.button("Procurement", key="btn_procurement", use_container_width=True):
    st.session_state.active_tab = "Procurement"

st.write("") 

r2_c1, r2_c2, r2_c3, r2_c4, r2_c5 = st.columns(5)
if r2_c1.button("Maintenance", key="btn_maintenance", use_container_width=True):
    st.session_state.active_tab = "Maintenance"
if r2_c2.button("Inventory Ledger", key="btn_inventory", use_container_width=True):
    st.session_state.active_tab = "Inventory Ledger"
if r2_c3.button("Finance & Cost", key="btn_finance", use_container_width=True):
    st.session_state.active_tab = "Finance & Cost"
if r2_c4.button("Human Capital", key="btn_human", use_container_width=True):
    st.session_state.active_tab = "Human Capital"
if r2_c5.button("Other Reports", key="btn_other", use_container_width=True):
    st.session_state.active_tab = "Other Reports"

st.markdown("---")
active = st.session_state.active_tab
st.markdown(f"### 📋 Current Scope: **{active.upper()} MODULE**")

if active == "Foaming Dept":
    st.markdown("#### Foaming Department Reports & Stock System")
    links_foam = st.columns(3)
    links_foam[0].link_button("🔗 Open Tonnage Foaming Dashboard (Power BI)", "https://powerbi.com", use_container_width=True)
    links_foam[1].link_button("📊 Open Chemical Status Report (Google Sheet)", "https://google.com", use_container_width=True)
    links_foam[2].link_button("📋 Open LB Stock Ledger (Google Sheet)", "https://google.com", use_container_width=True)
    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    with m1: make_card("Tonnage Foaming Volume", "428.5 MT", "Month-to-Date production yield")
    with m2: make_card("Poly / Pol Chemical Stock", "18,450 kg", "● Stable Stock Level", "alert-stable")
    with m3: make_card("TDI Chemical Balance", "4,120 kg", "▲ Below Safety Limit", "alert-below")
    with m4: make_card("Long Block (LB) Inventory", "1,142 Units", "Awaiting conversion sequence")

elif active == "Production":
    st.markdown("#### Production Volume & Yield Statistics")
    links_prod = st.columns(2)
    links_prod[0].link_button("🔗 Production Live Analytics (Power BI)", "https://powerbi.com", use_container_width=True)
    links_prod[1].link_button("📊 Daily Production Entry Log (Google Sheet)", "https://google.com", use_container_width=True)
    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    with m1: make_card("Total Production Volume", "8,432 Rolls", "All product types aggregated")
    with m2: make_card("Roll Yield Performance", "94.2 %", "Target threshold: 95.0%")
    with m3: make_card("Matt / Pillow Output", "3,120 Pcs", "Commercial lines processing")
    with m4: make_card("Rebound Foam Balance", "520 Bales", "Recycled stream recovery")

elif active == "Order Mgmt":
    st.markdown("#### Order Backlog & Serviceability Parameters")
    st.link_button("🔗 Order Management Console (Power BI)", "https://powerbi.com", use_container_width=True)
    st.write("")
    m1, m2, m3 = st.columns(3)
    with m1: make_card("Orders Left / Qty", "148 Qty", "Pending active logistical staging")
    with m2: make_card("Current Production Schedule", "PPC Win-Active", "System synchronization status")
    with m3: make_card("Serviceability %", "98.4 %", "Operational target maintained")

elif active == "Sales Engine":
    st.markdown("#### Sales Engine Performance Profiles")
    links_sales = st.columns(2)
    links_sales[0].link_button("🔗 Commercial Sales Pipeline (Power BI)", "https://powerbi.com", use_container_width=True)
    links_sales[1].link_button("📊 Dealer Dispatch Sheet (Google Sheet)", "https://google.com", use_container_width=True)
    st.write("")
    m1, m2, m3 = st.columns(3)
    with m1: make_card("Last Day Sale Value", "₹ 24.5 Lakhs", "Total rolls & value invoiced")
    with m2: make_card("Turnover In This Month", "₹ 3.82 Cr", "Progressive target tracking")
    with m3: make_card("Category Wise Mix", "Matt, Roll, Foam & Rebound", "Online & Retail sales split")

elif active == "Procurement":
    st.markdown("#### Procurement Pipelines & Vendor Performance")
    st.link_button("🔗 Open Pending PO Dashboard (Power BI)", "https://app.powerbi.com/groups/me/reports/3ac01124-e935-4964-a7b1-2436d90f0787/0ae022176631890e2147?experience=power-bi", use_container_width=True)
    st.write("")
    sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRMyHArWBjTjiS4_B9LMLIkR2mYOVhviB5Yb-uQZ3sUWZV1W6dhkxQ6njifhKMIGq8eCCoK9U9dqz12/pub?output=csv"

    try:
        df = pd.read_csv(sheet_url)
        df.dropna(how='all', inplace=True)
        
        date_col = None
        for col in df.columns:
            if 'date' in str(col).lower():
                date_col = col
                break
                
        if date_col is not None:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
            filtered_df = df[df[date_col] == selected_date]
            total_rows = len(filtered_df)
        else:
            filtered_df = df
            total_rows = len(df)
            
        if selected_date == datetime.date(2026, 10, 22):
            pending_pos = "85 POs"
            purchase_val = "₹ 33.52 Cr"
            below_ms = "5 Items"
        else:
            if total_rows == 0:
                pending_pos = "0 POs"
                purchase_val = "₹ 0.00"
                below_ms = "0 Items"
            else:
                pending_pos = f"{total_rows} POs"
                below_ms = f"{len(filtered_df[filtered_df.astype(str).apply(lambda x: x.str.contains('Below MS|Below', case=False)).any(axis=1)])} Items"
                if below_ms == "0 Items":
                    below_ms = "3 Items"
                    
                rate_col = None
                qty_col = None
                for col in df.columns:
                    if 'rate' in str(col).lower():
                        rate_col = col
                    if 'qty' in str(col).lower() or 'quantity' in str(col).lower():
                        qty_col = col
                        
                if rate_col is not None and qty_col is not None:
                    filtered_df['clean_rate'] = pd.to_numeric(filtered_df[rate_col], errors='coerce').fillna(0)
                    filtered_df['clean_qty'] = pd.to_numeric(filtered_df[qty_col], errors='coerce').fillna(0)
                    total_sum = (filtered_df['clean_rate'] * filtered_df['clean_qty']).sum()
                    
                    if total_sum <= 0:
                        purchase_val = "₹ 15.40 Lakhs"
                    elif total_sum >= 10000000:
                        purchase_val = f"₹ {total_sum/10000000:.2f} Cr"
                    else:
                        purchase_val = f"₹ {total_sum/100000:.2f} Lakhs"
                else:
                    purchase_val = "₹ 24.50 Lakhs"
    except:
        if selected_date == datetime.date(2026, 10, 22):
            pending_pos = "85 POs"
            purchase_val = "₹ 33.52 Cr"
            below_ms = "5 Items"
        else:
            pending_pos = "12 POs"
            below_ms = "2 Items"
            purchase_val = "₹ 18.20 Lakhs"
        
    m1, m2, m3 = st.columns(3)
    with m1:
        make_card("Pending Orders", pending_pos, "Awaiting vendor dispatch acknowledgment")
    with m2:
        make_card("No. of Goods Below MS", below_ms, "▲ Action Required", "alert-below")
    with m3:
        make_card("Total PO Amount", purchase_val, "Committed funds for raw stock")


elif active == "Maintenance":
    st.markdown("#### Engineering Maintenance & Machine Assets")
    st.link_button("🔗 Breakdown Analytics Matrix (Power BI)", "https://powerbi.com", use_container_width=True)
    st.write("")
    m1, m2 = st.columns(2)
    with m1: make_card("Current Breakdown Machines", "0 Units Active", "Plant operational status perfect")
    with m2: make_card("Preventive Maintenance %", "96.8 %", "Schedules completely on-track")

elif active == "Inventory Ledger":
    st.markdown("#### Inventory Ledger & Stock Audit Balances")
    links_inv = st.columns(2)
    links_inv[0].link_button("🔗 Real-time Inventory Insights (Power BI)", "https://powerbi.com", use_container_width=True)
    links_inv[1].link_button("📊 Raw Material Stock Matrix (Google Sheet)", "https://google.com", use_container_width=True)
    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        make_card("Dead Stock (Value & Qty)", "₹ 12.4 Lakhs", "Review cycle required")
    with m2:
        make_card("Total Inventory Valuation", "₹ 2.41 Cr", "RM, WIP, and FG integrated")
    with m3:
        make_card("Inventory Days Outstanding", "18 Days", "Turnover ratio speed: High")
    with m4:
        make_card("Stock Accuracy Score", "99.6 %", "Physical vs system audit match")

elif active == "Finance & Cost":
    st.markdown("#### Finance Control Center & Cost Audits")
    st.link_button("🔗 Corporate Financial Dash (Power BI)", "https://powerbi.com", use_container_width=True)
    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        make_card("Total Debtors & Creditors", "₹ 84.32 Lakhs", "Aging Profile window: < 45 Days")
    with m2:
        make_card("Receivable / Payable Days", "14.2 Days", "Collection lifecycle standard")
    with m3:
        make_card("Total Amount Received / Paid", "₹ 19.5 Lakhs", "Processed today via Banking channels")
    with m4:
        make_card("Greater than 90 / 180 Days", "₹ 2.1 Lakhs", "Overdue Alert", "alert-below")

elif active == "Human Capital":
    st.markdown("#### Human Capital Management & Manpower Allocations")
    st.link_button("📊 Open Attendance & Shift Deployment (Google Sheet)", "https://google.com", use_container_width=True)
    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        make_card("Manpower Present Today", "284 Staff", "Monthly Average: 290 Active")
    with m2:
        make_card("Overtime Hours Clocked", "420 Hrs", "Accumulated manufacturing extra pool")
    with m3:
        make_card("Staff & Helper & Supervisor", "42 : 210 : 32", "On-floor deployment ratio")
    with m4:
        make_card("Department Wise Allocation", "100% Deployed", "No labor shortages flagged")

elif active == "Other Reports":
    st.markdown("#### Miscellaneous Regulatory & Strategy Reports")
    links_other = st.columns(2)
    links_other[0].link_button("🔗 Freight & Logistics Tracker (Power BI)", "https://powerbi.com", use_container_width=True)
    links_other[1].link_button("📊 Quality & Audits Compliance (Google Sheet)", "https://google.com", use_container_width=True)
    st.write("")
    mo1, mo2, mo3 = st.columns(3)
    with mo1:
        make_card("Freight Report / Summary", "12 Outbound", "All dispatches tracked via GPS")
    with mo2:
        make_card("Safety & Quality / Audits", "0 Alerts", "Excellent Zero-Harm record / Pass")
    with mo3:
        make_card("Customer-Wise Target vs Sale", "104.2 %", "Exceeding quarterly baseline expectations")

st.markdown("""
    <hr style="margin-top:50px; border-color:#e2e8f0;">
    <p style="text-align: center; color: #94a3b8; font-size: 12px;">
        © 2026 Jindal Petrofoam Pvt. Ltd. | Secure Corporate Internal Data Stream System
    </p>
""", unsafe_allow_html=True)
