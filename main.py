import csv
import datetime
import calendar
import io
import logging
import re
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

log = logging.getLogger("dashboard")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REFRESH_SECONDS = 300
IST = ZoneInfo("Asia/Kolkata")

# ====================================================================
# 1. PAGE CONFIGURATION
# ====================================================================
st.set_page_config(
    page_title="Enterprise Master Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ====================================================================
# 2. CUSTOM CSS  (unchanged look; per-KPI date box removed, date line added)
# ====================================================================
st.markdown(
    """
    <style>
    .block-container { padding-top: 4rem; padding-bottom: 0.8rem; max-width: 100%; }
    div[data-testid="stVerticalBlock"] { gap: 0.35rem; }
    h1, h2, h3, h4 { font-family: 'Segoe UI', Arial, sans-serif; color: #1E3A8A; }

    .header-box {
        background-color: #ffffff; padding: 8px 18px; border-radius: 8px;
        border-bottom: 3px solid #1E3A8A; margin-bottom: 6px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    div[data-testid="stPopover"] > button,
    div[data-testid="stPopover"] button[data-testid="stPopoverButton"],
    a[data-testid="stBaseLinkButton-secondary"] {
        background-color: #1E3A8A !important;
        border: none !important;
        color: #ffffff !important;
        width: 100% !important;
        min-height: 32px !important;
        padding: 4px 12px !important;
        border-radius: 6px !important;
        justify-content: flex-start !important;
    }
    div[data-testid="stPopover"] > button p,
    a[data-testid="stBaseLinkButton-secondary"] p {
        font-weight: 800 !important; font-size: 15px !important; color: #ffffff !important;
    }
    div[data-testid="stPopover"] > button:hover,
    a[data-testid="stBaseLinkButton-secondary"]:hover {
        background-color: #2B4FB5 !important;
    }

    /* ---------- KPI card: bade aur saaf akshar (buzurg workers ke liye) ---------- */
    .kpi-wrap { padding: 2px 2px 10px 2px; }
    .kpi-title { font-size: 15px; font-weight: 800; color: #1E3A8A; letter-spacing: .3px;
                text-transform: uppercase; line-height: 1.2; margin-bottom: 4px; }
    .kpi-value { font-size: 26px; font-weight: 800; color: #0F172A; line-height: 1.15; margin: 4px 0; }
    .kpi-desc  { font-size: 15px; font-weight: 600; line-height: 1.35; margin: 4px 0; }
    .kpi-date  { display: inline-block; font-size: 15px; font-weight: 800; color: #1E3A8A;
                background: #E0E7FF; border-radius: 6px; padding: 2px 10px; line-height: 1.4; }
    .kpi-err   { font-size: 14px; font-weight: 600; line-height: 1.35; color: #dc2626;
                max-height: 6em; overflow: hidden; }
    .kpi-extra { font-size: 14px; font-weight: 700; color: #0F172A; line-height: 1.4; margin-top: 6px; }

    .kpi-extra { font-size: 14px; font-weight: 700; color: #0F172A; line-height: 1.4; margin-top: 6px; }

    /* Cards ki height fix karne aur alignment ke liye */
    /* Saare cards ko equal height dene ke liye */
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] {
        min-height: 350px !important; 
    }
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] {
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }
    /* Card ke andar ka content flexible banayein */
    div[data-testid="stVerticalBlockBorderWrapper"] > div,
    div[data-testid="stVerticalBlock"] {
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }
    /* Expander (View Full Details) ko hamesha sabse niche push karein */
    div[data-testid="stExpander"] {
        margin-top: auto !important;
    }
    /* HTML wale content ko flex-grow dein taaki space le sake */
    .kpi-wrap {
        flex-grow: 1 !important;
    }
    /* metric tiles: bade number + chhota label */
    .kpi-tiles { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 4px 0; }
    .kpi-tile  { flex: 1 1 88px; background: #F1F5F9; border-radius: 10px; padding: 6px 8px;
                text-align: center; border: 1px solid #E2E8F0; }
    .kpi-tile.yield { background: #DCFCE7; border-color: #86EFAC; }
    .kpi-num   { font-size: 24px; font-weight: 800; color: #0F172A; line-height: 1.1; }
    .kpi-tile.yield .kpi-num { color: #15803D; }
    .kpi-lbl   { font-size: 12px; font-weight: 700; color: #475569; text-transform: uppercase;
                line-height: 1.2; margin-top: 2px; }

    /* sections: Selected date / Month / Total */
    .kpi-sec   { margin-top: 8px; padding-top: 6px; border-top: 2px solid #E2E8F0; }
    .kpi-sec-h { font-size: 14px; font-weight: 800; color: #1E3A8A; margin-bottom: 2px; }
    .kpi-row   { display: flex; justify-content: space-between; align-items: baseline; gap: 10px;
                font-size: 15px; line-height: 1.45; padding: 1px 0; }
    .kpi-rl    { color: #334155; font-weight: 600; white-space: nowrap; }
    .kpi-rv    { color: #0F172A; font-weight: 800; text-align: right; }

    /* Dropdowns: bade aur padhne layak */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        min-height: 38px !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        padding-left: 8px !important;
        padding-right: 2px !important;
    }
    div[data-testid="stSelectbox"] {
        width: 100% !important;
        margin-bottom: 0 !important;
    }
    div[data-testid="stSelectbox"] label {
        font-size: 12px !important;
        margin-bottom: 2px !important;
        line-height: 1 !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span { overflow: visible !important; }
    div[data-testid="stDateInput"] { width: 150px !important; margin-bottom: -6px; }
    div[data-testid="stDateInput"] input { font-size: 15px !important; }
    div[data-testid="stExpander"] { margin-top: 2px; }
    div[data-testid="stExpander"] summary { padding: 4px 8px !important; }
    div[data-testid="stExpander"] summary p { font-size: 14px !important; font-weight: 800 !important; color: #1E3A8A; }
    .kpi-wrap { padding-bottom: 4px; }
    /* 4 cards wali line mein dropdowns ko chhota karne ke liye */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        min-height: 32px !important;
        font-size: 13px !important;
        padding-left: 4px !important;
        padding-right: 0px !important;
    }
    div[data-testid="stSelectbox"] label {
        font-size: 11px !important;
    }
    /* Date Input ko chhota karne ke liye */
    div[data-testid="stDateInput"] { 
        width: 100% !important; 
    }
    div[data-testid="stDateInput"] input { 
        font-size: 13px !important; 
    }
        /* =========================================
       PRODUCTION CARDS SPECIFIC FIX (4x2 Grid)
       ========================================= */
    
    /* Har column ke andar ka content flex container ban jaye */
    div[data-testid="column"] > div {
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }

    /* KPI Card ka container poori height le */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }

    /* Card ke andar ka content flex-grow le taaki space bhar sake */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }

    /* Andar ka actual HTML content (kpi-wrap) grow kare */
    .kpi-wrap {
        flex-grow: 1 !important;
        display: flex !important;
        flex-direction: column !important;
    }

    /* Expander (View Full Details) ko sabse niche push karo */
    div[data-testid="stExpander"] {
        margin-top: auto !important;
        margin-bottom: 0px !important;
    }

    /* Production section ke andar ke fonts aur gaps ko ekdum tight karo */
    .kpi-title { font-size: 13px !important; margin-bottom: 2px !important; line-height: 1.1 !important; }
    .kpi-tiles { margin: 4px 0 2px 0 !important; gap: 4px !important; }
    .kpi-tile { padding: 4px 4px !important; }
    .kpi-num { font-size: 18px !important; }
    .kpi-lbl { font-size: 10px !important; margin-top: 0px !important; }
    .kpi-desc { font-size: 12px !important; margin: 2px 0 !important; line-height: 1.2 !important; }
    
    .kpi-sec { margin-top: 4px !important; padding-top: 4px !important; }
    .kpi-sec-h { font-size: 12px !important; margin-bottom: 2px !important; }
    .kpi-row { margin-bottom: 2px !important; padding-bottom: 2px !important; gap: 2px !important; }
    .kpi-rl, .kpi-rv { font-size: 11px !important; }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { min-height: 28px !important; font-size: 11px !important; }
    div[data-testid="stSelectbox"] label { font-size: 10px !important; margin-bottom: 0 !important; }
    div[data-testid="stDateInput"] input { font-size: 11px !important; min-height: 28px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)
# ---------- Cards ki height barabar (department-wise) ----------
st.markdown(
    """
    <style>
    /* marker ko chhupa do (jagah na ghere) */
    div[data-testid="stElementContainer"]:has(span[class^="dept-"]),
    div[data-testid="element-container"]:has(span[class^="dept-"]) { display: none !important; }

    /* PRODUCTION: 4 cards, sab ki height barabar */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.dept-production)
      div[data-testid="stVerticalBlockBorderWrapper"] {
        min-height: 480px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.dept-production)
      div[data-testid="stVerticalBlockBorderWrapper"] > div {
        min-height: inherit !important;   /* View Full Details ko neeche rakhta hai */
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ====================================================================
# 2b. PROFESSIONAL THEME (upar wali CSS ke upar override; purani CSS jyon ki tyon hai)
# ====================================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stApp { font-family: 'Inter', 'Segoe UI', Arial, sans-serif !important; }
    .stApp { background: linear-gradient(180deg, #EEF2F8 0%, #E6ECF5 100%) !important; }
    header[data-testid="stHeader"] { background: transparent !important; }
    .block-container { padding-top: 3.2rem !important; padding-left: 1.6rem !important; padding-right: 1.6rem !important; }

    /* purana simple header chhupa do, naya corporate header neeche hai */
    .header-box { display: none !important; }

    /* ---------- CORPORATE HEADER ---------- */
    .corp-header {
        position: relative; overflow: hidden;
        background: linear-gradient(120deg, #0B1F4B 0%, #14337A 55%, #1E4FB3 100%);
        border-radius: 16px; padding: 18px 26px; margin-bottom: 10px;
        display: flex; align-items: center; justify-content: space-between; gap: 18px; flex-wrap: wrap;
        box-shadow: 0 10px 28px rgba(11,31,75,.28);
        border-bottom: 4px solid #F5B301;
    }
    .corp-header::after {
        content: ""; position: absolute; right: -60px; top: -80px; width: 260px; height: 260px;
        border-radius: 50%; background: radial-gradient(circle, rgba(255,255,255,.14), rgba(255,255,255,0) 70%);
    }
    .corp-left { display: flex; align-items: center; gap: 16px; z-index: 1; }
    .corp-logo {
        width: 56px; height: 56px; border-radius: 14px; flex: 0 0 56px;
        background: linear-gradient(135deg, #F5B301, #FFD65A); color: #0B1F4B;
        display: flex; align-items: center; justify-content: center;
        font-weight: 800; font-size: 22px; letter-spacing: 1px;
        box-shadow: 0 4px 12px rgba(0,0,0,.25);
    }
    .corp-name { color: #ffffff; font-size: 26px; font-weight: 800; letter-spacing: .6px; line-height: 1.15; text-transform: uppercase; }
    .corp-sub  { color: #C7D5F5; font-size: 13px; font-weight: 500; letter-spacing: .4px; margin-top: 3px; }
    .corp-title { color: #F5B301; font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-top: 6px; }
    .corp-right { text-align: right; z-index: 1; }
    .corp-date  { color: #ffffff; font-size: 18px; font-weight: 700; }
    .corp-time  { color: #C7D5F5; font-size: 13px; font-weight: 500; margin-top: 2px; }
    .corp-live  { display: inline-block; margin-top: 6px; background: rgba(34,197,94,.18); color: #86EFAC;
                  border: 1px solid rgba(134,239,172,.5); border-radius: 999px; padding: 2px 12px;
                  font-size: 12px; font-weight: 700; letter-spacing: .5px; }

    /* ---------- DEPARTMENT CARDS (bahar wale container) ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #ffffff !important; border: 1px solid #DCE4F0 !important;
        border-radius: 16px !important; box-shadow: 0 4px 16px rgba(15,23,42,.07) !important;
    }
    /* ---------- KPI CARDS (andar wale container) ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #FBFCFE !important; border: 1px solid #E3E9F3 !important; border-top: 4px solid #1E4FB3 !important;
        border-radius: 12px !important; box-shadow: 0 2px 8px rgba(15,23,42,.06) !important;
        transition: transform .15s ease, box-shadow .15s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px); box-shadow: 0 8px 20px rgba(30,79,179,.18) !important;
    }

    /* ---------- DEPARTMENT BUTTON ---------- */
    div[data-testid="stPopover"] > button,
    div[data-testid="stPopover"] button[data-testid="stPopoverButton"],
    a[data-testid="stBaseLinkButton-secondary"] {
        background: linear-gradient(90deg, #0B1F4B, #1E4FB3) !important;
        border-radius: 10px !important; min-height: 38px !important;
        box-shadow: 0 3px 8px rgba(11,31,75,.25) !important;
    }
    div[data-testid="stPopover"] > button p { letter-spacing: .8px !important; font-size: 15px !important; }
    div[data-testid="stPopover"] > button:hover,
    a[data-testid="stBaseLinkButton-secondary"]:hover { background: linear-gradient(90deg, #14337A, #2B63D6) !important; }

    /* ---------- KPI TEXT ---------- */
    .kpi-title { color: #0B1F4B !important; font-size: 14px !important; letter-spacing: .8px !important; }
    .kpi-value { color: #0B1F4B !important; font-size: 28px !important; }
    .kpi-date  { background: linear-gradient(90deg, #E0E7FF, #EEF2FF) !important; border: 1px solid #C7D2FE; color: #1E3A8A !important; }
    .kpi-tile  { background: linear-gradient(180deg, #F8FAFD, #EEF2F9) !important; border: 1px solid #DCE4F0 !important;
                 border-radius: 12px !important; box-shadow: inset 0 1px 0 #fff; }
    .kpi-tile.yield { background: linear-gradient(180deg, #ECFDF3, #D1FAE5) !important; border-color: #6EE7B7 !important; }
    .kpi-sec   { border-top: 1px dashed #CBD5E1 !important; }
    .kpi-rv    { color: #0B1F4B !important; }

    /* ---------- DROPDOWNS / EXPANDER / BUTTONS ---------- */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        border-radius: 8px !important; background: #F1F5FB !important; border: 1px solid #D5DEEC !important;
    }
    div[data-testid="stExpander"] { border: 1px solid #DCE4F0 !important; border-radius: 10px !important; background: #F8FAFD; }
    button[kind="secondary"] { border-radius: 10px !important; border: 1px solid #C7D2E8 !important; font-weight: 700 !important; }

    button[kind="secondary"] { border-radius: 10px !important; border: 1px solid #C7D2E8 !important; font-weight: 700 !important; }

    /* ---------- YIELD TILE: har KPI block mein sabse pehle (first position) ---------- */
    .kpi-tiles .kpi-tile.yield { order: -1; }

    /* ---------- FOOTER ---------- */
    .corp-footer { text-align: center; color: #64748B; font-size: 12px; font-weight: 500; padding: 14px 0 4px 0; letter-spacing: .4px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ====================================================================
# 3. HEADER
# ====================================================================
st.markdown(
    """
    <div class="header-box">
        <h1 style="margin:0; font-size:1.6rem; font-weight:800;">Enterprise Master Dashboard</h1>
        <p style="margin:2px 0 0 0; color:#475569; font-size:0.8rem; font-weight:500;">
            Centralized Management Control • Jindal Petrofoam Pvt. Ltd. • JTM Execution
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

_now_hdr = datetime.datetime.now(IST)
st.markdown(
    f"""
    <div class="corp-header">
        <div class="corp-left">
            <div class="corp-logo">JP</div>
            <div>
                <div class="corp-name">Jindal Petrofoam Private Limited</div>
                <div class="corp-sub">Centralized Management Control &nbsp;•&nbsp; JTM Execution</div>
                <div class="corp-title">Enterprise Master Dashboard</div>
            </div>
        </div>
        <div class="corp-right">
            <div class="corp-date">{_now_hdr:%A, %d %B %Y}</div>
            <div class="corp-time">{_now_hdr:%I:%M %p} IST</div>
            <div class="corp-live">● LIVE DATA</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
# ====================================================================
# ====================================================================
# 3.1 GLOBAL DATE & MONTH SELECTOR (Professional Control Panel)
# ====================================================================
import datetime
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")

if "global_date" not in st.session_state:
    st.session_state.global_date = datetime.datetime.now(IST).date()
if "global_month" not in st.session_state:
    st.session_state.global_month = (datetime.datetime.now(IST).year, datetime.datetime.now(IST).month)

# CSS for Global Control Panel
st.markdown(
    """
    <style>
    .global-panel {
        background: linear-gradient(90deg, #F8FAFC, #EEF2F9);
        border: 1px solid #DCE4F0;
        border-left: 6px solid #1E4FB3;
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 12px rgba(15,23,42,.05);
    }
    .global-panel-title {
        font-size: 14px; font-weight: 800; color: #0B1F4B; text-transform: uppercase; letter-spacing: 1px;
    }
    .global-panel-sub {
        font-size: 12px; color: #64748B; font-weight: 500; margin-top: 2px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<div class="global-panel"><div><div class="global-panel-title">🌍 Global Dashboard Controls</div><div class="global-panel-sub">Change date/month here to update all KPIs at once. (Individual cards have their own controls below).</div></div></div>', unsafe_allow_html=True)

gcol1, gcol2, _ = st.columns([2, 2, 4], gap="medium")

with gcol1:
    # Date Input mein "key" nahi daalenge warna Streamlit purani value pakad leta hai
    new_date = st.date_input("📅 Global Date", st.session_state.global_date, format="DD/MM/YYYY")

with gcol2:
    current_yr = datetime.datetime.now(IST).year
    month_options = []
    for y in [current_yr, current_yr - 1]:
        for m in range(1, 13):
            month_options.append((y, m))
    month_options = sorted(month_options, reverse=True)
    try:
        default_idx = month_options.index(st.session_state.global_month)
    except ValueError:
        default_idx = 0
    
    # Month Input mein bhi "key" nahi daalenge
    new_month = st.selectbox(
        "🗓 Global Month", 
        month_options, 
        index=default_idx,
        format_func=lambda x: datetime.date(x[0], x[1], 1).strftime("%b-%Y"),
    )

# Logic: Agar Month change hua hai, toh Date ko us month ki 1st date par set karo
if new_month != st.session_state.global_month:
    st.session_state.global_month = new_month
    # Naya month change hua -> Date ko us month ki 1st date (ya aaj ki date) par set karo
    st.session_state.global_date = datetime.date(new_month[0], new_month[1], 1)
    st.rerun()

# Logic: Agar Date change hui hai
if new_date != st.session_state.global_date:
    st.session_state.global_date = new_date
    # Agar user ne aisi date chuni hai jo current month mein nahi hai, toh month ko auto-update kar do
    if (new_date.year, new_date.month) != st.session_state.global_month:
        st.session_state.global_month = (new_date.year, new_date.month)
    st.rerun()

if new_month != st.session_state.global_month:
    st.session_state.global_month = new_month
    st.rerun()


# ====================================================================
# DATA ENGINE
# ====================================================================
class DataError(Exception):
    """A problem with the data itself (missing column, bad sheet ...)."""


def sheet_id(url):
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url or "")
    if not m:
        raise ValueError("This is not a Google Sheets link (expected .../spreadsheets/d/<ID>/...)")
    return m.group(1)


def _frame_from_rows(rows, header_hint=None):
    """Rows -> DataFrame of text. Header row = first row containing `header_hint`."""
    rows = [list(r) for r in rows]
    if not rows:
        return pd.DataFrame()
    start = 0
    if header_hint:
        want = str(header_hint).strip().lower()
        found = False
        for i, row in enumerate(rows):
            if any(str(c).strip().lower() == want for c in row):
                start, found = i, True
                break
        if not found:
            first = [str(c).strip() for c in rows[0]]
            raise DataError(
                f"Header '{header_hint}' not found in the sheet. First row is: {first}. "
                f"Check 'date_col' in SHEETS and the tab (worksheet/gid)."
            )
    cols, seen = [], {}
    for j, h in enumerate(rows[start]):
        name = str(h).strip() or f"col_{j + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        cols.append(name)
    n = len(cols)
    body = [(r + [""] * (n - len(r)))[:n] for r in rows[start + 1:]]
    return pd.DataFrame(body, columns=cols)


def _frame_from_csv(data, header_hint=None):
    text = data.decode("utf-8-sig", errors="replace")
    return _frame_from_rows(list(csv.reader(io.StringIO(text))), header_hint)


def _http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def _fetch_published(url, gid=None, header_hint=None):
    """'Publish to web' link (.../spreadsheets/d/e/2PACX-.../pubhtml). gid = tab number."""
    base = url.split("/pub")[0]
    csv_url = f"{base}/pub?output=csv" + (f"&gid={gid}" if gid not in (None, "") else "")
    data = _http_get(csv_url)
    if data.lstrip()[:1] == b"<":
        raise PermissionError(
            "Google did not return data. Publish the tab to the web as CSV/web page, "
            "and check the gid (the number after #gid= in the sheet address)."
        )
    return _frame_from_csv(data, header_hint)


def fetch_sheet(url, worksheet=None, service_account=None, header_hint=None):
    if "/spreadsheets/d/e/" in (url or ""):
        return _fetch_published(url, worksheet, header_hint)
    sid = sheet_id(url)

    if service_account:
        import gspread  # only needed for private sheets

        gc = gspread.service_account_from_dict(dict(service_account))
        sh = gc.open_by_key(sid)
        try:
            ws = sh.worksheet(worksheet) if worksheet else sh.sheet1
        except gspread.WorksheetNotFound:
            names = [w.title for w in sh.worksheets()]
            raise DataError(f"Worksheet '{worksheet}' not found. Tabs in this file: {names}")
        return _frame_from_rows(ws.get_all_values(), header_hint)

    query = {"tqx": "out:csv"}
    if worksheet:
        query["sheet"] = worksheet
    csv_url = f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?{urllib.parse.urlencode(query)}"
    data = _http_get(csv_url)
    if data.lstrip()[:1] == b"<":
        raise PermissionError(
            "Google returned a login page: the sheet is private. Share it as "
            "'Anyone with the link - Viewer', or add a service account in secrets."
        )
    return _frame_from_csv(data, header_hint)


# --------------------------------------------------------------------
# Preparing and computing KPI values
# --------------------------------------------------------------------
def _parse_dates(series, dayfirst):
    """Text -> datetime (unreadable -> NaT)."""
    if int(pd.__version__.split(".")[0]) >= 2:
        parsed = pd.to_datetime(series, dayfirst=dayfirst, errors="coerce", format="mixed")
    else:
        parsed = pd.to_datetime(series, dayfirst=dayfirst, errors="coerce")

    # Jahan normal parse fail ho gaya (NaT) aur text "Apr-25" type ka hai, use handle karo
    mask = parsed.isna() & series.notna()
    if mask.any():
        def _fix_month(m):
            try:
                month_str = str(m).split('-')[0].strip()
                year_str = str(m).split('-')[1].strip()
                year = f"20{year_str}" if len(year_str) == 2 else year_str
                return pd.to_datetime(f"01-{month_str}-{year}", format="%d-%b-%Y", errors="coerce")
            except:
                return pd.NaT

        fixed_dates = series[mask].apply(_fix_month)
        parsed.loc[mask] = fixed_dates

    return parsed


def prepare(df, date_col, dayfirst=True, ffill_cols=(), anchor=None, extra_date_cols=(), ignore_cols=()):
    """Clean the sheet and add `_date` (+ `_d_<col>` for extra date columns).

    Sheets where one record spans several rows (a PO line, then one row per
    invoice with the PO cells left blank) are handled with `anchor` + `ffill_cols`:
    every row with a value in `anchor` starts a new record (`_grp`), and the
    record's header cells are copied down onto its continuation rows.
    """
    if df.empty:
        raise DataError("The sheet returned no rows (empty response).")
    if date_col not in df.columns:
        raise DataError(f"date column '{date_col}' not found. Sheet columns: {list(df.columns)}")
    out = df.copy()

    # drop completely blank rows (ignoring dropdown-only columns such as Status)
    check = [c for c in out.columns if c not in set(ignore_cols)]
    filled = out[check].astype(str).apply(lambda s: s.str.strip()).ne("")
    out = out[filled.any(axis=1)].copy()

    if ffill_cols:
        need = list(ffill_cols) + ([anchor] if anchor else [])
        miss = [c for c in need if c not in out.columns]
        if miss:
            raise DataError(f"columns {miss} not found. Sheet columns: {list(df.columns)}")
        is_head = out[anchor].astype(str).str.strip().ne("")
        out["_grp"] = is_head.cumsum()
        out["_is_head"] = is_head
        out = out[out["_grp"] > 0].copy()
        for c in ffill_cols:
            s = out[c].astype(str).str.strip().replace("", pd.NA)
            out[c] = s.groupby(out["_grp"]).ffill().fillna("")

    parsed = _parse_dates(out[date_col], dayfirst)
    non_blank = out[date_col].astype(str).str.strip() != ""
    bad = int((parsed.isna() & non_blank).sum())
    if bad:
        log.warning("%d rows have an unreadable '%s' value and were skipped", bad, date_col)
    out["_date"] = parsed.dt.date
    for c in extra_date_cols:
        if c not in out.columns:
            raise DataError(f"extra date column '{c}' not found. Sheet columns: {list(df.columns)}")
        out["_d_" + c] = _parse_dates(out[c], dayfirst).dt.date
    if out["_date"].isna().all():
        hdr_dates = _parse_dates(pd.Series(list(out.columns)), dayfirst=True).dropna()
        out["_date"] = hdr_dates.iloc[-1].date() if not hdr_dates.empty else datetime.datetime.now(IST).date()
    else:
        out = out.dropna(subset=["_date"])
    out = out.sort_values(["_date"] + (["_grp"] if "_grp" in out.columns else []), kind="stable")
    out.attrs["bad_dates"] = bad
    return out


def available_dates(df):
    """Every real date in the source (PO dates and receipt dates), newest first."""
    cols = ["_date"] + [c for c in df.columns if str(c).startswith("_d_")]
    found = set()
    for c in cols:
        found.update(d for d in df[c].dropna().unique() if isinstance(d, datetime.date))
    return sorted(found, reverse=True)


def _num(series):
    """Text -> numbers. Strips currency, commas, units; blanks/text become NaN."""
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)", expand=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _need(df, col):
    if col not in df.columns:
        raise DataError(f"column '{col}' not found. Sheet columns: {[c for c in df.columns if c != '_date']}")


def compute(df, spec, day):
    """Generic KPI (count/sum/...) for `day`; None when the sheet has no data for that day."""
    sub = df[df["_date"] <= day] if spec.get("mode", "on_date") == "as_of" else df[df["_date"] == day]
    if sub.empty:
        return None

    values = []
    for part in spec["parts"]:
        rows = sub
        for col, wanted in part.get("where", {}).items():
            _need(rows, col)
            rows = rows[rows[col].astype(str).str.strip().str.lower() == str(wanted).strip().lower()]
        agg = part["agg"]
        if agg == "count":
            values.append(len(rows))
            continue
        _need(rows, part["col"])
        col = rows[part["col"]]
        filled = col.astype(str).str.strip()
        filled = filled[filled != ""]
        if agg == "nunique":
            values.append(filled.nunique())
        elif agg == "last":
            values.append(filled.iloc[-1] if len(filled) else None)
        elif agg in ("sum", "mean", "min", "max"):
            values.append(getattr(_num(col), agg)())
        else:
            raise DataError(f"unknown agg '{agg}'")

    if any(v is None or (isinstance(v, float) and v != v) for v in values):
        return None
    return spec.get("fmt", "{0}").format(*values)


# ====================================================================
# PURCHASE ORDER CALCULATIONS  (sheet "PO STATUS_v2" / tab "Consolidated")
# ====================================================================
PO_COLUMNS = {
    "po_no": ["PO #", "PO No", "PO No.", "PO Number", "PO"],
    "item": ["Item Description", "Item Code", "Item", "Item Name", "Material", "Material Code"],
    "uom": ["UoM", "UOM", "Unit"],
    "po_qty": ["PO Qty", "PO Quantity", "Order Qty", "Ordered Qty", "Order Quantity"],
    "po_rate": ["PO Rate", "Rate"],
    "received_qty": ["Inv Qty", "Received Qty", "Received Quantity", "GRN Qty", "Receipt Qty", "Rcvd Qty"],
    "inv_rate": ["Invoice Rate", "Inv Rate"],
    "receipt_no": ["Invoice #", "Invoice No", "Invoice No.", "Invoice Number", "GRN No", "GRN #", "Challan No"],
    "receipt_date": ["Recd Date", "Invoice Date", "Received Date", "Receipt Date", "GRN Date"],
    "status": ["Status"],
    "sheet_balance": ["Balance Qty", "Pending Qty", "Balance Quantity", "Pending Quantity"],
}
PO_REQUIRED = ("po_no", "item", "po_qty", "received_qty")
PO_EXCLUDE_STATUS = ["cancelled", "canceled", "short closed", "deleted"]
MIXED_RATE_RATIO = 20     # same item with rates differing > 20x => probably mixed currencies


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _fuzzy_pick(cols, role):
    """Find a column for `role` by keywords when no exact header matches."""
    for c in cols:
        toks = _norm(c).split()
        t = set(toks)
        qty = bool(t & {"qty", "quantity"})
        if role == "po_no" and "po" in t and t & {"no", "number", "num"}:
            return c
        if role == "item" and "item" in t and "date" not in t and not qty:
            return c
        if role == "po_qty" and qty and t & {"po", "order", "ordered"} \
                and not t & {"pending", "balance", "received", "recd", "rcvd", "grn", "invoice", "inv"}:
            return c
        if role == "received_qty" and qty and t & {"received", "recd", "rcvd", "grn", "receipt"} \
                and not t & {"pending", "balance"}:
            return c
        if role == "receipt_date" and "date" in t and t & {"received", "recd", "rcvd", "grn", "receipt"}:
            return c
        if role == "sheet_balance" and qty and t & {"pending", "balance"}:
            return c
    return None


def _resolve_columns(df, overrides=None):
    cols = [c for c in df.columns if not str(c).startswith("_")]
    lower = {c.strip().lower(): c for c in cols}
    found = {}
    for key, header in (overrides or {}).items():
        if header.strip().lower() not in lower:
            raise DataError(f"columns override {key}='{header}' not found. Sheet columns: {cols}")
        found[key] = lower[header.strip().lower()]
    for key, candidates in PO_COLUMNS.items():
        if key in found:
            continue
        for cand in candidates:
            if cand.strip().lower() in lower:
                found[key] = lower[cand.strip().lower()]
                break
        else:
            pick = _fuzzy_pick(cols, key)
            if pick:
                found[key] = pick
    missing = [k for k in PO_REQUIRED if k not in found]
    if missing:
        raise DataError(
            "PO calculation cannot find column(s): " + ", ".join(missing)
            + f". Sheet columns are: {cols}. Fix: add \"columns\": {{\"po_no\": \"...\", \"item\": \"...\", "
            "\"po_qty\": \"...\", \"received_qty\": \"...\"}} (exact header text) to the KPI in KPI_SOURCES."
        )
    if "received_qty" not in (overrides or {}):
        if set(_norm(found["received_qty"]).split()) & {"inv", "invoice"} and "receipt_date" not in found:
            raise DataError(
                f"'{found['received_qty']}' is an invoice quantity and no receipt-date column (e.g. 'Recd Date') "
                f"was found, so received stock cannot be told apart from billed stock. Sheet columns: {cols}."
            )
    return found


def _receipt_dates(w, c):
    if "receipt_date" not in c:
        return None
    col = "_d_" + c["receipt_date"]
    if col in w.columns:
        return w[col]
    return _parse_dates(w[c["receipt_date"]], False).dt.date


def _is_date(d, test):
    return d is not None and pd.notna(d) and test(d)


def _po_rows(df, c, issues):
    """Numbers parsed, cancelled PO lines removed, duplicate invoice rows neutralised."""
    w = df.copy()
    if "_grp" not in w.columns:
        w["_grp"] = range(len(w))
    if "_is_head" not in w.columns:
        w["_is_head"] = True
    if "status" in c:
        txt = w[c["status"]].astype(str).str.strip().str.lower()
        cancelled = set(w.loc[txt.isin(PO_EXCLUDE_STATUS), "_grp"])
        if cancelled:
            issues.append(f"{len(cancelled)} PO lines excluded (status in {PO_EXCLUDE_STATUS})")
            w = w[~w["_grp"].isin(cancelled)].copy()
    w["_po_qty"] = _num(w[c["po_qty"]])
    w["_inv"] = _num(w[c["received_qty"]])
    for key in ("po_qty", "received_qty"):
        raw = w[c[key]].astype(str).str.strip()
        txt = int(((raw != "") & _num(w[c[key]]).isna()).sum())
        if txt:
            issues.append(f"{txt} cells in '{c[key]}' are not numbers (ignored)")
    neg = w["_inv"] < 0
    if neg.any():
        issues.append(f"{int(neg.sum())} rows with a negative '{c['received_qty']}' ignored")
    has_inv = w["_inv"].notna() & (w["_inv"] > 0)
    key = ["_grp", c["received_qty"]] + [c[k] for k in ("receipt_no", "receipt_date") if k in c]
    dup = has_inv & w.duplicated(subset=key)
    if dup.any():
        issues.append(f"{int(dup.sum())} duplicate invoice rows ignored (same line, invoice, qty and date)")
    w["_inv"] = w["_inv"].where(has_inv & ~dup, 0.0)
    return w


def po_pending(df, day, overrides=None, only_day=False):
    issues = []
    try:
        c = _resolve_columns(df, overrides)
    except Exception as e:
        return {"open_pos": 0, "open_lines": 0, "qty_by_uom": {}, "table": pd.DataFrame(), "issues": [str(e)], "formula": "", "columns": {}, "recon": {"checked": 0, "mismatch": pd.DataFrame()}}
    
    # only_day hata diya, ab selected date tak ke saare PO uthayega
    w = df[df["_date"] <= day]
    if w.empty:
        return None
        
    w = _po_rows(w, c, issues)

    rd = _receipt_dates(w, c)
    if rd is not None:
        by_day = rd.apply(lambda d: _is_date(d, lambda x: x <= day)).astype(bool)
        undated = ((w["_inv"] > 0) & ~rd.apply(lambda d: _is_date(d, lambda x: True)).astype(bool))
        if undated.any():
            issues.append(f"{int(undated.sum())} invoice rows have a quantity but no valid {c['receipt_date']}: counted as NOT yet received")
        w["_rec_asof"] = w["_inv"].where(by_day, 0.0)
    else:
        w["_rec_asof"] = w["_inv"]

    if "sheet_balance" in c:
        w["_sb"] = _num(w[c["sheet_balance"]])
        raw = w[c["sheet_balance"]].astype(str).str.strip()
        txt = int(((raw != "") & w["_sb"].isna()).sum())
        if txt:
            issues.append(f"{txt} '{c['sheet_balance']}' cells contain text notes (ignored)")
    else:
        w["_sb"] = float("nan")

    agg = {c["po_no"]: "first", c["item"]: "first", "_po_qty": "first",
        "_rec_asof": "sum", "_inv": "sum", "_sb": "first"}
    if "uom" in c:
        agg[c["uom"]] = "first"
    g = w.groupby("_grp", sort=False).agg(agg).reset_index(drop=True)
    g = g.rename(columns={c["po_no"]: "PO", c["item"]: "Item", "_po_qty": "po_qty",
                        "_rec_asof": "received", "_inv": "received_all", "_sb": "sheet_balance"})
    g["UoM"] = g[c["uom"]].astype(str).str.strip() if "uom" in c else ""

    bad = g["po_qty"].isna() | (g["po_qty"] < 0)
    if bad.any():
        issues.append(f"{int(bad.sum())} PO lines skipped: PO qty blank, text or negative")
        g = g[~bad].copy()
        
    g["pending_raw"] = g["po_qty"] - g["received"]
    over = g["pending_raw"] < 0
    if over.any():
        issues.append(f"{int(over.sum())} PO lines are over-received (pending shown as 0)")
    g["pending"] = g["pending_raw"].clip(lower=0)

    calc_all = g["po_qty"] - g["received_all"]
    checked = g["sheet_balance"].notna()
    diff = (calc_all - g["sheet_balance"]).abs()
    mism = g[checked & (diff > 1.0)].assign(calc_balance=calc_all, diff=diff)[
        ["PO", "Item", "po_qty", "received_all", "calc_balance", "sheet_balance", "diff"]]
    recon = {"checked": int(checked.sum()), "mismatch": mism}

    open_ = g[g["pending"] > 0]
    by_uom = open_.groupby("UoM")["pending"].sum().sort_values(ascending=False)
    
    formula = (
        "Per PO line (a PO # row plus the invoice rows under it): pending = PO Qty - sum of "
        f"'{c['received_qty']}' on invoices received on/before the selected date "
        f"({'by ' + c['receipt_date'] if rd is not None else 'all invoices'}; duplicate rows ignored), "
        "floored at 0. Only PO lines dated on/before the selected date. Open POs = distinct PO # with pending > 0. "
        "Quantities are totalled per UoM (never across PCS / KGS / MTR)."
    )
    return {
        "open_pos": int(open_["PO"].nunique()),
        "open_lines": int(len(open_)),
        "qty_by_uom": {k: float(v) for k, v in by_uom.items()},
        "table": g[["PO", "Item", "UoM", "po_qty", "received", "pending", "sheet_balance"]],
        "issues": issues, "formula": formula, "columns": c, "recon": recon,
    }


def _mixed_rate_items(df, item_col, rate_cols):
    """Items whose PO / invoice rates differ by more than MIXED_RATE_RATIO x anywhere in the sheet."""
    item = df[item_col].astype(str).str.strip().str.upper()
    parts = [pd.DataFrame({"item": item, "rate": _num(df[rc])}) for rc in rate_cols]
    t = pd.concat(parts).dropna()
    t = t[(t["rate"] > 0) & (t["item"] != "")]
    s = t.groupby("item")["rate"].agg(["min", "max"])
    return set(s.index[(s["max"] / s["min"]) > MIXED_RATE_RATIO])


def purchase_mtd(df, day, overrides=None, basis="received", all_time=False):
    issues = []
    c = _resolve_columns(df, overrides)
    if all_time:
        start, day = datetime.date(2000, 1, 1), datetime.date.max
    else:
        start = day.replace(day=1)
    if basis == "received":
        for k in ("inv_rate", "receipt_date"):
            if k not in c:
                raise DataError(f"basis 'received' needs a '{k}' column; Sheet columns: "
                                f"{[x for x in df.columns if not str(x).startswith('_')]}")
        w = _po_rows(df, c, issues)
        rd = _receipt_dates(w, c)
        win = rd.apply(lambda d: _is_date(d, lambda x: start <= x <= day)).astype(bool)
        rows = w[win & (w["_inv"] > 0)].copy()
        qty, rate_col = rows["_inv"], c["inv_rate"]
    elif basis == "po":
        if "po_rate" not in c:
            raise DataError("basis 'po' needs a PO Rate column")
        w = _po_rows(df[(df["_date"] >= start) & (df["_date"] <= day)], c, issues)
        rows = w[w["_is_head"]].copy()
        qty, rate_col = rows["_po_qty"], c["po_rate"]
    else:
        raise DataError(f"unknown basis '{basis}' (use 'received' or 'po')")
    if rows.empty:
        return None
    rate = _num(rows[rate_col])
    bad = rate.isna() | qty.isna()
    if bad.any():
        issues.append(f"{int(bad.sum())} rows skipped: quantity or rate blank / text")
    rows, rate, qty = rows[~bad], rate[~bad], qty[~bad]
    if rows.empty:
        return None
    flagged = _mixed_rate_items(df, c["item"], [c[k] for k in ("po_rate", "inv_rate") if k in c])
    used = set(rows[c["item"]].astype(str).str.strip().str.upper())
    
    # NAYA LOGIC: Bill Amount ka sum calculate karein (day-wise aur month-wise)
    bill_amt_sum = 0
    if "Bill Amount" in rows.columns:
        bill_amt_sum = _num(rows["Bill Amount"]).sum()
    elif "Bill Amount" in c:
        bill_amt_sum = _num(rows[c["Bill Amount"]]).sum()

    table = pd.DataFrame({"PO": rows[c["po_no"]], "Item": rows[c["item"]], "Qty": qty,
                        "Rate": rate, "Value": qty * rate})
    
    formula = (
        f"Sum of ({'Inv Qty x Invoice Rate for invoices with ' + c['receipt_date'] if basis == 'received' else 'PO Qty x PO Rate for PO lines with PO Date'}"
        f") between {start:%d-%m-%Y} and {day:%d-%m-%Y}; duplicate invoice rows ignored. "
        "Amounts are in the sheet's own rate currency (no conversion applied)."
    )
    
    # Return dictionary mein bill_amt_sum add kar dein
    return {"value": float((qty * rate).sum()), "bill_amt": float(bill_amt_sum), "warn_items": sorted(flagged & used), 
            "table": table, "issues": issues, "formula": formula, "columns": c}
# ====================================================================
# PENDING PO AGEING (0-15 / 15-30 / 30-60 / 60+ days)  -- NAYA BLOCK
# ====================================================================
PO_AGE_BUCKETS = {
    "po_age_0_15":    ("0-15 Days", 0, 15),
    "po_age_15_30":   ("15-30 Days", 15, 30),
    "po_age_30_60":   ("30-60 Days", 30, 60),
    "po_age_60_plus": ("60+ Days", 60, None),
}


def po_ageing(df, day, overrides=None):
    """Har PO line ka pending aur uski age (day - PO date). Pending > 0 wali lines hi wapas aati hain."""
    issues = []
    try:
        c = _resolve_columns(df, overrides)
    except Exception as e:
        return None, [str(e)]
    w = df[df["_date"] <= day]
    if w.empty:
        return None
    w = _po_rows(w, c, issues)
    rd = _receipt_dates(w, c)
    if rd is not None:
        by_day = rd.apply(lambda d: _is_date(d, lambda x: x <= day)).astype(bool)
        w["_rec_asof"] = w["_inv"].where(by_day, 0.0)
    else:
        w["_rec_asof"] = w["_inv"]

    pick = lambda name: next((x for x in w.columns if str(x).strip().lower() == name), None)
    sup, cat = pick("supplier name"), pick("category")
    agg = {c["po_no"]: "first", c["item"]: "first", "_po_qty": "first", "_rec_asof": "sum", "_date": "first"}
    if "uom" in c:
        agg[c["uom"]] = "first"
    if sup:
        agg[sup] = "first"
    if cat:
        agg[cat] = "first"
    g = w.groupby("_grp", sort=False).agg(agg).reset_index(drop=True)
    g = g.rename(columns={c["po_no"]: "PO", c["item"]: "Item", "_po_qty": "po_qty",
                          "_rec_asof": "received", "_date": "po_date"})
    g["UoM"] = g[c["uom"]].astype(str).str.strip() if "uom" in c else ""
    g["Supplier"] = g[sup].astype(str).str.strip() if sup else ""
    g["Category"] = g[cat].astype(str).str.strip() if cat else ""
    g = g[g["po_qty"].notna() & (g["po_qty"] >= 0)].copy()
    g["pending"] = (g["po_qty"] - g["received"]).clip(lower=0)
    g = g[g["pending"] > 0].copy()
    g["age"] = g["po_date"].apply(lambda d: (day - d).days)
    return g, issues


def po_ageing_card(df, spec, day):
    import html as _html
    r = po_ageing(df, day, spec.get("columns"))
    if r is None:
        return {"value": "0 POs", "desc": "No PO on or before this date", "color": GREY}
    g, issues = r
    if g is None or g.empty:
        return {"value": "0 POs", "desc": f"Error: {issues[0] if issues else 'No data'}", "color": RED}
    label, lo, hi = PO_AGE_BUCKETS[spec["calc"]]

    def pick_bucket(lo_, hi_):
        m = (g["age"] >= lo_) if lo_ == 0 else (g["age"] > lo_)
        if hi_ is not None:
            m = m & (g["age"] <= hi_)
        return g[m]

    b = pick_bucket(lo, hi).sort_values("age", ascending=False)
    n_pos = int(b["PO"].nunique())
    by_uom = b.groupby("UoM")["pending"].sum().sort_values(ascending=False)
    uom_txt = " · ".join(f"{k or 'units'}: {v:,.0f}" for k, v in by_uom.items()) or "No pending"

    counts = [int(pick_bucket(l, h)["PO"].nunique()) for _, l, h in PO_AGE_BUCKETS.values()]
    total_open = int(g["PO"].nunique())
    extra = (f"0-15: {counts[0]} + 15-30: {counts[1]} + 30-60: {counts[2]} + 60+: {counts[3]} "
             f"= {sum(counts)} (total open POs: {total_open})")

    esc = lambda x: _html.escape(str(x))
    details = []
    if not b.empty:
        details.append((f"📋 {label} · {n_pos} POs / {len(b)} lines", [
            (f"PO {esc(r_.PO)} ({r_.po_date.strftime('%d-%m-%Y')})",
             f"{esc(r_.Supplier[:22])} · {esc(r_.Item[:24])} · {r_.pending:,.0f} {esc(r_.UoM)} · {r_.age}d")
            for r_ in b.itertuples()]))
        sw = b.groupby("Supplier")["PO"].nunique().sort_values(ascending=False)
        details.append(("🏭 Supplier wise", [(esc(s[:26]), f"{n} POs") for s, n in sw.items() if s]))
        cw = b.groupby("Category")["PO"].nunique().sort_values(ascending=False)
        details.append(("🗂 Category wise", [(esc(k), f"{n} POs") for k, n in cw.items() if k]))
    return {
        "value": f"{n_pos} POs",
        "desc": uom_txt,
        "color": RED if (lo >= 60 and n_pos) else BLUE,
        "details": details,
    }


def _inr(x):
    """12345678 -> ₹1,23,45,678"""
    n = int(round(x))
    s = str(abs(n))
    if len(s) > 3:
        head, tail, parts = s[:-3], s[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + "₹" + s

def _inr_cr(x):
    """Rupees ko Crores mein convert karta hai (e.g. 2344259 -> ₹0.23 Cr)"""
    crores = x / 10000000
    return f"₹{crores:,.2f} Cr"

PROD_TYPES = {
    "total":    {"col": None,   "words": [],                        "qty": "SHEET", "unit": "Sheets"},
    "bdls":     {"col": "ITEM", "words": ["BONDED"],                "qty": "SHEET", "unit": "Sheets"},
    "rolls":    {"col": "ITEM", "words": ["ROLL"], "not": ["ROLLPACK", "ROLL PACK"], "qty": "MTR", "unit": "Mtr"},
    "mattress": {"col": "ITEM", "words": ["MATTRESS"],              "qty": "SHEET", "unit": "Pcs"},
    "pillow":   {"col": "ITEM", "words": ["PILLOW"],                "qty": "SHEET", "unit": "Pcs", "is_pcs": True},
    "rollpack": {"col": "ITEM", "words": ["ROLLPACK", "ROLL PACK", "ROLL P"], "qty": "SHEET", "unit": "Pcs", "is_pcs": True},
}


def _direct_url(url):
    import base64
    if "1drv.ms" in url or "onedrive.live.com" in url:
        b = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
        return f"https://api.onedrive.com/v1.0/shares/u!{b}/root/content"
    if "sharepoint.com" in url:
        return url + ("&" if "?" in url else "?") + "download=1"
    return url


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_excel_cached(url, sheet_name, date_col, dayfirst, static=False):
    if re.match(r"^https?://", url or ""):
        data = _http_get(_direct_url(url))
        src = io.BytesIO(data)
    else:
        src = url
    file_ext = str(url).split('?')[0].split('.')[-1].lower()
    eng = "xlrd" if file_ext == "xls" else "openpyxl"
    raw = pd.read_excel(src, sheet_name=sheet_name, header=None, dtype=object, engine=eng)
    # Agar date_col khali hai, toh header_hint mat do
    df = _frame_from_rows(raw.fillna("").values.tolist(), header_hint=date_col if date_col else None)
    if static:
        df["_date"] = datetime.datetime.now(IST).date()
        return df, datetime.datetime.now(IST)
    # Agar date_col nahi diya, toh aaj ki date de do
    if not date_col:
        df["_date"] = datetime.datetime.now(IST).date()
        return df, datetime.datetime.now(IST)
    def _to_date(v):
        if isinstance(v, (datetime.datetime, pd.Timestamp)):
            return v.date()
        if isinstance(v, datetime.date):
            return v
        d = _parse_dates(pd.Series([str(v)]), dayfirst).iloc[0]
        return d.date() if pd.notna(d) else None
    df["_date"] = df[date_col].apply(_to_date)
    df = df.dropna(subset=["_date"]).copy()
    if df.empty:
        raise DataError(f"'{date_col}' column has no valid date")
    return df, datetime.datetime.now(IST)


def _pcol(df, name):
    import re
    # Sirf letters aur numbers rakho
    want = re.sub(r"[^A-Z0-9]", "", name.upper())
    cols = [(c, re.sub(r"[^A-Z0-9]", "", str(c).upper())) for c in df.columns]

    # Exact match (SHEET -> SHEET)
    for c, n in cols:
        if n == want:
            return df[c]

    # Startswith match (SHEET ✓ -> SHEET)
    for c, n in cols:
        if n.startswith(want) and not str(c).startswith("_"):
            return df[c]

    # Endswith match
    for c, n in cols:
        if n.endswith(want) and not str(c).startswith("_"):
            return df[c]

    raise DataError(f"Column '{name}' not found. Columns: {[c for c in df.columns if not str(c).startswith('_')]}")


def _hr_daily(df):
    """Har (date, department) ka ek row. Ek department ke kai rows (SHEET/MM/WEIGHT/BDL) mein
    manpower aur OT repeat hote hain, isliye max lete hain, sum nahi (warna double count hoga)."""
    cols = {_norm(c): c for c in df.columns if not str(c).startswith("_")}
    for need in ("department", "actual man power", "total over time hours"):
        if need not in cols:
            raise DataError(f"HR sheet: column '{need}' not found. Columns: {list(cols.values())}")
    w = pd.DataFrame({"_date": df["_date"]})
    w["dept"] = (df[cols["department"]].astype(str).str.strip().str.upper()
                .str.replace(r"\s+", " ", regex=True)
                .replace({"STICHING & COVRING": "STICHING & COVERING"}))
    w["man"] = _num(df[cols["actual man power"]]).fillna(0)
    w["ot"] = _num(df[cols["total over time hours"]]).fillna(0)
    w = w[w["dept"] != ""]
    return w.groupby(["_date", "dept"], as_index=False).agg(man=("man", "max"), ot=("ot", "max"))


def _hr_dates(df):
    """Sirf wo dates jin din kuch data bhara hai (blank September rows nahi)."""
    t = _hr_daily(df).groupby("_date")[["man", "ot"]].sum()
    return sorted(t[(t["man"] > 0) | (t["ot"] > 0)].index, reverse=True)


@st.cache_data(ttl=900, show_spinner="Loading stock file (large file)...")
def _fetch_stock_cached(url, sheet_name):
    src = io.BytesIO(_http_get(_direct_url(url))) if re.match(r"^https?://", url or "") else url
    raw = pd.read_excel(src, sheet_name=sheet_name, dtype=object, engine="openpyxl")
    keys = {re.sub(r"[^A-Z0-9]", "", str(c).upper()): c for c in raw.columns}

    def pick(prefix):
        for k, c in keys.items():
            if k.startswith(prefix):
                return c
        raise DataError(f"Column '{prefix}' not found. Columns: {list(raw.columns)}")

    df = pd.DataFrame({
        "date": _parse_dates(raw[pick("DATE")], True),
        "group": raw[pick("STOCKGROUP")].astype(str).str.strip().str.upper(),
        "item": raw[pick("ITEMNAME")].astype(str).str.strip().str.upper(),
        "qty": _num(raw[pick("QUANT")]),
        "amount": _num(raw[pick("AMOUNT")]),
    })
    df = df.dropna(subset=["date"])
    df = df[df["item"] != ""].copy()
    df["qty"] = df["qty"].fillna(0)
    df["amount"] = df["amount"].fillna(0)
    df["_date"] = df["date"].dt.date
    if df.empty:
        raise DataError("No valid date found in stock sheet")
    return df, datetime.datetime.now(IST)


# ====================================================================
# GRADE YIELD  (Prod. Summary file)
#   yield % = (grade ka weight / us period ka TOTAL weight) x 100
#   Item ka naam (ITEM NAME column) hi grade decide karta hai.
# ====================================================================
SECOND_GRADE_ITEMS = ["PEELING 2ND GRADE", "PU FOAM 2ND GRADE", "PU FOAM A GRADE",
                      "A GRADE", "PU FOAM DC GRADE"]
THIRD_GRADE_ITEMS = ["PEELING 3RD GRADE", "PU FOAM 3RD GRADE", "MEMORY FOAM SCRAP", "QUILTING SCRAP"]
# 1st Grade = BAAKI SAB items (mattress, pillow, bonded sheet, peeling roll, pu foam sheet ...)
FIRST_GRADE_EXCLUDE = SECOND_GRADE_ITEMS + THIRD_GRADE_ITEMS
BUNDLES_ONLY_WITH_WEIGHT = True      # True: jis row mein weight 0 hai (mattress) wo bundle count mein nahi
YIELD_START = datetime.date(2026, 4, 1)   # saal ki shuruaat (April)

_YIELD_DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%b-%y", "%d-%m-%Y",
                       "%d-%b-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d/%m/%y"]


@st.cache_data(ttl=900, show_spinner="Loading production summary (large file)...")
def _fetch_yield_cached(url, sheet_name):
    """Columns: DATE, ITEM NAME, BUNDLES, KGS  ->  _date, ym, item, kg, BUNDLES, grade (1/2/3)."""
    is_csv = str(url).lower().split("?")[0].endswith(".csv")
    if re.match(r"^https?://", url or ""):
        src = io.BytesIO(_http_get(_direct_url(url)))
    else:
        src = url
    if is_csv:
        raw = pd.read_csv(src, dtype=str)
    else:
        xl = pd.ExcelFile(src, engine="openpyxl")
        tab = sheet_name if sheet_name in xl.sheet_names else ("DATA" if "DATA" in xl.sheet_names else xl.sheet_names[0])
        raw = xl.parse(tab, dtype=object)
    
    # Headers ko clean karein (BUNDLES, KGS, DATE etc.)
    raw.columns = [re.sub(r"\s+", " ", str(c).strip().upper()) for c in raw.columns]

    def pick(exact, *contains):
        # 1. Exact match
        if exact in raw.columns:
            return exact
        # 2. Case-insensitive exact match 
        for c in raw.columns:
            if str(c).strip().upper() == exact.upper():
                return c
        # 3. Contains match (agar kahin beech mein ho)
        for c in raw.columns:
            if any(str(w).upper() in str(c).upper() for w in contains):
                return c
        return None

    date_col = pick("DATE", "DATE")
    item_col = pick("ITEM NAME", "ITEM", "NAME")
    kg_col = pick("KGS", "KGS", "KG", "WEIGHT") 
    # Yahan BUNDLES ko pehle dhoondhega, phir BUNDLE_NO
    bdl_col = pick("BUNDLES", "BUNDLE_NO", "BUNDLE", "BDL")
    sheet_col = pick("SHEET", "SHEET")
    mtr_col = pick("MTRS.", "MTRS", "MTR")
    gname_col = pick("GRADE", "GRADE")
    cat_col = next((c for c in raw.columns if str(c).startswith("CAT")), None)
    
    if not all([date_col, item_col, kg_col, bdl_col]):
        raise DataError(f"Columns not found (DATE / ITEM NAME / KGS / BUNDLES). Found: {list(raw.columns)}")

    txt = raw[date_col].astype(str).str.strip()
    d = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    for fmt in _YIELD_DATE_FORMATS:                    # file mein 2 date formats mile hue hain
        m = d.isna()
        if not m.any():
            break
        d[m] = pd.to_datetime(txt[m], format=fmt, errors="coerce")

    item = raw[item_col].astype(str).str.strip().str.upper().str.replace(r"\s+", " ", regex=True)
    df = pd.DataFrame({
        "_date": d.dt.date,
        "ym": d.dt.year * 100 + d.dt.month,
        "item": item,
        "kg": _num(raw[kg_col].astype(str).str.replace(',', '', regex=False)).fillna(0.0),
        "sheet": _num(raw[sheet_col]).fillna(0.0) if sheet_col else 0.0,
        "BUNDLES": raw[bdl_col].astype(str).str.strip().replace({"nan": "", "None": ""}) if bdl_col else "",
        "mtr": _num(raw[mtr_col]).fillna(0.0) if mtr_col else 0.0,
        "gname": raw[gname_col].astype(str).str.strip().str.upper().replace({"NAN": "", "NONE": ""}) if gname_col else "",
        "cat": raw[cat_col].astype(str).str.strip().str.upper().replace({"NAN": "", "NONE": ""}) if cat_col else "",
    })
    df["grade"] = 1
    df.loc[df["item"].isin(SECOND_GRADE_ITEMS), "grade"] = 2
    df.loc[df["item"].isin(THIRD_GRADE_ITEMS), "grade"] = 3
    df = df[d.notna()].copy()
    if df.empty:
        raise DataError("No valid date found in production summary")
    return df, datetime.datetime.now(IST)


def _grade_table(frame):
    """Ek period ka data -> weight, yield % aur bundles (1st / 2nd / 3rd)."""
    kg = frame.groupby("grade")["kg"].sum()
    total = float(kg.sum())
    b = frame[frame["BUNDLES"] != ""]
    if BUNDLES_ONLY_WITH_WEIGHT:
        b = b[b["kg"] > 0]
    bd = b.groupby("grade").size()
    return {
        "total": total,
        "kg": {g: float(kg.get(g, 0.0)) for g in (1, 2, 3)},
        "pct": {g: (float(kg.get(g, 0.0)) / total * 100 if total else 0.0) for g in (1, 2, 3)},
        "bdl": {g: int(bd.get(g, 0)) for g in (1, 2, 3)},
        "bdl_total": int(bd.sum()),
    }


# ---------------- PILLOW (J shed): bundle no. "26-J....." + item PILLOW ----------------
PILLOW_ITEM = "PILLOW"
PILLOW_BUNDLE_RE = r"^\d{2}-[JK]"      # 26-J00001 (J shed) + 26-K00001 (K shed) ...


def pillow_rows(y_df):
    """Prod. Summary se sirf J shed ke PILLOW rows (BUNDLES column 26-J..... se shuru)."""
    b = y_df["BUNDLES"].astype(str).str.strip().str.upper()
    # return y_df[(y_df["item"] == PILLOW_ITEM) & b.str.match(PILLOW_BUNDLE_RE)]   # purani line: sirf PILLOW item
    # Ab J + K shed ki SAARI rows (item chahe PILLOW, MATTRESS HOSPITAL, SOFA CUM BED kuch bhi ho): 2358 + 4663 = 7021 bundles
    return y_df[b.str.match(PILLOW_BUNDLE_RE)]


def pillow_agg(frame):
    """Bundles = rows ki ginti (count), Sheets = SHEET ka sum, Kg = KGS ka sum."""
    if frame.empty:
        return {"bdl": 0, "sheets": 0.0, "kg": 0.0}
    
    # Bundles ki ginti karo (jahan bundl no. likha ho)
    bdl_count = frame["BUNDLES"].astype(str).str.strip().ne("").sum()
    
    return {
        "bdl": int(bdl_count), 
        "sheets": float(frame["sheet"].sum()), 
        "kg": float(frame["kg"].sum())
    }
    
    # Sirf un rows ko ginein jinka weight 0 se zyada hai
    valid_frame = frame[frame["kg"] > 0]
    
    return {
        "bdl": int(len(valid_frame)), 
        "sheets": float(valid_frame["sheet"].sum()), 
        "kg": float(valid_frame["kg"].sum())
    }


def pillow_txt(a):
    return f"{a['bdl']:,} Bdls | {a['sheets']:,.0f} Sheets | {a['kg']:,.1f} Kg"


def shed_rows(y_df, letter, item=None):
    """Prod. Summary se kisi shed ke rows: BUNDLES column '26-<letter>.....' se shuru (H = Mattress, J = Pillow)."""
    b = y_df["BUNDLES"].astype(str).str.strip().str.upper()
    m = b.str.match(rf"^\d{{2}}-{letter}")
    if item:
        m = m & (y_df["item"] == item)
    return y_df[m]


def _month_range(day):
    m_start = day.replace(day=1)
    m_end = (m_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    return m_start, m_end

def bonded_card(day):
    """Bonded (A Shed): selected date, month aur total production (Bundles, Pcs, Weight). Yield = 100%"""
    y_df, err, _ = get_sheet("prod_summary")
    if y_df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    
    # Sirf A Shed (Bundles '26-A' se shuru hone wale)
    b = y_df["BUNDLES"].astype(str).str.strip().str.upper()
    m_rows = y_df[b.str.match(r"^\d{2}-A")]
    
    if m_rows.empty:
        return {"value": "No Data", "desc": "No 26-A bonded row found in Prod. Summary", "color": GREY}

    # Agar chuni hui date par data nahi hai, toh pichli latest date ka data uthao
    actual_day = day
    if not m_rows[m_rows["_date"] == day].empty:
        actual_day = day
    else:
        past_dates = m_rows[m_rows["_date"] <= day]["_date"]
        if not past_dates.empty:
            actual_day = past_dates.max()

    m_start, m_end = _month_range(actual_day)
    d_day = pillow_agg(m_rows[m_rows["_date"] == actual_day])
    d_mon = pillow_agg(m_rows[(m_rows["_date"] >= m_start) & (m_rows["_date"] <= m_end)])
    d_all = pillow_agg(m_rows)
    first, last = m_rows["_date"].min(), m_rows["_date"].max()

    def rows(a):
        return [("Bundles", f"{a['bdl']:,}"), ("Pcs", f"{a['sheets']:,.0f}"), ("Weight", f"{a['kg']:,.1f} Kg")]

    return {
        "value": f"100% Yield | {d_day['bdl']:,} Bdls | {d_day['sheets']:,.0f} Pcs",
        "desc": f"Bonded production (A Shed) · Showing data for {actual_day.strftime('%d-%b-%Y')}",
        "color": BLUE,
        "metrics": [
            ("100%", "Yield", "yield"),
            (f"{d_day['bdl']:,}", "Bundles"),
            (f"{d_day['sheets']:,.0f}", "Pcs"),
            (f"{d_day['kg']:,.1f}", "Kg"),
        ],
        "sections": [(f"🗓 Month {actual_day:%b-%y}", rows(d_mon))],
        "details": [(f"📆 Total ({first:%d-%m-%y} to {last:%d-%m-%y})", rows(d_all))],
    }


def mould_card(day):
    """Mould (J Shed): selected date, month aur total production (Bundles, Sheets, Weight)."""
    y_df, err, _ = get_sheet("prod_summary")
    if y_df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    
    # Sirf J Shed (Bundles '26-J' se shuru hone wale)
    b = y_df["BUNDLES"].astype(str).str.strip().str.upper()
    m_rows = y_df[b.str.match(r"^\d{2}-J")]
    
    if m_rows.empty:
        return {"value": "No Data", "desc": "No 26-J mould row found in Prod. Summary", "color": GREY}

    m_start, m_end = _month_range(day)
    d_day = pillow_agg(m_rows[m_rows["_date"] == day])
    d_mon = pillow_agg(m_rows[(m_rows["_date"] >= m_start) & (m_rows["_date"] <= m_end)])
    d_all = pillow_agg(m_rows)
    first, last = m_rows["_date"].min(), m_rows["_date"].max()

    def rows(a):
        return [("Bundles", f"{a['bdl']:,}"), ("Pcs", f"{a['sheets']:,.0f}"), ("Weight", f"{a['kg']:,.1f} Kg")]

    return {
        "value": f"{d_day['bdl']:,} Bdls | {d_day['sheets']:,.0f} Pcs | {d_day['kg']:,.1f} Kg",
        "desc": "Mould production (J Shed)",
        "color": BLUE,
        "metrics": [(f"{d_day['bdl']:,}", "Bundles"), (f"{d_day['sheets']:,.0f}", "Pcs"), (f"{d_day['kg']:,.1f}", "Kg")],
        "sections": [(f"🗓 Month {day:%b-%y}", rows(d_mon))],
        "details": [(f"📆 Total ({first:%d-%m-%y} to {last:%d-%m-%y})", rows(d_all))],
    }
FG_CATS = [
    # (naam, dikhane wale fields)
    ("A Grade",       ("bdl", "sheet")),
    ("Bonded",        ("bdl", "sheet", "kg")),
    ("PU Foam Sheet", ("bdl", "kg")),
    ("PU 2nd Grade",  ("bdl", "kg")),
    ("PU 3rd Grade",  ("bdl", "kg")),
    ("DC Grade",      ("bdl", "kg")),
    ("Mattress",      ("bdl", "pcs")),
    ("Rollpack",      ("bdl", "pcs")),
    ("Pillow",        ("bdl", "pcs")),
    ("Other / Scrap", ("bdl", "kg")),
]


def _fg_category(item, bundle):
    item = str(item).upper().strip()
    bundle = str(bundle).upper().strip()
    if "MATTRESS" in item:
        return "Mattress"
    if "ROLLPACK" in item or "ROLL PACK" in item:
        return "Rollpack"
    if "PILLOW" in item:
        return "Pillow"
    if "BONDED" in item or bundle.startswith("26-A"):
        return "Bonded"
    if "DC GRADE" in item:
        return "DC Grade"
    if item in ("A GRADE", "PU FOAM A GRADE"):
        return "A Grade"
    if "2ND GRADE" in item:
        return "PU 2nd Grade"
    if "3RD GRADE" in item:
        return "PU 3rd Grade"
    if item == "PU FOAM SHEET":
        return "PU Foam Sheet"
    return "Other / Scrap"
def finance_gt90_card(day):
    """Greater Than 90 / 180 Days Ageing: Is file mein Total Amount ka sum nikalta hai."""
    # Yahan aapko apni us Excel file ki config key daalni hogi jo aapne SHEETS mein define ki hai.
    # Agar aapne us file ka naam SHEETS mein "finance_gt90" rakha hai, toh yahan wahi likhein.
    df, err, _ = get_sheet("finance_gt90")
    
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}

    cols = [c for c in df.columns if not str(c).startswith("_")]
    norm = lambda s: re.sub(r"[^A-Z0-9]", "", str(s).upper())
    
    # Columns automatically dhoondhna
    # Total Amount column dhoondhein
    amt_col = next((c for c in cols if norm(c) == "TOTALAMOUNT"), None)
    
    if not amt_col:
        return {"value": "Error", "desc": f"TOTAL AMOUNT column not found. Columns: {cols}", "color": RED}

    # Data clean karna aur sum nikalna
    total_amt = _num(df[amt_col]).fillna(0.0).sum()

    # Convert to Crores (kyunki dashboard par Cr mein dikhana hai)
    def to_cr(x):
        return f"{x / 10000000:,.2f}"

    return {
        "value": f"{to_cr(total_amt)} Cr",
        "desc": f"Total Amount for >90/180 Days (As on {day:%d-%b-%Y})",
        "color": BLUE,
        "metrics": [
            (f"{to_cr(total_amt)} Cr", "Total Amount")
        ],
        "details": [
            ("📊 Summary", [("Total Amount", f"{to_cr(total_amt)} Cr ({_inr(total_amt)})")])
        ],
    }

def finance_drs_crs_card(day):
    """DRS & CRS: BAL.AMT ka seedha sum (bina Dr/Cr sign ke, Excel jaisa)."""
    # Yahan "_m" add kar dein
    df, err, _ = get_sheet("finance_drs_crs_m") 
    
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}

    cols = [c for c in df.columns if not str(c).startswith("_")]
    norm = lambda s: re.sub(r"[^A-Z0-9]", "", str(s).upper())
    
    # Columns automatically dhoondhna
    grp_col = next((c for c in cols if norm(c) == "GROUP"), None)
    bal_col = next((c for c in cols if norm(c) == "BALAMT"), None)
    
    if not grp_col or not bal_col:
        return {"value": "Error", "desc": f"GROUP / BAL.AMT column not found. Columns: {cols}", "color": RED}

    # Data ko clean karna
    w = pd.DataFrame({
        "grp": df[grp_col].astype(str).str.strip(),
        "bal": _num(df[bal_col]).fillna(0.0),
    })
    w = w[w["grp"] != ""]

    # Aapke exact groups
    DRS_GROUPS = ["sundry debtors"]
    CRS_GROUPS = ["sundry creditors", "sundry creditors for expenses"]

    # 1. DRS Calculation: Sirf Sundry Debtors ka balance sum
    drs = float(w[w["grp"].str.lower().isin(DRS_GROUPS)]["bal"].sum())
    
    # 2. CRS Calculation: Sundry Creditors + Sundry Creditors For Expenses ka sum
    crs = float(w[w["grp"].str.lower().isin(CRS_GROUPS)]["bal"].sum())

    # Convert to Crores (kyunki dashboard par Cr mein dikhana hai)
    def to_cr(x):
        return f"{x / 10000000:,.2f}"

    # Group-wise detail ke liye (View full details mein dikhega)
    def group_rows(groups):
        rows = []
        for g in groups:
            f = w[w["grp"].str.lower() == g]
            total = float(f["bal"].sum())
            rows.append((g.title(), f"{to_cr(total)} Cr  ({len(f)} parties)"))
        return rows

    # Card Return
    return {
        "value": f"DRS {to_cr(drs)} Cr | CRS {to_cr(crs)} Cr",
        "desc": "Closing balance (Data from 1 April till date)",
        "color": BLUE,
        "metrics": [
            (f"{to_cr(drs)} Cr", "DRS (Debtors)"),
            (f"{to_cr(crs)} Cr", "CRS (Creditors)")
        ],
        "details": [
            ("💰 DRS group-wise", group_rows(DRS_GROUPS)),
            ("💸 CRS group-wise", group_rows(CRS_GROUPS)),
        ],
    }
def credit_note_card(day):
    """Credit Note (CN): Day total, Month total, aur Month-wise breakdown."""
    df, err, _ = get_sheet("cn_sheet") 
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}

    # Column names dhoondhna (TOTAL aur Date column)
    amt_col = next((c for c in df.columns if str(c).strip().upper() == "TOTAL"), None)
    if not amt_col:
        return {"value": "Error", "desc": "TOTAL column not found", "color": RED}

    # Data clean karna
    df["amt"] = _num(df[amt_col]).fillna(0.0)
    df["month_year"] = df["_date"].apply(lambda x: x.strftime('%b-%Y') if pd.notna(x) else "")

    # 1. Selected Day ka Total
    day_data = df[df["_date"] == day]
    day_total = day_data["amt"].sum()

    # 2. Selected Month ka Total
    m_start, m_end = _month_range(day)
    month_data = df[(df["_date"] >= m_start) & (df["_date"] <= m_end)]
    month_total = month_data["amt"].sum()

    # 3. Month-wise Breakdown (April se Nov tak)
    # Hum sirf un months ko dikhayenge jahan data hai
    month_breakdown = df.groupby("month_year")["amt"].sum().reset_index()
    month_breakdown["_date"] = pd.to_datetime(month_breakdown["month_year"], format='%b-%Y')
    month_breakdown = month_breakdown.sort_values("_date", ascending=False)
    
    month_rows = []
    for _, row in month_breakdown.iterrows():
        if row["amt"] > 0:
            month_rows.append((row["month_year"], f"{row['amt']:,.2f}"))

    # 4. Grand Total (1 April se abhi tak)
    grand_total = df["amt"].sum()
    day_total = day_total / 10000000
    month_total = month_total / 10000000
    grand_total = grand_total / 10000000

    return {
        "value": f"{day_total:,.2f}",
        "desc": f"CN for {day:%d-%b-%Y}",
        "color": BLUE,
        "sections": [
            (f"🗓 Month Total ({day:%b-%Y})", [("Total CN Amount", f"{month_total:,.2f}")])
        ],
        "details": [
            (f"📅 {day:%d-%b-%Y} Data", [("Total CN Amount", f"{day_total:,.2f}")]),
            (f"🗓 Month {day:%b-%Y} Total", [("Total CN Amount", f"{month_total:,.2f}")]),
            ("📊 Month-wise Breakdown", month_rows),
            ("📆 Grand Total (Till Date)", [("Total CN Amount", f"{grand_total:,.2f}")])
        ]
    }

def debit_note_card(day):
    """Debit Note (DN): Day total, Month total, aur Month-wise breakdown."""
    df, err, _ = get_sheet("dn_sheet") 
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}

    # Column names dhoondhna (TOTAL aur Date column)
    amt_col = next((c for c in df.columns if str(c).strip().upper() == "TOTAL"), None)
    if not amt_col:
        return {"value": "Error", "desc": "TOTAL column not found", "color": RED}

    # Data clean karna
    df["amt"] = _num(df[amt_col]).fillna(0.0)
    df["month_year"] = df["_date"].apply(lambda x: x.strftime('%b-%Y') if pd.notna(x) else "")

    # 1. Selected Day ka Total
    day_data = df[df["_date"] == day]
    day_total = day_data["amt"].sum()

    # 2. Selected Month ka Total
    m_start, m_end = _month_range(day)
    month_data = df[(df["_date"] >= m_start) & (df["_date"] <= m_end)]
    month_total = month_data["amt"].sum()

    # 3. Month-wise Breakdown (April se Nov tak)
    month_breakdown = df.groupby("month_year")["amt"].sum().reset_index()
    month_breakdown["_date"] = pd.to_datetime(month_breakdown["month_year"], format='%b-%Y')
    month_breakdown = month_breakdown.sort_values("_date", ascending=False)
    
    month_rows = []
    for _, row in month_breakdown.iterrows():
        if row["amt"] > 0:
            month_rows.append((row["month_year"], f"{row['amt']:,.2f}"))

    # 4. Grand Total (1 April se abhi tak)
    grand_total = df["amt"].sum()
    day_total = day_total / 10000000
    month_total = month_total / 10000000
    grand_total = grand_total / 10000000

    return {
        "value": f"{day_total:,.2f}",
        "desc": f"DN for {day:%d-%b-%Y}",
        "color": BLUE,
        "sections": [
            (f"🗓 Month Total ({day:%b-%Y})", [("Total DN Amount", f"{month_total:,.2f}")])
        ],
        "details": [
            (f"📅 {day:%d-%b-%Y} Data", [("Total DN Amount", f"{day_total:,.2f}")]),
            (f"🗓 Month {day:%b-%Y} Total", [("Total DN Amount", f"{month_total:,.2f}")]),
            ("📊 Month-wise Breakdown", month_rows),
            ("📆 Grand Total (Till Date)", [("Total DN Amount", f"{grand_total:,.2f}")])
        ]
    }
def _note_month_card(sheet, tag, day):
    """CN / DN: sirf MONTH-WISE total (selected month ki 1st date se last data tak) + party-wise detail."""
    df, err, _ = get_sheet(sheet)
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    amt_col = next((c for c in df.columns if str(c).strip().upper() == "TOTAL"), None)
    if not amt_col:
        return {"value": "Error", "desc": "TOTAL column not found", "color": RED}

    w = df[df["_date"].notna()].copy()
    w["amt"] = _num(w[amt_col]).fillna(0.0)

    m_start, m_end = _month_range(day)
    mon = w[(w["_date"] >= m_start) & (w["_date"] <= m_end)]
    mon_total = float(mon["amt"].sum())
    last = mon["_date"].max() if not mon.empty else None
    rng = f"{m_start:%d-%b} to {last:%d-%b-%Y}" if last else f"{day:%b-%Y}"

    by = w.assign(ym=w["_date"].apply(lambda x: (x.year, x.month))).groupby("ym")["amt"].sum().sort_index(ascending=False)
    rows = [(datetime.date(y, m, 1).strftime("%b-%Y"), f"{v / 10000000:,.2f} Cr  ({_inr(v)})")
            for (y, m), v in by.items() if v != 0]
    grand = float(w["amt"].sum())

    # ---- party column apne aap dhoondho ----
    cols = [c for c in df.columns if not str(c).startswith("_")]
    exact = ("PARTY NAME", "PARTY", "PARTY'S NAME", "NAME OF PARTY", "CUSTOMER NAME", "PARTICULARS", "ACCOUNT NAME")
    pcol = next((c for c in cols if str(c).strip().upper() in exact), None) or \
        next((c for c in cols if c != amt_col and any(k in str(c).upper() for k in ("PARTY", "CUSTOMER", "PARTICULAR", "NAME"))), None)

    details = [
        (f"🗓 Month-wise {tag}", rows),
        ("📆 Grand Total (Till Date)", [(f"Total {tag} Amount", f"{grand / 10000000:,.2f} Cr  ({_inr(grand)})")]),
    ]
    if pcol is not None:
        pw = (mon.assign(party=mon[pcol].astype(str).str.strip())
              .groupby("party")["amt"].agg(["sum", "count"]).sort_values("sum", ascending=False))
        prow = [(p, f"{_inr(r['sum'])}  ({int(r['count'])} {tag})") for p, r in pw.iterrows()
                if p and p.lower() not in ("nan", "none")]
        details.insert(0, (f"👥 Party-wise {tag} · {day:%b-%Y} ({len(prow)} parties)",
                           prow + [("TOTAL", _inr(mon_total))]))
    else:
        details.insert(0, ("👥 Party-wise", [("Party column not found", "Sheet columns: " + ", ".join(map(str, cols)))]))

    return {
        "value": f"{mon_total / 10000000:,.2f}",
        "desc": f"{tag} total {day:%b-%Y} ({rng}) · {_inr(mon_total)}",
        "color": BLUE,
        "details": details,
    }
# ====================================================================
# CATEGORY MIX (Prod. Summary se, month-wise, item-group + grade-wise)
# ====================================================================
CMIX_GROUPS = [
    # (naam, item match karne wala function, dikhane wale fields)
    ("Rollpack",           lambda i: i.startswith("FLO ") or "ROLLPACK" in i or "ROLL PACK" in i, ("bdl", "pcs", "kg")),
    ("Mattress",           lambda i: "MATTRESS" in i,                                              ("bdl", "pcs", "kg")),
    ("Pillow",             lambda i: "PILLOW" in i,                                                ("bdl", "pcs", "kg")),
    ("Peeling Roll",       lambda i: "PEELING ROLL" in i,                                          ("bdl", "mtr", "kg")),
    ("Quilting Roll",      lambda i: "QUILTING ROLL" in i,                                         ("bdl", "mtr", "kg")),
    ("PU Foam Sheet",      lambda i: i == "PU FOAM SHEET",                                         ("bdl", "kg")),
    ("A Grade + DC Grade", lambda i: i in ("A GRADE", "PU FOAM A GRADE") or "DC GRADE" in i,       ("bdl", "kg")),
    ("PU 2nd / 3rd Grade", lambda i: "2ND GRADE" in i or "3RD GRADE" in i,                         ("bdl", "kg")),
    ("Bonded",             lambda i: "BONDED" in i,                                                ("bdl", "pcs", "kg")),
]
CMIX_OTHER = ("Other (Sofa cum bed etc.)", ("bdl", "pcs", "kg"))


def _cmix_group(item):
    for name, fn, _f in CMIX_GROUPS:
        if fn(item):
            return name
    return CMIX_OTHER[0]


def _cmix_fields(name):
    for n, _fn, f in CMIX_GROUPS:
        if n == name:
            return f
    return CMIX_OTHER[1]


def _cmix_agg(f):
    return {
        "bdl": int(f["BUNDLES"].astype(str).str.strip().ne("").sum()),
        "pcs": float(f["sheet"].sum()),
        "mtr": float(f["mtr"].sum()),
        "kg": float(f["kg"].sum()),
    }


def _cmix_txt(a, fields):
    parts = []
    for f in fields:
        if f == "bdl":
            parts.append(f"{a['bdl']:,} {'Rolls' if 'mtr' in fields else 'Bdls'}")
        elif f == "pcs":
            parts.append(f"{a['pcs']:,.0f} Pcs")
        elif f == "mtr":
            parts.append(f"{a['mtr']:,.0f} Mtr")
        else:
            parts.append(f"{a['kg']:,.1f} Kg")
    return " | ".join(parts)


# ====================================================================
# CATEGORY MIX (Prod. Summary se, month-wise, item-group + grade-wise)
# ====================================================================
# (naam, item match function, dikhane wale fields, View Details mein kis column se split: "gname" = GRADE, "cat" = CATEGORY)
# ORDER MATTER KARTA HAI: pehla match jeetta hai (Rollpack Mattress se pehle, kyunki FLO ... MATTRESS rollpack hai)
CMIX_GROUPS = [
    ("Rollpack",            lambda i: i.startswith("FLO ") or "ROLLPACK" in i or "ROLL PACK" in i,         ("bdl", "pcs", "kg"), "gname"),
    ("Mattress",            lambda i: "MATTRESS" in i,                                                     ("bdl", "pcs", "kg"), "gname"),
    ("Pillow",              lambda i: "PILLOW" in i,                                                       ("bdl", "pcs", "kg"), "gname"),
    ("Peeling Roll",        lambda i: i in ("PEELING ROLL", "PEELING") or i.startswith("PEELING ROLL"),    ("bdl", "mtr", "kg"), "cat"),
    ("Quilting Roll",       lambda i: "QUILTING ROLL" in i,                                                ("bdl", "mtr", "kg"), "gname"),
    ("PU Foam Sheet",       lambda i: i == "PU FOAM SHEET" or "PROFILE SHEET" in i,                        ("bdl", "kg"),        "gname"),
    ("A Grade + DC Grade",  lambda i: i in ("A GRADE", "PU FOAM A GRADE") or "DC GRADE" in i,              ("bdl", "kg"),        "gname"),
    ("PU 2nd / 3rd / Scrap", lambda i: "2ND GRADE" in i or "3RD GRADE" in i or "SCRAP" in i,               ("bdl", "kg"),        "gname"),
    ("Bonded",              lambda i: "BONDED" in i,                                                       ("bdl", "pcs", "kg"), "gname"),
]
CMIX_OTHER = ("Other (Sofa cum bed)", ("bdl", "pcs", "kg"), "gname")   # jo upar kisi group mein nahi aaya


def _cmix_group(item):
    for name, fn, _f, _s in CMIX_GROUPS:
        if fn(item):
            return name
    return CMIX_OTHER[0]


def _cmix_meta(name):
    for n, _fn, f, s in CMIX_GROUPS:
        if n == name:
            return f, s
    return CMIX_OTHER[1], CMIX_OTHER[2]


def _cmix_agg(f):
    return {
        "bdl": int(f["BUNDLES"].astype(str).str.strip().ne("").sum()),
        "pcs": float(f["sheet"].sum()),
        "mtr": float(f["mtr"].sum()),
        "kg": float(f["kg"].sum()),
    }


def _cmix_txt(a, fields):
    parts = []
    for f in fields:
        if f == "bdl":
            parts.append(f"{a['bdl']:,} {'Rolls' if 'mtr' in fields else 'Bdls'}")
        elif f == "pcs":
            parts.append(f"{a['pcs']:,.0f} Pcs")
        elif f == "mtr":
            parts.append(f"{a['mtr']:,.0f} Mtr")
        else:
            parts.append(f"{a['kg']:,.1f} Kg")
    return " | ".join(parts)


def _cmix_total(frame):
    """Poore frame ka total: Bundles = saare items, Kg = saare items, Pcs = sirf wo groups jinme Pcs dikhte hain
    (roll / sheet wale items ki 'SHEET' = 1 ko pcs mein nahi ginte)."""
    grp = frame["item"].map(_cmix_group)
    pcs_groups = {n for n, _fn, f, _s in CMIX_GROUPS if "pcs" in f} | {CMIX_OTHER[0]}
    a = _cmix_agg(frame)
    a["pcs"] = float(frame.loc[grp.isin(pcs_groups), "sheet"].sum())
    return a
# Pcs wali categories (Category Mix 1). Baaki sab Kgs wali (Category Mix 2).
def _cm_group(item):
    u = re.sub(r"\s+", " ", str(item)).strip().upper()
    if u == "PILLOW":
        return "Pillow"
    if u.startswith("MATTRESS") and u != "MATTRESS COVER":
        return "Mattress"
    if u == "SOFA CUM BED":
        return "Sofa Cum Bed"
    if u == "BONDED SHEET":
        return "Bonded Sheet"
    if u == "FOAM MATTRESS BARE":
        return "Foam Mattress Bare"
    if u == "ORTHO PILLOW":
        return "Ortho Pillow"
    if u == "MATTRESS COVER":
        return "Mattress Cover"
    return None


def _cm_load(day=None):
    df, err, _ = get_sheet("cate_1")
    if df is None:
        return None, err
    w = df.copy()
    w.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in w.columns]
    low = {c.lower(): c for c in w.columns}
    pick = lambda *n: next((low[x.lower()] for x in n if x.lower() in low), None)
    item, grade = pick("ITEM", "Category"), pick("Grade")
    pcs, kgs, amt = pick("Pcs", "Pieces"), pick("Kgs", "Kg"), pick("Amt", "Amount", "Value")
    month_col = pick("Month", "Date")
    if not (item and pcs and kgs and amt):
        return None, f"Columns not found: {list(w.columns)}"
    if day is not None and month_col:
        target_short = day.strftime("%b").lower()
        m_series = w[month_col].astype(str).str.strip().str.lower()
        w = w[m_series.str.startswith(target_short)]
    if False:   # static sheet ki _date = aaj ki date hoti hai, isliye month Month column se hi filter hoga
        w = w[(pd.to_datetime(w["_date"]).dt.year == day.year) & (pd.to_datetime(w["_date"]).dt.month == day.month)]
    elif day is not None and month_col:
        target_m = day.strftime("%B").lower()
        target_short = day.strftime("%b-%y").lower()
        m_series = w[month_col].astype(str).str.strip().str.lower()
        w = w[m_series.str.startswith(target_m) | (m_series == target_short)]
    for c in (pcs, kgs, amt):
        w[c] = pd.to_numeric(w[c].astype(str).str.replace(",", "").str.replace("₹", "").str.strip(), errors="coerce").fillna(0.0)
    w["_item"] = w[item].fillna("").astype(str).str.strip()
    w.loc[w["_item"].isin(["", "nan", "None", "NaN", "#N/A"]), "_item"] = "UNSPECIFIED"
    w["_grade"] = w[grade].fillna("").astype(str).str.strip() if grade else "-"
    w.loc[w["_grade"].isin(["", "nan", "None", "NaN"]), "_grade"] = "-"
    w["_grp"] = w["_item"].map(_cm_group)
    w = w[(w[pcs] != 0) | (w[kgs] != 0) | (w[amt] != 0)].copy()
    return (w, pcs, kgs, amt), None


def _cm_amt(x):
    v = float(x)
    if abs(v) >= 1e7: return f"₹{v/1e7:,.2f} Cr"
    if abs(v) >= 1e5: return f"₹{v/1e5:,.2f} L"
    return f"₹{v:,.2f}"
def _cm_tile(name, a, b):
    """Ek category ka box: upar naam, neeche ek hi line mein (a) aur (b)."""
    import html as _h
    num = f'<span style="font-size:13px;font-weight:800;">{_h.escape(str(name))}</span>'
    lbl = (f'<span style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:2px 8px;'
           f'text-transform:none;letter-spacing:0;font-size:12px;font-weight:700;color:#0F172A;">'
           f'<span>{a}</span><span>{b}</span></span>')
    return (num, lbl)


def category_mix_pcs_card(day):
    r, err = _cm_load(day)
    if r is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    w, pcs, kgs, amt = r
    w = w[w["_grp"].notna()]
    if w.empty:
        return {"value": "0 Items", "desc": "No data found", "color": GREY}
    sections, details = [], []
    for g in ["Pillow", "Mattress", "Sofa Cum Bed", "Bonded Sheet", "Foam Mattress Bare", "Ortho Pillow", "Mattress Cover"]:
        x = w[w["_grp"] == g]
        if x.empty:
            continue
        sections.append(_cm_tile(g.upper(), f"{x[pcs].sum():,.0f} Pcs", _cm_amt(x[amt].sum())))
        rows = []
        for _, rr in x.sort_values(amt, ascending=False).iterrows():
            nm = rr["_grade"] if rr["_item"].upper() == g.upper() else f"{rr['_grade']} ({rr['_item'].title()})"
            rows.append((nm, f"{rr[pcs]:,.0f} Pcs | {_cm_amt(rr[amt])}"))
        rows.append(("TOTAL", f"{x[pcs].sum():,.0f} Pcs | {_cm_amt(x[amt].sum())}"))
        details.append((f"📦 {g} · Grade-wise", rows))
    return {
        "value": _cm_amt(w[amt].sum()),
        "desc": "Pillow · Mattress · Sofa Cum Bed · Bonded Sheet",
        "color": BLUE,
        "metrics": [(f"{w[pcs].sum():,.0f}", "Total Pcs"), (_cm_amt(w[amt].sum()), "Total Amt")] + sections,
        "details": details,
    }


def category_mix_kgs_card(day):
    r, err = _cm_load(day)
    if r is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    w, pcs, kgs, amt = r
    w = w[w["_grp"].isna()]
    if w.empty:
        return {"value": "0 Items", "desc": "No data found", "color": GREY}
    items = w.groupby("_item")[[kgs, amt]].sum().sort_values(amt, ascending=False)
    tiles = [_cm_tile(i, f"{v[kgs]:,.1f} Kg", _cm_amt(v[amt])) for i, v in items.iterrows()]
    details = []
    for i in items.index:
        x = w[w["_item"] == i].sort_values(amt, ascending=False)
        rows = [(rr["_grade"], f"{rr[kgs]:,.1f} Kg | {_cm_amt(rr[amt])}") for _, rr in x.iterrows()]
        rows.append(("TOTAL", f"{x[kgs].sum():,.1f} Kg | {_cm_amt(x[amt].sum())}"))
        details.append((f"📦 {i} · Grade-wise", rows))
    return {
        "value": _cm_amt(w[amt].sum()),
        "desc": f"gs categories ({len(items)})",
        "color": BLUE,
        "metrics": [(f"{w[kgs].sum():,.0f}", "Total Kg"), (_cm_amt(w[amt].sum()), "Total Amt")] + tiles,
        "details": details,
    }


def category_mix_card(day):
    """Category Mix: cate (1) sheet se har ek ITEM category + Grade wise breakdown aur Amount."""
    df, err, _ = get_sheet("cate_1")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}

    w = df.copy()
    w.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in w.columns]

    def _col(names):
        for n in names:
            for c in w.columns:
                if c.lower() == n.lower():
                    return c
        return None

    item_col = _col(["ITEM", "Item", "Category"])
    grade_col = _col(["Grade", "GRADE"])
    bdl_col = _col(["Bundle", "Bundles", "BDL"])
    pcs_col = _col(["Pcs", "PCS", "Pieces"])
    kgs_col = _col(["Kgs", "Kg", "KG"])
    amt_col = _col(["Amt", "Amount", "Value"])

    if not item_col:
        return {"value": "Config error", "desc": f"ITEM column not found: {list(w.columns)}", "color": RED}

    for col in [bdl_col, pcs_col, kgs_col, amt_col]:
        if col:
            w[col] = pd.to_numeric(
                w[col].astype(str).str.replace(",", "").str.replace("₹", "").str.strip(),
                errors="coerce",
            ).fillna(0.0)
        else:
            w[col] = 0.0

    # Har ek ITEM category ko lo — blank ITEM ko "UNSPECIFIED" naam do taaki kuch bhi skip na ho
    w["_item"] = w[item_col].fillna("").astype(str).str.strip()
    w.loc[w["_item"].isin(["", "nan", "None", "NaN"]), "_item"] = "UNSPECIFIED"

    w["_grade"] = w[grade_col].fillna("").astype(str).str.strip() if grade_col else "-"
    w.loc[w["_grade"].isin(["", "nan", "None", "NaN"]), "_grade"] = "-"

    # Sirf completely empty (all 0) rows hatayein
    w = w[(w[bdl_col] != 0) | (w[pcs_col] != 0) | (w[kgs_col] != 0) | (w[amt_col] != 0)].copy()
    if w.empty:
        return {"value": "0 Items", "desc": "No data found", "color": GREY}

    fmt_i = lambda x: f"{int(round(float(x))):,}"
    fmt_k = lambda x: f"{float(x):,.1f}"
    def fmt_a(x):
        v = float(x)
        if abs(v) >= 1e7:
            return f"₹{v / 1e7:,.2f} Cr"
        elif abs(v) >= 1e5:
            return f"₹{v / 1e5:,.2f} L"
        return f"₹{v:,.2f}"

    tot_bdl = w[bdl_col].sum()
    tot_pcs = w[pcs_col].sum()
    tot_kgs = w[kgs_col].sum()
    tot_amt = w[amt_col].sum()

    # Har ek category (ITEM) — ek bhi skip nahi hogi
    item_order = list(dict.fromkeys(w["_item"].tolist()))
    summary_rows = []
    details = []

    for item_name in item_order:
        g = w[w["_item"] == item_name]
        c_bdl = g[bdl_col].sum()
        c_pcs = g[pcs_col].sum()
        c_kgs = g[kgs_col].sum()
        c_amt = g[amt_col].sum()

        line_txt = f"{fmt_i(c_bdl)} Bdls | {fmt_i(c_pcs)} Pcs | {fmt_k(c_kgs)} Kg | {fmt_a(c_amt)}"
        summary_rows.append((item_name, line_txt))

        # View Full Details: Har category ke niche uske saare Grade rows + Category Total
        g_rows = []
        for _, r in g.iterrows():
            g_rows.append((
                r["_grade"],
                f"{fmt_i(r[bdl_col])} Bdls | {fmt_i(r[pcs_col])} Pcs | {fmt_k(r[kgs_col])} Kg | {fmt_a(r[amt_col])}",
            ))
        g_rows.append((f"TOTAL ({item_name})", line_txt))
        details.append((f"📦 {item_name} · {line_txt}", g_rows))

    summary_rows.append((
        "TOTAL (sab items)",
        f"{fmt_i(tot_bdl)} Bdls | {fmt_i(tot_pcs)} Pcs | {fmt_k(tot_kgs)} Kg | {fmt_a(tot_amt)}",
    ))

    return {
        "value": fmt_a(tot_amt),
        "desc": f"Category mix ({len(item_order)} categories) · Total Amt: {fmt_a(tot_amt)}",
        "color": BLUE,
        "metrics": [
            (fmt_i(tot_bdl), "Bundles"),
            (fmt_i(tot_pcs), "Pcs"),
            (fmt_k(tot_kgs), "Kg"),
            (fmt_a(tot_amt), "Total Amt"),
        ],
        "sections": [
            (f"📦 All Categories ({len(item_order)} Items) · Qty & Amount", summary_rows),
        ],
        "details": details,
    }
def _ds_num(v):
    s = str(v).strip().replace(",", "")
    if s.upper() in ("", "NIL", "NAN", "NONE", "-"):
        return 0.0
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else 0.0


def _ds_parse(rows):
    """Rows -> items: cat, item, uom, prev, last, bdl."""
    out, section = [], "main"
    for r in rows:
        r = [("" if str(x).strip().lower() == "nan" else str(x).strip()) for x in r] + [""] * 6
        a, b, c, d, e, f = r[:6]
        up = b.upper()
        if up.startswith("OLD MATTRESS COVER"):
            section = "Old Mattress Cover"
            continue
        if up.startswith("OLD INN"):
            section = "Old Inner Cover"
            continue
        if not b or not a.replace(".", "").isdigit():
            continue
        if section == "main":
            out.append({"cat": re.sub(r"\s+", " ", c).strip().title() or "Other", "item": b,
                        "uom": d.upper(), "prev": _ds_num(e), "last": _ds_num(f), "bdl": 0.0})
        else:
            out.append({"cat": section, "item": b, "uom": "PCS",
                        "prev": _ds_num(e), "last": _ds_num(f), "bdl": _ds_num(d)})
    return out


def _ds_date_label(h):
    s = str(h)
    m = re.search(r"\d{1,2}\.\d{1,2}\.\d{2,4}", s)
    if m:
        return m.group()
    try:
        return pd.to_datetime(s).strftime("%d.%m.%y")
    except Exception:
        return s.strip()


def dead_stock_store_card(day):
    df, err, _ = get_sheet("dead_stock_store")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    base = df.iloc[:, :6]
    if all(isinstance(c, int) for c in base.columns):      # Google Sheet: header row data ke andar hai
        rows = base.values.tolist()
    else:                                                   # Excel file: header = columns
        rows = [list(base.columns)] + base.values.tolist()
    hdr = rows[0]
    items = [x for x in _ds_parse(rows) if x["last"] > 0]
    if not items:
        return {"value": "0 Items", "desc": "No dead stock", "color": BLUE}
    prev_lbl, last_lbl = _ds_date_label(hdr[4]), _ds_date_label(hdr[5])

    def uom_txt(lst):
        t = {}
        for x in lst:
            t[x["uom"]] = t.get(x["uom"], 0) + x["last"]
        return " | ".join(f"{v:,.0f} {u}" for u, v in sorted(t.items(), key=lambda kv: -kv[1]))

    cats = {}
    for x in items:
        cats.setdefault(x["cat"], []).append(x)

    summary, drill = [], []
    for cat, lst in cats.items():
        summary.append((cat, uom_txt(lst)))
        rows = []
        for x in lst:
            if x["bdl"]:
                txt = f"{x['bdl']:,.0f} Bdl · {x['last']:,.0f} Pcs  ({prev_lbl}: {x['prev']:,.0f})"
            else:
                txt = f"{x['last']:,.0f} {x['uom']}  ({prev_lbl}: {x['prev']:,.0f})"
            rows.append((x["item"], txt))
        rows.append(("TOTAL", uom_txt(lst)))
        drill.append((f"▸ {cat} · {len(lst)} materials · {uom_txt(lst)}", rows))

    return {
        "value": f"{len(cats)} Categories",
        "desc": f"Dead stock balance as on {last_lbl}",
        "color": BLUE,
        "metrics": [(f"{len(cats)}", "Categories"), (f"{len(items)}", "Materials")],
        "sections": [(f"📦 Category-wise balance · {last_lbl}", summary)],
        "drill": drill,
    }

def total_inventory_card(day):
    """Total Inventory Bundles (FG): din + mahine ki total production, category wise + SHED WISE details."""
    y_df, err, _ = get_sheet("prod_summary")
    if y_df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}

    y_df = y_df.copy()
    y_df = y_df[y_df["BUNDLES"].astype(str).str.strip() != ""]
    
    # --- Shed nikalne ke liye helper ---
    def get_shed(bundle):
        b = str(bundle).strip().upper()
        # "26-A123" -> "A Shed" (agar 2 digit year ke baad - aur letter ho)
        m = re.match(r"^\d{2}-([A-Z])", b)
        if m:
            return f"{m.group(1)} Shed"
        return "Other"

    y_df["cat"] = [_fg_category(i, b) for i, b in zip(y_df["item"], y_df["BUNDLES"])]
    y_df["shed"] = y_df["BUNDLES"].apply(get_shed)

    def agg(frame):
        out = {}
        for name, _f in FG_CATS:
            f = frame[frame["cat"] == name]
            out[name] = {
                "bdl": len(f), 
                "sheet": float(f["sheet"].sum()), 
                "pcs": float(f["sheet"].sum()),
                "kg": float(f["kg"].sum())
            }
        total = {
            "bdl": sum(v["bdl"] for v in out.values()),
            "sheet": out["A Grade"]["sheet"] + out["Bonded"]["sheet"],
            "pcs": sum(out[k]["pcs"] for k in ("Mattress", "Rollpack", "Pillow")),
            "kg": sum(out[k]["kg"] for k in out if k not in ("A Grade", "Mattress", "Rollpack", "Pillow")),
        }
        return out, total

    m_start, m_end = _month_range(day)
    d_cat, d_tot = agg(y_df[y_df["_date"] == day])
    m_cat, m_tot = agg(y_df[(y_df["_date"] >= m_start) & (y_df["_date"] <= m_end)])

    def line(name, fields, c):
        label = {"bdl": "Bdls", "sheet": "Sheet", "pcs": "Pcs", "kg": "Kg"}
        parts = []
        for f in fields:
            v = c[name][f]
            parts.append(f"{v:,.0f} {label[f]}" if f != "kg" else f"{v:,.1f} Kg")
        return " | ".join(parts)

    # Naya function: har category ke andar shed-wise lines nikalne ke liye
    def get_shed_rows(frame, cat_name):
        """Us category ke andar shed-wise breakup rows banata hai."""
        cat_frame = frame[frame["cat"] == cat_name]
        if cat_frame.empty:
            return []
        
        shed_counts = cat_frame.groupby("shed").size().sort_index()
        return [(f"  ↳ {shed}", f"{count} Bdls") for shed, count in shed_counts.items()]

    def rows(c, tot, frame_for_sheds):
        result = []
        for name, fields in FG_CATS:
            if c[name]["bdl"] > 0:
                # 1. Main category ki line
                result.append((name, line(name, fields, c)))
                # 2. Uske neeche shed-wise lines (jab View Details khula ho)
                result.extend(get_shed_rows(frame_for_sheds, name))
        result.append(("TOTAL", f"{tot['bdl']:,} Bdls | {tot['sheet']:,.0f} Sheet | {tot['pcs']:,.0f} Pcs | {tot['kg']:,.1f} Kg"))
        return result

    return {
        "value": f"{d_tot['bdl']:,} Bdls",
        "desc": "Finished goods production (Prod. Summary)",
        "color": BLUE,
        "metrics": [
            (f"{d_tot['bdl']:,}", "Bundles"),
            (f"{d_tot['sheet']:,.0f}", "Sheet"),
            (f"{d_tot['pcs']:,.0f}", "Pcs"),
            (f"{d_tot['kg']:,.1f}", "Kg"),
        ],
        "sections": [
            (f"🗓 Month {day:%b-%y} Total", [
                ("Bundles", f"{m_tot['bdl']:,}"),
                ("Sheet", f"{m_tot['sheet']:,.0f}"),
                ("Pcs", f"{m_tot['pcs']:,.0f}"),
                ("Weight", f"{m_tot['kg']:,.1f} Kg"),
            ])
        ],
        "details": [
            # Day wale section mein day ka data pass kiya
            (f"📅 {day:%d-%m-%y} · Category & Shed wise", rows(d_cat, d_tot, y_df[y_df["_date"] == day])),
            # Month wale section mein month ka data pass kiya
            (f"🗓 Month {day:%b-%y} · Category & Shed wise", rows(m_cat, m_tot, y_df[(y_df["_date"] >= m_start) & (y_df["_date"] <= m_end)])),
        ],
    }
def scrap_card(day):
    """Scrap (O Shed): Bundles count + KGs sum (Day & Month wise) aur 3 items ki yield."""
    y_df, err, _ = get_sheet("prod_summary")
    if y_df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    
    # O Shed ki rows (Bundles '26-O' se shuru hone wali)
    b = y_df["BUNDLES"].astype(str).str.strip().str.upper()
    o_rows = y_df[b.str.match(r"^\d{2}-O")]
    
    if o_rows.empty:
        return {"value": "No Data", "desc": "No 26-O scrap row found in Prod. Summary", "color": GREY}

    m_start, m_end = _month_range(day)

    # --- Day wise ---
    d_day = o_rows[o_rows["_date"] == day]
    day_bdls = int(d_day["BUNDLES"].astype(str).str.strip().ne("").sum())
    day_kg = float(d_day["kg"].sum())

    # --- Month wise ---
    d_mon = o_rows[(o_rows["_date"] >= m_start) & (o_rows["_date"] <= m_end)]
    mon_bdls = int(d_mon["BUNDLES"].astype(str).str.strip().ne("").sum())
    mon_kg = float(d_mon["kg"].sum())

    # --- Month-wise Breakdown (View Details ke liye) ---
    month_breakdown_rows = []
    if not d_mon.empty:
        m_grouped = d_mon.groupby("_date").agg(
            bdls=("BUNDLES", lambda x: x.astype(str).str.strip().ne("").sum()),
            kg=("kg", "sum")
        ).sort_index(ascending=False)
        
        for dt, row in m_grouped.iterrows():
            dt_str = dt.strftime('%d-%b-%Y')
            month_breakdown_rows.append((f"📅 {dt_str}", f"{row['bdls']} Bdls | {row['kg']:,.1f} Kg"))

    # --- Yield Calculation (3 Items) ---
    scrap_items = ["PU FOAM 3RD GRADE", "MEMORY FOAM SCRAP", "QUILTING SCRAP"]
    
    # Formula: (Item ka total weight / 3 items ke total weight) * 100
    # item column ka naam dhoondho (case-insensitive)
    item_col = next((c for c in d_mon.columns if str(c).strip().upper() == "ITEM"), "item")
    mon_item_weights = {item: float(d_mon.loc[d_mon[item_col] == item, "kg"].sum()) for item in scrap_items}
    total_3_items_kg = sum(mon_item_weights.values())

    yield_rows = []
    for item in scrap_items:
        w = mon_item_weights[item]
        pct = (w / total_3_items_kg * 100) if total_3_items_kg > 0 else 0.0
        yield_rows.append((item.title(), f"{w:,.1f} Kg | Yield: {pct:.2f}%"))

    # 👇 Yahan se 4 space (indentation) zaroori hai
    d_item_w = {it: float(d_day.loc[d_day[item_col] == it, "kg"].sum()) for it in scrap_items}
    d_total = sum(d_item_w.values())
    day_yield_rows = [(it.title(), f"{w:,.1f} Kg | Yield: {(w/d_total*100 if d_total else 0):.2f}%")
                      for it, w in d_item_w.items()]

    # --- Card Return ---
    return {
        "value": f"{day_kg:,.1f} Kg | {day_bdls:,} Bdls",
        "desc": f"Scrap production (O Shed) · {day:%d-%b-%Y}",
        "color": BLUE,
        "metrics": [
            (f"{day_kg:,.1f}", "Day Kg"),
            (f"{day_bdls:,}", "Day Bdls"),
            (f"{mon_kg:,.1f}", f"Month Kg ({day:%b})"),
            (f"{mon_bdls:,}", f"Month Bdls ({day:%b})"),
        ],
        "details": [
            (f"🗓 Month-wise Breakdown ({day:%b-%y})", month_breakdown_rows),
            (f"⚖ Scrap Items Yield (Month {day:%b-%y})", yield_rows),
            (f"📅 Scrap Items Yield (Day {day:%d-%m-%y})", day_yield_rows)
        ]
    }



def pillow_card(day):
    """Pillow button: selected date, selected month aur total (April se last date tak)."""
    y_df, err, _ = get_sheet("prod_summary")
    if y_df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    # Sirf K Shed (Bundles '26-K' se shuru hone wale) filter karein
    b = y_df["BUNDLES"].astype(str).str.strip().str.upper()
    p = y_df[b.str.match(r"^\d{2}-K")]
    
    if p.empty:
        return {"value": "No Data", "desc": "No 26-K pillow row found in Prod. Summary", "color": GREY}

    m_start, m_end = _month_range(day)
    d_day = pillow_agg(p[p["_date"] == day])
    d_mon = pillow_agg(p[(p["_date"] >= m_start) & (p["_date"] <= m_end)])
    d_all = pillow_agg(p)
    first, last = p["_date"].min(), p["_date"].max()

    def rows(a):
        return [("Bundles", f"{a['bdl']:,}"), ("Sheets", f"{a['sheets']:,.0f}"), ("Weight", f"{a['kg']:,.1f} Kg")]

    return {
        "value": pillow_txt(d_day),
        "desc": "Pillow production (K Shed only)",
        "color": BLUE,
        "metrics": [(f"{d_day['bdl']:,}", "Bundles"), (f"{d_day['sheets']:,.0f}", "Sheets"),
                    (f"{d_day['kg']:,.1f}", "Kg")],
        "sections": [(f"🗓 Month {day:%b-%y}", rows(d_mon))],
        "details": [(f"📆 Total ({first:%d-%m-%y} to {last:%d-%m-%y})", rows(d_all))],
    }


def mattress_card(day):
    """Mattress: production (bundles / sheets / weight) Prod. Summary se (H+M combined), Yield M-Shed se."""
    y_df, err, _ = get_sheet("prod_summary")
    if y_df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    
    # 1. H-Shed aur M-Shed ka Production data (Bundles, Pcs, Weight) Prod. Summary file se
    # H-Shed wali rows (jisme BUNDLES '26-H' se shuru hota hai)
    h = shed_rows(y_df, "H")
    
    # M-Shed wali rows (Prod. Summary mein jinke BUNDLES '26-M' se shuru hote hain)
    m_rows = y_df[y_df["BUNDLES"].astype(str).str.upper().str.startswith("26-M", na=False)]
    
    # Dono ko mila dein (H + M)
    combined_prod = pd.concat([h, m_rows], ignore_index=True)
    
    m_start, m_end = _month_range(day)
    
    # Din ka production
    a_day = pillow_agg(combined_prod[combined_prod["_date"] == day])
    # Mahine ka production
    a_mon = pillow_agg(combined_prod[(combined_prod["_date"] >= m_start) & (combined_prod["_date"] <= m_end)])
    # Total production
    a_all = pillow_agg(combined_prod)

    # 2. Yield M-Shed (4) file se
    m_df, m_err, _ = get_sheet("m_yield")
    
    dy = None
    if m_df is not None:
        m_day_data = m_df[m_df["_date"] == day]
        if not m_day_data.empty and m_day_data["kg"].sum() > 0:
            dy = d_yield(m_df, day, day)
                
    my = d_yield(m_df, m_start, m_end) if m_df is not None else None

    def ys(r):
        return f"{r['pct']:.2f}%" if r else "no data"

    def rows(a):
        return [
            ("Bundles", f"{a['bdl']:,}"), 
            ("Sheets", f"{a['sheets']:,.0f}"), 
            ("Weight", f"{a['kg'] / 1000:,.3f} Tons")
        ]

    details = []
    if not combined_prod.empty:
        details.append((f"📆 Total ({combined_prod['_date'].min():%d-%m-%y} to {combined_prod['_date'].max():%d-%m-%y})", 
                        rows(a_all)))
    if dy:
        details.append((f"⚖ M Shed grade-wise · {day:%d-%m-%y}",
                        [(k.title(), f"{v:,.1f} kg") for k, v in dy["by_item"].items() if v > 0]))

    return {
        "value": f"{ys(dy)} Yield | {a_day['bdl']:,} Bdls | {a_day['sheets']:,.0f} Sheets",
        "desc": "Mattress production (H + M shed) & yield (M shed)" if m_df is not None
                else f"⚠ M-Shed yield not found: {m_err}",
        "color": BLUE if m_df is not None else AMBER,
        "metrics": [
            (f"{dy['pct']:.2f}%" if dy else "—", "Yield", "yield"),
            (f"{a_day['bdl']:,}", "Bundles"), 
            (f"{a_day['sheets']:,.0f}", "Sheets"),
            (f"{a_day['kg'] / 1000:,.3f}", "Total Tons"),
        ],
        "sections": [(f"🗓 Month {day:%b-%y}", [("Yield", ys(my))] + rows(a_mon))],
        "details": details,
    }


def yield_card(day):
    """Total Production & Yield: selected date, selected month, saal ka total (month-wise list nahi)."""
    y_df, err, _ = get_sheet("prod_summary")
    if y_df is None:
        return {"value": "0.00 %", "desc": f"Data error: {err}", "color": RED}

    ym = day.year * 100 + day.month
    month = y_df[y_df["ym"] == ym]                      # selected month (poora)
    if month.empty or month["kg"].sum() == 0:
        return {"value": "0.00 %", "desc": f"No data for {day:%b-%Y}", "color": GREY}
    mt = _grade_table(month)

    upto = y_df[(y_df["ym"] <= ym) & (y_df["_date"] >= YIELD_START)]     # April se selected month tak
    yt = _grade_table(upto)

    dfr = y_df[y_df["_date"] == day]                    # selected date
    dt = _grade_table(dfr) if (not dfr.empty and dfr["kg"].sum() > 0) else None

    def grade_rows(t):
        return [("1st Grade", f"{t['pct'][1]:.2f}%"), ("2nd Grade", f"{t['pct'][2]:.2f}%"),
                ("3rd Grade", f"{t['pct'][3]:.2f}%"), ("Production", f"{t['total'] / 1000:,.1f} Tons"),
                ("Bundles", f"{t['bdl_total']:,}  (1st {t['bdl'][1]:,} · 2nd {t['bdl'][2]:,} · 3rd {t['bdl'][3]:,})")]

    p = mt["pct"]
    details = []
    if dt:
        details.append((f"📅 {day:%d-%m-%y}", grade_rows(dt)))
    details.append((f"🗓 Month {day:%b-%y}", grade_rows(mt)))
    details.append((f"📆 Year total (Apr to {day:%b-%y})", grade_rows(yt)))
    return {
        "value": f"{p[1]:,.2f} %",
        "desc": "1st Grade yield & production",
        "color": BLUE,
        "metrics": [
            (f"{dt['pct'][1]:.2f}%" if dt else "—", f"Yield {day:%d-%m}", "yield"),
            (f"{p[1]:.2f}%", f"Yield {day:%b-%y}", "yield"),
            (f"{mt['total'] / 1000:,.1f}", f"Tons {day:%b-%y}"),
        ],
        "details": details,
    }


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_shed_cached(files):
    """D/E shed jaisi files (Date=col C, Type=col D, Value=col E) jodta hai."""
    def _to_date(v):
        if isinstance(v, (datetime.datetime, pd.Timestamp)):
            return v.date()
        if isinstance(v, datetime.date):
            return v
        d = _parse_dates(pd.Series([str(v)]), True).iloc[0]
        return d.date() if pd.notna(d) else None

    
    frames = []
    for shed, path, sheet in files:
        raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object, engine="openpyxl")
        t = pd.DataFrame({
            "shed": shed,
            "_date": raw.iloc[:, 2].apply(_to_date),
            "type": raw.iloc[:, 3].astype(str).str.strip().str.upper(),
            "val": _num(raw.iloc[:, 4]).fillna(0),
        })
        frames.append(t.dropna(subset=["_date"]))
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        raise DataError("No valid date found in shed files")
    return df, datetime.datetime.now(IST)


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_rolls_cached(files):
    """B-Shed aur C-Shed ki files padhkar ek table banata hai. files = ((shed, path, sheet), ...)"""
    def _to_date(v):
        if isinstance(v, (datetime.datetime, pd.Timestamp)):
            return v.date()
        if isinstance(v, datetime.date):
            return v
        d = _parse_dates(pd.Series([str(v)]), True).iloc[0]
        return d.date() if pd.notna(d) else None

    frames = []
    for shed, path, sheet in files:
        raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object, engine="openpyxl")
        t = pd.DataFrame({
            "shed": shed,
            "_date": raw.iloc[:, 2].apply(_to_date),
            "type": raw.iloc[:, 3].astype(str).str.strip().str.upper(),
            "val": _num(raw.iloc[:, 4]).fillna(0),
        })
        frames.append(t.dropna(subset=["_date"]))   # header row apne aap hat jayegi
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        raise DataError("No valid date found in B/C shed files")
    return df, datetime.datetime.now(IST)


# ---------------- D+E SHED YIELD (1st Grade weight / total weight x 100) ----------------
D_YIELD_EXCLUDE = []          # total se kuch item hatane ho to yahan likho, e.g. ["DC GRADE"]
D_YIELD_FIRST = "1ST GRADE"


def _parse_mixed_dates(s):
    """'01-Apr-25', '01-04-2025', '2025-04-01 00:00:00' sab format ek hi column mein chalte hain."""
    s = s.astype(str).str.strip()
    d = pd.to_datetime(s, format="%d-%b-%y", errors="coerce")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        m = d.isna()
        if not m.any():
            break
        d[m] = pd.to_datetime(s[m], format=fmt, errors="coerce")
    return d


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_m_shed_custom(url):
    """M-Shed file ko seedha column index se padhta hai (C=Date, D=Item, E=Weight)"""
    src = io.BytesIO(_http_get(_direct_url(url))) if re.match(r"^https?://", url or "") else url
    xl = pd.ExcelFile(src, engine="openpyxl")
    tab = "M-Shed" if "M-Shed" in xl.sheet_names else xl.sheet_names[0]
    
    # header=None taaki headers ki wajah se data skip na ho
    raw = xl.parse(tab, dtype=object, header=None)
    
    # Date column (Index 2 = Column C), Item (Index 3 = Column D), Weight (Index 4 = Column E)
    d = _parse_mixed_dates(raw.iloc[:, 2])
    item = raw.iloc[:, 3].astype(str).str.strip().str.upper().str.replace(r"\s+", " ", regex=True)
    kg = _num(raw.iloc[:, 4]).fillna(0.0)
    
    t = pd.DataFrame({
        "shed": "M Shed",
        "_date": d.dt.date,
        "item": item,
        "kg": kg,
    })
    
    # Blank rows aur header text ko hatao
    t = t.dropna(subset=["_date"])
    t = t[(t["item"] != "") & (t["item"] != "NAN") & (t["item"] != "ITEM") & (t["item"] != "NONE")]
    
    return t, datetime.datetime.now(IST)
def _fetch_dyield_cached(files):
    """Yield files (DATE, ITEM, <X>-SHED) jodkar ek table banata hai.
    files = (("D Shed", url), ("F Shed", url, "F-Shed"), ...). 3rd cheez = sheet(tab) ka naam (na ho to pehli tab).
    Header row apne aap dhoondhi jaati hai (jis row mein DATE likha ho)."""
    frames = []
    for item in files:
        shed, url = item[0], item[1]
        want_tab = item[2] if len(item) > 2 else None
        src = io.BytesIO(_http_get(_direct_url(url))) if re.match(r"^https?://", url or "") else url
        is_csv = str(url).lower().split("?")[0].endswith(".csv")
        if is_csv:
            raw0 = pd.read_csv(src, dtype=str, header=None)
        else:
            xl = pd.ExcelFile(src, engine="openpyxl")
            tab = want_tab if want_tab in xl.sheet_names else xl.sheet_names[0]
            raw0 = xl.parse(tab, dtype=object, header=None)
        hdr = next((i for i in range(min(15, len(raw0)))
                    if any(str(c).strip().upper() == "DATE" for c in raw0.iloc[i].tolist())), None)
        if hdr is None:
            raise DataError(f"{shed} yield file mein 'DATE' header row not found")
        raw = raw0.iloc[hdr + 1:].copy()
        raw.columns = [re.sub(r"\s+", " ", str(c).strip().upper()) for c in raw0.iloc[hdr].tolist()]
        date_col = next((c for c in raw.columns if c == "DATE"), None)
        item_col = next((c for c in raw.columns if c == "ITEM"), None)
        val_col = next((c for c in raw.columns if "SHED" in c), None)
        if not all([date_col, item_col, val_col]):
            raise DataError(f"{shed} yield file mein DATE / ITEM / SHED columns nahi mile. "
                            f"Found: {list(raw.columns)}")
        d = _parse_mixed_dates(raw[date_col])
        t = pd.DataFrame({
            "shed": shed,
            "_date": d.dt.date,
            "item": raw[item_col].astype(str).str.strip().str.upper().str.replace(r"\s+", " ", regex=True),
            "kg": _num(raw[val_col]).fillna(0.0),
        })
        frames.append(t[d.notna() & (t["item"] != "") & (t["item"] != "NAN")])
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        raise DataError("No valid date found in yield files")
    return df, datetime.datetime.now(IST)


def d_yield(y_df, start, end, shed=None):
    """[start, end] ka 1st grade yield %. shed=None => D+E combined. Data na ho to None."""
    s = y_df[(y_df["_date"] >= start) & (y_df["_date"] <= end)]
    if shed:
        s = s[s["shed"] == shed]
    s = s[~s["item"].isin(D_YIELD_EXCLUDE)]
    total = float(s["kg"].sum())
    if total <= 0:
        return None
    first = float(s.loc[s["item"] == D_YIELD_FIRST, "kg"].sum())
    return {"pct": first / total * 100, "first": first, "total": total,
            "by_item": s.groupby("item")["kg"].sum().sort_values(ascending=False)}


def d_yield_text(day, sheet="d_yield", label="D+E"):
    """Card ki extra lines: combined yield (bold, sabse upar), phir shed-wise, grade-wise, month-wise.
    D+E ke liye sheet="d_yield", B+C ke liye sheet="bc_yield"."""
    y_df, err, _ = get_sheet(sheet)
    if y_df is None:
        return f"Yield: data error ({err})"

    def fmt(r):
        return f"{r['pct']:.2f}%" if r else "no data"

    m_start = day.replace(day=1)
    m_end = (m_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    dy, my = d_yield(y_df, day, day), d_yield(y_df, m_start, m_end)

    # din ki yield ab upar bold value line mein jaati hai; yahan sirf mahine ki yield
    lines = [f"<b>1st Grade Yield ({label}) {day:%b-%y}: {fmt(my)}</b>"]

    for shed in (sorted(y_df["shed"].unique()) if y_df["shed"].nunique() > 1 else []):
        sd = d_yield(y_df, day, day, shed)
        sm = d_yield(y_df, m_start, m_end, shed)
        lines.append(f"{shed}: {day:%d-%m} {fmt(sd)} | {day:%b-%y} {fmt(sm)}")

    if dy:
        lines.append(f"{day:%d-%m} grade-wise (kg): " + " | ".join(
            f"{k.title()} {v:,.1f}" for k, v in dy["by_item"].items() if v > 0))
    if my:
        lines.append(f"{day:%b-%y}: 1st Grade {my['first']:,.0f} / Total {my['total']:,.0f} kg")

    fy_year = day.year if day.month >= 4 else day.year - 1
    months = []
    for k in range(12):
        y, m = (fy_year + (3 + k) // 12, (3 + k) % 12 + 1)
        ms = datetime.date(y, m, 1)
        if ms > m_start:
            break
        me = (ms.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
        r = d_yield(y_df, ms, me)
        if r:
            months.append(f"{ms:%b} {r['pct']:.1f}%")
    if months:
        lines.append(f"Month-wise yield ({label}): " + " | ".join(months))
    return "<br>".join(lines)


def shed_card(df, day, kind, y_sheet, label):
    """D+E (kind="bdls") aur B+C (kind="rolls") ka card: selected date, selected month, shed-wise, grade-wise."""
    def tot(d, typ):
        return float(d.loc[d["type"] == typ, "val"].sum())

    def txt(d):
        if kind == "bdls":
            return f"{tot(d, 'BUNDLES'):,.0f} Bdls · {tot(d, 'PRODUCTION') / 1000:,.2f} Tons"
        return (f"{tot(d, 'ROLLS'):,.0f} Rolls · {tot(d, 'METERS'):,.0f} Mtr · "
                f"{tot(d, 'PRODUCTION') / 1000:,.2f} Tons")

    m_start, m_end = _month_range(day)
    d_day = df[df["_date"] == day]
    d_mon = df[(df["_date"] >= m_start) & (df["_date"] <= m_end)]

    y_df, _yerr, _ = get_sheet(y_sheet)

    def yld(a, b, shed=None):
        return d_yield(y_df, a, b, shed) if y_df is not None else None

    def ys(r):
        return f"{r['pct']:.2f}%" if r else "no data"

    dy, my = yld(day, day), yld(m_start, m_end)

    if kind == "bdls":
        tiles = [(f"{tot(d_day, 'BUNDLES'):,.0f}", "Bdls"), (f"{tot(d_day, 'PRODUCTION') / 1000:,.2f}", "Tons")]
    else:
        tiles = [(f"{tot(d_day, 'ROLLS'):,.0f}", "Rolls"), (f"{tot(d_day, 'METERS'):,.0f}", "Mtr"),
                 (f"{tot(d_day, 'PRODUCTION') / 1000:,.2f}", "Tons")]
    tiles.append((f"{dy['pct']:.2f}%" if dy else "—", "Yield", "yield"))

    sheds = sorted(df["shed"].unique())
    day_rows = [(sh, f"{txt(d_day[d_day['shed'] == sh])} · {ys(yld(day, day, sh))}") for sh in sheds]
    mon_rows = [("Total", txt(d_mon)), (f"Yield ({label})", ys(my))]
    mon_shed_rows = [(sh, f"{txt(d_mon[d_mon['shed'] == sh])} · {ys(yld(m_start, m_end, sh))}") for sh in sheds]

    sections = [(f"🗓 Month {day:%b-%y}", mon_rows)]
    details = [(f"📅 {day:%d-%m-%y} · Shed wise", day_rows), (f"🗓 Month {day:%b-%y} · Shed wise", mon_shed_rows)]
    if dy:
        details.append((f"⚖ Grade-wise weight · {day:%d-%m-%y}",
                        [(k.title(), f"{v:,.1f} kg") for k, v in dy["by_item"].items() if v > 0]))
    b = tot(d_day, "BUNDLES" if kind == "bdls" else "ROLLS")
    return {
        "value": " | ".join(f"{t[0]} {t[1]}" for t in tiles),
        "desc": f"Selected date total ({label} shed)",
        "color": BLUE,
        "metrics": tiles,
        "sections": sections,
        "details": details,
    }
# ====================================================================
# TONNAGE FOAMING: daily chemical-consumption files (chemicals = rows, dates = columns)
# ====================================================================
@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_chem_daily_cached(files):
    """files = ((url,), (url2,), ...) ya ((url, "tab name"), ...). Har file ek mahine ki daily consumption.
    Header row = jis row ke pehle cell mein 'CHEMICALS' likha ho. Output: chem, _date, kg."""
    frames = []
    for item in files:
        url = item[0]
        want_tab = item[1] if len(item) > 1 else None
        src = io.BytesIO(_http_get(_direct_url(url))) if re.match(r"^https?://", url or "") else url
        if str(url).lower().split("?")[0].endswith(".csv"):
            raw = pd.read_csv(src, dtype=str, header=None, encoding="utf-8-sig")
        else:
            xl = pd.ExcelFile(src, engine="openpyxl")
            tab = want_tab if want_tab in xl.sheet_names else xl.sheet_names[0]
            raw = xl.parse(tab, dtype=object, header=None)
        hdr = next((i for i in range(min(15, len(raw)))
                    if str(raw.iloc[i, 0]).strip().upper() == "CHEMICALS"), None)
        if hdr is None:
            raise DataError(f"'CHEMICALS' header row not found in Tonnage file: {url}")
        dates = _parse_mixed_dates(pd.Series(raw.iloc[hdr, 2:].tolist()))
        body = raw.iloc[hdr + 1:]
        names = (body.iloc[:, 0].astype(str).str.strip().str.upper()
                 .str.replace(r"\s+", " ", regex=True))
        keep = ~names.isin(["", "NAN", "NONE"])
        body, names = body[keep], names[keep]
        parts = []
        for j in range(len(dates)):
            dt = dates.iloc[j]
            if pd.isna(dt) or 2 + j >= body.shape[1]:
                continue
            parts.append(pd.DataFrame({
                "chem": names.values,
                "_date": dt.date(),
                "kg": _num(body.iloc[:, 2 + j]).fillna(0.0).values,
            }))
        if not parts:
            continue
        f = pd.concat(parts, ignore_index=True)
        f["chem"] = f["chem"].replace({"GRAND TOTAL": "GRAND TOTAL", "TOTAL": "GRAND TOTAL"})
        if "GRAND TOTAL" not in set(f["chem"]):          # Grand Total row na ho to khud jod do
            s = f.groupby("_date", as_index=False)["kg"].sum()
            s["chem"] = "GRAND TOTAL"
            f = pd.concat([f, s], ignore_index=True)
        frames.append(f)
    if not frames:
        raise DataError("No valid date found in tonnage daily files")
    return pd.concat(frames, ignore_index=True), datetime.datetime.now(IST)


def _tonnage_net(frame):
    """Formula: TOTAL - (ADDTIVE 90250 x 2.5 + MCL (METHYLENE CHLORIDE)). Data na ho to None."""
    if frame is None or frame.empty:
        return None
    g = frame.groupby("chem")["kg"].sum()
    total = float(g.get("GRAND TOTAL", 0.0))
    add = float(sum(v for k, v in g.items() if str(k).startswith("ADDTIVE 90250")))
    mcl = float(sum(v for k, v in g.items() if str(k).startswith("MCL")))
    return {"total": total, "add": add, "mcl": mcl, "net": total - (add * 2.5 + mcl)}


def tonnage_card(day):
    """Tonnage Foaming: selected din ki consumption + mahine ka total (daily file se, warna monthly sheet se).
    Daily file par formula: TOTAL - (ADDTIVE 90250 x 2.5 + MCL)  (din ka bhi aur mahine ka bhi)."""
    d_df, d_err, _ = get_sheet("foaming_daily")
    m_df, m_err, _ = get_sheet("foaming_chemicals")
    m_start, m_end = _month_range(day)
    day_val = month_val = None
    n_days = 0
    src = ""
    chem = None
    f_day = f_mon = None
    if d_df is not None:
        tot = d_df[d_df["chem"] == "GRAND TOTAL"]
        f_day = _tonnage_net(d_df[d_df["_date"] == day])
        f_mon = _tonnage_net(d_df[(d_df["_date"] >= m_start) & (d_df["_date"] <= m_end)])
        if f_day and f_day["total"] > 0:
            day_val = f_day["net"]
        if f_mon and f_mon["total"] > 0:
            month_val = f_mon["net"]
            t_mon = tot[(tot["_date"] >= m_start) & (tot["_date"] <= m_end)]
            n_days = int((t_mon.groupby("_date")["kg"].sum() > 0).sum())
            src = "daily"
        chem = d_df[d_df["chem"] != "GRAND TOTAL"]
    if month_val is None and m_df is not None and "CONS" in m_df.columns:
        sub = m_df[m_df["_date"].apply(lambda d: d.year == day.year and d.month == day.month)]
        if not sub.empty:
            month_val = float(_num(sub["CONS"]).sum())
            src = "monthly"
    if month_val is None and day_val is None:
        return None

    # Tiles ko update karein
    tiles = [
        (f"{day_val:,.0f}" if day_val is not None else "—", f"{day:%d-%m} Kg"),
    ]
    if month_val is not None:
        tiles += [
            (f"{month_val:,.0f}", f"{day:%b-%y} Kg"),
            (f"{month_val / 1000:,.1f}", f"Tons {day:%b-%y}")
        ]

    if src == "daily":
        desc = f"Consumption {day:%b-%Y} · {n_days} working days · avg {month_val / max(n_days, 1):,.0f} kg/day"
    else:
        desc = f"Consumption for {day:%b-%Y} (monthly total, daily data not added)"

    details = []
    for lbl, f in ((f"📅 {day:%d-%m-%y} · Formula", f_day), (f"🗓 Month {day:%b-%y} · Formula", f_mon)):
        if f and f["total"] > 0:
            details.append((lbl, [
                ("Total chemicals", f"{f['total']:,.0f} kg"),
                ("Additive 90250 x 2.5", f"- {f['add'] * 2.5:,.0f} kg  ({f['add']:,.0f} x 2.5)"),
                ("MCL", f"- {f['mcl']:,.0f} kg"),
                ("Net tonnage", f"{f['net']:,.0f} kg")]))
    if chem is not None and not chem.empty:
        c_day = chem[chem["_date"] == day].groupby("chem")["kg"].sum().sort_values(ascending=False)
        c_day = c_day[c_day > 0]
        if not c_day.empty:
            details.append((f"📅 {day:%d-%m-%y} · Chemical wise",
                            [(k.title(), f"{v:,.0f} kg") for k, v in c_day.items()]))
        c_mon = (chem[(chem["_date"] >= m_start) & (chem["_date"] <= m_end)]
                 .groupby("chem")["kg"].sum().sort_values(ascending=False))
        c_mon = c_mon[c_mon > 0]
        if not c_mon.empty:
            details.append((f"🗓 Month {day:%b-%y} · Chemical wise",
                            [(k.title(), f"{v:,.0f} kg") for k, v in c_mon.items()]))
    return {
        "value": f"{(month_val if month_val is not None else day_val):,.0f}",
        "desc": desc,
        "color": BLUE,
        "metrics": tiles,
        "details": details,
    }
def stock_balance_card(df, day, issued_col, label):
    """TDI / POP / POLYOL: Balance as on selected date, with EXACT TOTAL In/Out totals."""
    def find(*names):
        want = {re.sub(r"[^A-Z0-9]", "", n.upper()) for n in names}
        for c in df.columns:
            if re.sub(r"[^A-Z0-9]", "", str(c).upper()) in want:
                return c
        return None

    c_bal = find("Balance Qty")
    c_rec = find("Recd Qty")
    c_iss = find(issued_col, "Issued Qty", "Issues Qty")
    c_typ = find("Vech Type", "Vch Type", "Voucher Type")
    
    if not c_bal or not c_rec or not c_iss:
        raise DataError(f"{label} columns not found.")

    # 1. Selected Date tak ka Balance (Sabse aakhri valid balance)
    sub = df[df["_date"] <= day].copy()
    sub["_b"] = _num(sub[c_bal])
    sub = sub[sub["_b"].notna()]
    if sub.empty:
        return None
        
    valid_bal_rows = sub[sub["_b"] > 0]
    if not valid_bal_rows.empty:
        last = valid_bal_rows.iloc[-1]
    else:
        last = sub.iloc[-1]
        
    balance = float(last["_b"])
    last_dt = last["_date"]

    # 2+3. Month ka window: month ki AAKHRI "OPN." row se shuru (purani/duplicate rows ignore)
    month_data = df[(df["_date"] >= day.replace(day=1)) & (df["_date"] <= day)].copy()
    opening = None
    if c_typ is not None and not month_data.empty:
        typ = month_data[c_typ].astype(str).str.strip().str.upper()
        opn = typ.str.startswith("OPN").tolist()
        if any(opn):
            start = len(opn) - 1 - opn[::-1].index(True)
            opening = float(_num(pd.Series([month_data.iloc[start][c_rec]])).fillna(0).iloc[0])
            month_data = month_data.iloc[start:]
            typ = typ.iloc[start:]
        month_data = month_data[~typ.str.startswith("OPN")]

    day_data = month_data[month_data["_date"] == day]
    d_in = float(_num(day_data[c_rec]).fillna(0).sum()) if not day_data.empty else 0.0
    d_out = float(_num(day_data[c_iss]).fillna(0).sum()) if not day_data.empty else 0.0
    t_in = float(_num(month_data[c_rec]).fillna(0).sum())
    t_out = float(_num(month_data[c_iss]).fillna(0).sum())

    if last_dt == day:
        note = f"Balance as on {day.strftime('%d-%b-%Y')}"
    else:
        note = f"Balance as of last entry {last_dt.strftime('%d-%b-%Y')}"

    sections = [
        (f"🗓 Month Total ({day:%b-%y})", [
            ("Recd (In)", f"{t_in:,.2f} Kg"),
            ("Issued (Out)", f"{t_out:,.2f} Kg")
        ]),
        (f"📅 Today ({day:%d-%m-%y})", [
            ("Recd (In)", f"+{d_in:,.0f} Kg"),
            ("Issued (Out)", f"-{d_out:,.0f} Kg")
        ])
    ]
    if opening is not None:
        calc_bal = opening + t_in - t_out
        if abs(calc_bal - balance) > 1:
            sections.append(("⚠ Check: sheet balance does not match", [
                ("Sheet balance", f"{balance:,.0f} Kg"),
                ("Opening + In - Out", f"{calc_bal:,.0f} Kg"),
            ]))

    return {
        "value": f"{balance:,.2f} Kg",
        "desc": note,
        "color": RED if balance < 0 else BLUE,
        "sections": sections,
    }
def pending_vs_completed_card(sheet_key, day, label):
    """Sheet mein name column + STATUS column chahiye. Status = Completed / Pending."""
    df, err, _ = get_sheet(sheet_key)
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    cols = [c for c in df.columns if not str(c).startswith("_")]
    norm = lambda s: re.sub(r"[^A-Z]", "", str(s).upper())
    c_name = next((c for c in cols if norm(c) in ("PROJECT", "PROJECTNAME", "PRODUCT", "PRODUCTNAME", "ITEM", "NAME")), None)
    c_stat = next((c for c in cols if norm(c) == "STATUS"), None)
    if not c_name or not c_stat:
        return {"value": "Config error", "desc": f"Name / Status column not found: {cols}", "color": RED}

    w = pd.DataFrame({"name": df[c_name].astype(str).str.strip(),
                      "status": df[c_stat].astype(str).str.strip().str.upper()})
    w = w[(w["name"] != "") & (w["name"].str.lower() != "nan")]
    is_done = w["status"].isin(["COMPLETED", "COMPLETE", "DONE"])
    done, pend = w[is_done], w[~is_done]
    total = len(w)
    pct = (len(done) / total * 100) if total else 0.0

    return {
        "value": f"{len(done)} / {total}",
        "desc": f"{label} · {pct:.0f}% completed",
        "color": BLUE if pct >= 80 else (AMBER if pct >= 50 else RED),
        "metrics": [
            (f"{pct:.0f}%", "Completed", "yield"),
            (f"{total}", "Total"),
            (f"{len(done)}", "Completed"),
            (f"{len(pend)}", "Pending"),
        ],
        "details": [
            (f"⏳ Pending ({len(pend)})", [(r["name"], r["status"] or "Pending") for _, r in pend.iterrows()] or [("Nothing pending", "✅")]),
            (f"✅ Completed ({len(done)})", [(r["name"], "Done") for _, r in done.iterrows()] or [("None right now", "-")]),
        ],
    }
_DSP_ORDER = ["April", "May", "June", "July", "August", "September", "October", "November", "December",
              "January", "February", "March"]


def _dsp_prepare(df):
    w = df.copy()
    w.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in w.columns]
    low = {c.lower(): c for c in w.columns}
    party, month = low.get("party name"), low.get("month")
    c1, c2 = low.get("91-180 days"), low.get("181-270 days")
    if not (party and month and c1 and c2):
        return None, f"Columns not found: {list(w.columns)}"
    out = pd.DataFrame({
        "party": w[party].astype(str).str.strip(),
        "month": w[month].astype(str).str.strip().str.title(),
        "a": pd.to_numeric(w[c1].astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(0.0),
        "b": pd.to_numeric(w[c2].astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(0.0),
    })
    out = out[(out["party"] != "") & (out["party"].str.lower() != "nan")]
    return out, None


def _dsp_month_dates(df):
    """Month dropdown ke liye: sheet ke har month ki ek date (FY April-26 se March-27)."""
    w, _e = _dsp_prepare(df)
    if w is None:
        return [datetime.datetime.now(IST).date()]
    out = []
    for m in w["month"].unique():
        if m in _DSP_ORDER:
            n = _DSP_ORDER.index(m) + 4
            n = n - 12 if n > 12 else n
            out.append(datetime.date(2026 if n >= 4 else 2027, n, 1))
    return sorted(out, reverse=True) or [datetime.datetime.now(IST).date()]


def finance_dispute_card(day):
    df, err, _ = get_sheet("dispute_cases")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    w, err = _dsp_prepare(df)
    if w is None:
        return {"value": "Config error", "desc": err, "color": RED}
    mname = day.strftime("%B")
    m = w[w["month"] == mname].copy()
    if m.empty:
        return {"value": "0", "desc": f"{mname} has no dispute data", "color": GREY}
    m["t"] = m["a"] + m["b"]
    tot, ta, tb = m["t"].sum(), m["a"].sum(), m["b"].sum()
    ca, cb = int((m["a"] > 0).sum()), int((m["b"] > 0).sum())
    cases = int((m["t"] > 0).sum())
    top = m[m["t"] > 0].sort_values("t", ascending=False).head(15)
    top_rows = [(r.party, f"{_cm_amt(r.t)} (91-180: {_cm_amt(r.a)} | 181-270: {_cm_amt(r.b)})") for r in top.itertuples()]
    trend = []
    for mn in _DSP_ORDER:
        x = w[w["month"] == mn]
        if x.empty:
            continue
        t = x["a"] + x["b"]
        trend.append((mn, f"{_cm_amt(t.sum())} | {int((t > 0).sum())} cases"))
    return {
        "value": _cm_amt(tot),
        "desc": f"Dispute cases · {mname} · {cases} parties",
        "color": BLUE,
        "metrics": [
            (_cm_amt(tot), "Total Value"), (f"{cases}", "Total Cases"),
            (_cm_amt(ta), "91-180 Days"), (f"{ca}", "91-180 Cases"),
            (_cm_amt(tb), "181-270 Days"), (f"{cb}", "181-270 Cases"),
        ],
        "details": [
            (f"🔝 Top 15 Parties · {mname}", top_rows),
            ("📊 Month-wise (Value | Cases)", trend),
        ],
    }

# ====================================================================
# HR (Google Sheet "Publish to web" se): Manpower, Overtime, Staff/Helper/Supervisor %, Dept-wise
# ====================================================================
# Teeno ke link alag-alag (Google Sheet > Publish to web wale link)
HR_PUB_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQSzgc1P_NlZIKyfqO1IEhn2DinG1MlWTGYXsl7WLsQe-hQJa5iDClXRZReUAIkHg/pubhtml"
HR_OT_PUB_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQSzgc1P_NlZIKyfqO1IEhn2DinG1MlWTGYXsl7WLsQe-hQJa5iDClXRZReUAIkHg/pubhtml"
HR_STAFF_PUB_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQSzgc1P_NlZIKyfqO1IEhn2DinG1MlWTGYXsl7WLsQe-hQJa5iDClXRZReUAIkHg/pubhtml"
HR_TAB_MANPOWER = "DEPTT"
HR_TAB_OVERTIME = "OVERTIME"
HR_TAB_STAFF = "MASTER"

_HR_MON = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
_HR_FIX = {"PROD MANGER": "PROD MANAGER", "STICHING COVERING": "STICHING & COVERING", "STICHING & COVRING": "STICHING & COVERING",
           "BAILLING": "BAILING", "P P C": "PPC", "H R": "HR", "FIRE ND SAFETY": "FIRE & SAFETY", "FIRE &SAFETY": "FIRE & SAFETY",
           "HOUSKEEPING": "HOUSE KEEPING", "HOUSEKEEPING": "HOUSE KEEPING", "MATERIAL MOVMENT": "MATERIAL MOVEMENT",
           "ECOM": "E COMMERCE", "ACCOUNT": "ACCOUNTS", "MAINT.": "MAINT", "E - SHED": "E SHED", "MOULDING": "MOULD"}
# Staff / Helper / Supervisor ka rule (DESIGNATION ke hisaab se). Badalna ho to yahan badlo.
HR_SUPERVISOR_WORDS = ("SUPERVISOR",)       # SUPERVISOR + ASST SUPERVISOR
HR_HELPER_WORDS = ("HELPER",)               # baaki sab (operator, skilled, manager, gm, guard...) = Staff


def _hr_name(s):
    u = re.sub(r"\s+", " ", str(s).upper().replace(";", " ").replace(".", " ")).strip()
    return _HR_FIX.get(u, u)


def _hr_val(v):
    v = str(v).strip().replace(",", "")
    return float(v) if re.fullmatch(r"-?\d+(\.\d+)?", v) else None


def _hr_tab_rows(pub_url, keyword=""):
    tabs = discover_tabs(pub_url)
    pick = next((g for n, g in tabs if keyword and keyword.upper() in n.upper()), tabs[0][1] if not keyword else None)
    if pick is None:
        raise DataError(f"HR tab '{keyword}' not found. Tabs: {[n for n, _ in tabs]}")
    data = _http_get(pub_url.split("/pub")[0] + f"/pub?output=csv&gid={pick}")
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))


def _hr_parse_manpower(rows):
    """Monthly blocks: title row -> header (1,2,3..) -> department rows -> TOTAL."""
    out, cur, j = [], None, None
    for r in rows:
        c = [str(x).strip() for x in r]
        m = re.search(r"DAILY\s*MAN\s*POWER\s*DETA\w*\s*\(?\s*([A-Z]+)\s*(\d{4})", " ".join(c).upper())
        if m and m.group(1)[:3] in _HR_MON:
            cur, j = (int(m.group(2)), _HR_MON[m.group(1)[:3]]), None
            continue
        if cur is None:
            continue
        if j is None:
            j = next((k for k in range(len(c) - 2) if _hr_val(c[k]) == 1 and _hr_val(c[k + 1]) == 2 and _hr_val(c[k + 2]) == 3), None)
            continue
        name = _hr_name(c[0]) if c else ""
        if name == "TOTAL":
            cur, j = None, None
            continue
        if not name or name.startswith("ABSENT"):
            continue
        tgt = _hr_val(c[3]) if len(c) > 3 else None
        for d in range(1, calendar.monthrange(cur[0], cur[1])[1] + 1):
            k = j + d - 1
            v = _hr_val(c[k]) if k < len(c) else None
            if v is not None:
                out.append({"_date": datetime.date(cur[0], cur[1], d), "dept": name, "man": v, "target": tgt or 0.0})
    df = pd.DataFrame(out, columns=["_date", "dept", "man", "target"])
    if df.empty:
        return df
    df = df.groupby(["_date", "dept"], as_index=False).agg(man=("man", "max"), target=("target", "max"))
    tot = df.groupby("_date")["man"].sum()
    return df[df["_date"].isin(tot[tot > 0].index)]


def _hr_parse_overtime(rows):
    """Monthly blocks: 'LIST OF OVERTIME ... MONTH OF <MONTH> <YEAR>' -> header (1-Jan, 2-Jan..) -> dept rows -> TOTAL."""
    out, year, cols = [], None, None
    for r in rows:
        c = [str(x).strip() for x in r]
        m = re.search(r"MONTH OF\s+([A-Z]+)\s+(\d{4})", " ".join(c).upper())
        if m:
            year, cols = int(m.group(2)), None
            continue
        if year is None:
            continue
        if cols is None:
            found = {}
            for k, h in enumerate(c):
                mm = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})", h)
                if mm and mm.group(2).upper() in _HR_MON:
                    found[k] = (int(mm.group(1)), _HR_MON[mm.group(2).upper()])
            if found:
                cols = found
            continue
        name = _hr_name(c[0]) if c else ""
        if name == "TOTAL":
            year, cols = None, None
            continue
        if not name:
            continue
        for k, (d, mo) in cols.items():
            v = _hr_val(c[k]) if k < len(c) else None
            if v is not None:
                try:
                    out.append({"_date": datetime.date(year, mo, d), "dept": name, "ot": v})
                except ValueError:
                    pass
    df = pd.DataFrame(out, columns=["_date", "dept", "ot"])
    return df.groupby(["_date", "dept"], as_index=False)["ot"].sum() if not df.empty else df


def _hr_parse_staff(rows):
    if not rows:
        return pd.DataFrame(columns=["dept", "grp"])
    head = [re.sub(r"\s+", " ", str(h)).strip().upper() for h in rows[0]]
    if "DESIGNATION" not in head:
        raise DataError(f"DESIGNATION column not found in HR staff sheet: {head}")
    di = head.index("DESIGNATION")
    pi = head.index("DEPARTMENT") if "DEPARTMENT" in head else None
    out = []
    for r in rows[1:]:
        des = str(r[di]).strip().upper() if di < len(r) else ""
        if not des:
            continue
        dept = _hr_name(r[pi]) if pi is not None and pi < len(r) and str(r[pi]).strip() else "UNSPECIFIED"
        grp = ("Supervisor" if any(w in des for w in HR_SUPERVISOR_WORDS)
               else "Helper" if any(w in des for w in HR_HELPER_WORDS) else "Staff")
        out.append({"dept": dept, "grp": grp})
    return pd.DataFrame(out, columns=["dept", "grp"])


@st.cache_data(ttl=600, show_spinner=False)
def hr_manpower_df():
    tabs = discover_tabs(HR_PUB_URL)
    first = [t for t in tabs if HR_TAB_MANPOWER and HR_TAB_MANPOWER.upper() in t[0].upper()]
    for name, gid in first + [t for t in tabs if t not in first]:     # pehle naam wali tab, phir baaki sab tabs
        data = _http_get(HR_PUB_URL.split("/pub")[0] + f"/pub?output=csv&gid={gid}")
        df = _hr_parse_manpower(list(csv.reader(io.StringIO(data.decode("utf-8-sig")))))
        if len(df):
            return df
    raise DataError(f"Manpower data not found in any tab. Tabs: {[n for n, _ in tabs]}")


@st.cache_data(ttl=600, show_spinner=False)
def hr_overtime_df():
    return _hr_parse_overtime(_hr_tab_rows(HR_OT_PUB_URL, HR_TAB_OVERTIME))


@st.cache_data(ttl=600, show_spinner=False)
def hr_staff_df():
    return _hr_parse_staff(_hr_tab_rows(HR_STAFF_PUB_URL, HR_TAB_STAFF))


def _hr_dates_manpower():
    d = hr_manpower_df()
    return sorted(d["_date"].unique(), reverse=True) if len(d) else []


def _hr_dates_overtime():
    d = hr_overtime_df()
    if d.empty:
        return []
    t = d.groupby("_date")["ot"].sum()
    return sorted(t[t > 0].index, reverse=True)


def hrg_manpower_card(day):
    d = hr_manpower_df()
    tot = d.groupby("_date")["man"].sum()
    if day not in tot.index:
        return None
    month = tot[(tot.index >= day.replace(day=1)) & (tot.index <= day)]
    avg = month.mean() if len(month) else 0
    return {"value": f"{tot.loc[day]:,.0f} Present", "desc": f"Monthly avg: {avg:,.1f} per working day",
            "color": BLUE, "extra": f"Working days this month (till date): {len(month)}"}


def hrg_overtime_card(day):
    d = hr_overtime_df()
    if d.empty:
        return None
    tot = d.groupby("_date")["ot"].sum()
    if day not in tot.index or tot.loc[day] <= 0:
        return None
    month = tot[(tot.index >= day.replace(day=1)) & (tot.index <= day) & (tot > 0)]
    avg = month.mean() if len(month) else 0
    return {"value": f"{tot.loc[day]:,.0f} Hrs", "desc": f"Monthly avg: {avg:,.1f} Hrs per working day",
            "color": BLUE, "extra": f"Total OT this month (till date): {month.sum():,.0f} Hrs"}


def hrg_dept_card(day):
    d = hr_manpower_df()
    x = d[d["_date"] == day].sort_values("man", ascending=False)
    if x.empty:
        return None
    ot = hr_overtime_df()
    ot_map = ot[ot["_date"] == day].set_index("dept")["ot"].to_dict() if len(ot) else {}
    present, req = int(x["man"].sum()), int(x["target"].sum())
    rows = []
    for r in x.itertuples():
        t = f" / {int(r.target)} req" if r.target else ""
        o = f" | OT {ot_map[r.dept]:g} Hrs" if ot_map.get(r.dept) else ""
        rows.append((r.dept.title(), f"{int(r.man)} present{t}{o}"))
    top = " | ".join(f"{r.dept.title()}: {int(r.man)}" for r in x.head(3).itertuples())
    return {"value": f"{len(x[x['man'] > 0])} Depts present", "desc": top, "color": BLUE,
            "metrics": [(f"{present}", "Present"), (f"{req}" if req else "-", "Required"), (f"{len(x)}", "Departments")],
            "details": [(f"🏭 Department-wise · {day:%d-%b-%Y}", rows)]}


def hrg_staff_card(day):
    s = hr_staff_df()
    if s.empty:
        return None
    n = len(s)
    cnt = s["grp"].value_counts()
    pct = lambda g: cnt.get(g, 0) / n * 100
    rows = []
    for dp, g in s.groupby("dept"):
        c = g["grp"].value_counts()
        rows.append((dp.title(), f"Helper {c.get('Helper', 0)} | Supervisor {c.get('Supervisor', 0)} | Staff {c.get('Staff', 0)} | Total {len(g)}"))
    return {"value": f"{n} Employees",
            "desc": "Based on employee master (not daily attendance))", "color": BLUE,
            "metrics": [(f"{pct('Helper'):.1f}%", "Helper"), (f"{pct('Supervisor'):.1f}%", "Supervisor"),
                        (f"{pct('Staff'):.1f}%", "Staff"), (f"{n}", "Total")],
            "details": [("🏭 Department-wise (Helper | Supervisor | Staff)", rows)]}
# ===== HR NEW VERSIONS (sir ke changes) - purane hrg_* ke neeche paste karo =====
def hrg_manpower_card(day):
    d = hr_manpower_df()
    tot = d.groupby("_date")["man"].sum()
    if day not in tot.index:
        return None
    m_start, m_end = _month_range(day)
    month = tot[(tot.index >= m_start) & (tot.index <= day) & (tot > 0)]
    full = tot[(tot.index >= m_start) & (tot.index <= m_end) & (tot > 0)]
    avg = month.mean() if len(month) else 0
    rows = [(dt.strftime("%d-%m-%Y"), f"{v:,.0f} Present")
            for dt, v in full.sort_index(ascending=False).items()]
    return {
        "value": f"{tot.loc[day]:,.0f} Present",
        "desc": f"Present on {day:%d-%b-%Y}",
        "color": BLUE,
        "sections": [(f"📊 Monthly Avg · {day:%b-%y}", [
            ("Avg per working day", f"{avg:,.1f}"),
            ("Working days (till date)", f"{len(month)}")])],
        "details": [
            (f"🗓 Month total · {day:%b-%y}", [("Total man-days", f"{full.sum():,.0f}")]),
            (f"📅 Day-wise · {day:%b-%y}", rows),
        ],
    }


def hrg_overtime_card(day):
    d = hr_overtime_df()
    if d.empty:
        return None
    tot = d.groupby("_date")["ot"].sum()
    if day not in tot.index or tot.loc[day] <= 0:
        return None
    m_start, m_end = _month_range(day)
    month = tot[(tot.index >= m_start) & (tot.index <= day) & (tot > 0)]
    full = tot[(tot.index >= m_start) & (tot.index <= m_end) & (tot > 0)]
    avg = month.mean() if len(month) else 0
    day_rows = [(dt.strftime("%d-%m-%Y"), f"{v:,.0f} Hrs")
                for dt, v in full.sort_index(ascending=False).items()]
    dp = d[(d["_date"] >= m_start) & (d["_date"] <= m_end)].groupby("dept")["ot"].sum()
    dp = dp[dp > 0].sort_values(ascending=False)
    dept_rows = [(k.title(), f"{v:,.0f} Hrs") for k, v in dp.items()]
    return {
        "value": f"{tot.loc[day]:,.0f} Hrs",
        "desc": f"Overtime on {day:%d-%b-%Y}",
        "color": BLUE,
        "sections": [(f"📊 Monthly · {day:%b-%y}", [
            ("Avg OT per working day", f"{avg:,.1f} Hrs"),
            ("Month total OT", f"{full.sum():,.0f} Hrs")])],
        "details": [
            (f"🗓 Month total OT · {day:%b-%y}", [("Total OT", f"{full.sum():,.0f} Hrs")]),
            (f"📅 Day-wise OT · {day:%b-%y}", day_rows),
            (f"🏭 Dept-wise OT · {day:%b-%y}", dept_rows + [("TOTAL", f"{dp.sum():,.0f} Hrs")]),
        ],
    }


def hrg_staff_card(day):
    s = hr_staff_df()
    if s.empty:
        return None
    n = len(s)
    cnt = s["grp"].value_counts()
    pct = lambda g: cnt.get(g, 0) / n * 100
    rows = []
    for dp, g in s.groupby("dept"):
        c = g["grp"].value_counts()
        rows.append((dp.title(), f"Helper {c.get('Helper', 0)} | Supervisor {c.get('Supervisor', 0)} | Staff {c.get('Staff', 0)} | Total {len(g)}"))
    return {
        "value": f"{n} Employees",
        "desc": "Based on employee master (not daily attendance)",
        "color": BLUE,
        "metrics": [
            (f"{cnt.get('Helper', 0)}", f"Helper · {pct('Helper'):.1f}%"),
            (f"{cnt.get('Supervisor', 0)}", f"Supervisor · {pct('Supervisor'):.1f}%"),
            (f"{cnt.get('Staff', 0)}", f"Staff · {pct('Staff'):.1f}%"),
            (f"{n}", "Total · 100%"),
        ],
        "details": [("🏭 Department-wise (Helper | Supervisor | Staff)", rows)],
    }


def hrg_dept_card(day):
    d = hr_manpower_df()
    x = d[d["_date"] == day].sort_values("man", ascending=False)
    if x.empty:
        return None
    ot = hr_overtime_df()
    ot_map = ot[ot["_date"] == day].set_index("dept")["ot"].to_dict() if len(ot) else {}
    present, req = int(x["man"].sum()), int(x["target"].sum())
    rows = []
    for r in x.itertuples():
        t = f"{int(r.target)}" if r.target else "-"
        o = f"{ot_map.get(r.dept, 0):g}"
        rows.append((r.dept.title(), f"Present {int(r.man)} | Req {t} | OT {o} Hrs"))
    rows.append(("TOTAL", f"Present {present} | Req {req} | OT {sum(ot_map.values()):g} Hrs"))
    return {
        "value": f"{len(x[x['man'] > 0])} Depts present",
        "desc": f"Department-wise · {day:%d-%b-%Y}",
        "color": BLUE,
        "metrics": [(f"{present}", "Present"), (f"{req}" if req else "-", "Required"), (f"{len(x)}", "Departments")],
        "sections": [(f"🏭 All departments · {day:%d-%b-%Y}", rows)],
        "details": [(f"🏭 Department-wise · {day:%d-%b-%Y}", rows)],
    }
# ===== ORDER MANAGEMENT: PPC WISE (5 clickable blocks) — ADD-ON =====
PPC_NAMES = ["ASHIMA", "DIMPLE", "RAMAN", "SAJID", "SACHIN"]

def _ppc_wise_card(df, day):
    if "ORDER NO" not in df.columns:
        return {"value": "Error", "desc": "ORDER NO column not found", "color": RED}
    tab_col = "TAB_NAME" if "TAB_NAME" in df.columns else "TAB_GID"

    # Orders Left jaisa hi rule: ek ORDER NO = ek order (pehli date wala)
    orders = df[df["ORDER NO"].astype(str).str.strip() != ""].copy()
    orders["ORDER NO"] = orders["ORDER NO"].astype(str).str.strip()
    orders["_sort"] = orders["_date"].apply(lambda x: x if pd.notna(x) else datetime.date.max)
    orders = orders.sort_values("_sort", kind="stable").drop_duplicates("ORDER NO", keep="first")
    orders["_age"] = pd.to_numeric(
        orders["_date"].apply(lambda x: (day - x).days if pd.notna(x) else None), errors="coerce")
    orders["_ppc"] = orders[tab_col].astype(str).str.strip().str.upper()

    qty_col = next((c for c in orders.columns if "QTY" in str(c).upper()), None)

    def rows_for(g):
        g = g.sort_values("_age", ascending=False, na_position="last")
        out = []
        for _, r in g.iterrows():
            party = r.get("PARTY", r.get("PARTY NAME", "Unknown"))
            age = f"{int(r['_age'])} din" if pd.notna(r["_age"]) else "No date"
            q = ""
            if qty_col and str(r.get(qty_col, "")).strip() not in ("", "nan"):
                q = f" · Qty {r[qty_col]}"
            out.append((f"Order {r['ORDER NO']}", f"{party} · {age}{q}"))
        return out

    drill = []
    names = PPC_NAMES + [n for n in orders["_ppc"].unique() if n not in PPC_NAMES and n]  # koi extra tab ho to wo bhi
    for n in names:
        g = orders[orders["_ppc"] == n]
        drill.append((f"👤 {n.title()} — {len(g)} pending", rows_for(g)))

    total = len(orders)
    return {
        "value": f"{total} Orders",
        "desc": "PPC wise pending (Open Anyone's Block)",
        "color": RED if total > 0 else BLUE,
        "drill": drill,
        "drill_heading": "Pending orders (oldest first)",
    }



def compute_kpi(df, spec, day):
    calc = spec.get("calc")
    if calc == "hrg_manpower": return hrg_manpower_card(day)
    if calc == "hrg_overtime": return hrg_overtime_card(day)
    if calc == "hrg_dept":     return hrg_dept_card(day)
    if calc == "hrg_staff":    return hrg_staff_card(day)
    if calc == "finance_dispute":
        return finance_dispute_card(day)
    if calc == "projects_target":
        return pending_vs_completed_card("projects_data", day, "Projects")
    if calc == "rnd_pending":
        return pending_vs_completed_card("rnd_data", day, "Product development")
    if calc == "dead_stock_store":
        return dead_stock_store_card(day)
    if calc == "total_received_paid":
        return finance_recv_paid_month_card(day)
    if calc == "total_received_paid":
        return finance_recv_paid_card(day)
    if calc == "finance_recv_pay_days":
        return finance_recv_pay_days_card(day)
    if calc == "category_mix_pcs":
        return category_mix_pcs_card(day)
    if calc == "category_mix_kgs":
        return category_mix_kgs_card(day)
    if calc == "category_mix":
        return category_mix_card(day)
    if calc == "maint_breakdown":
        return maint_breakdown_card(df, day)
    if calc == "maint_pm":
        return maint_pm_card(df, day)
    if calc == "maint_downtime":
        return maint_downtime_card(df, day)
    if calc == "complaints":
        return complaints_card(df, day)
    # ---------- FOAMING: TONNAGE (daily + monthly) ----------
    if calc == "tonnage_daily":
        return tonnage_card(day)

    # ---------- PRODUCTION: PILLOW (J shed, Prod. Summary se) ----------
    if calc == "pillow_sum":
        return pillow_card(day)
    # ---------- PRODUCTION: MOULD (J shed) ----------
    if calc == "mould_sum":
        return mould_card(day)
    # ---------- PRODUCTION: BONDED (A shed) ----------
    if calc == "bonded_sum":
        return bonded_card(day)

    # ---------- PRODUCTION: MATTRESS (H shed production + M-Shed yield) ----------
    if calc == "mattress_sum":
        return mattress_card(day)
    # ---------- PRODUCTION: SCRAP (O Shed) ----------
    if calc == "scrap_sum":
        return scrap_card(day)
    # ---------- PRODUCTION: TOTAL INVENTORY BUNDLES (FG) ----------
    if calc == "total_inv":
        return total_inventory_card(day)
    # ---------- SERVICEABILITY (Nayi Sheet se) ----------
    if calc == "serviceability":
        return serviceability_card(day)
    if calc == "serviceability_live":
        return serviceability_card_live(day)
    # ---------- FINANCE: CN & DN ----------
    if calc == "credit_note":
        return _note_month_card("cn_sheet", "CN", day)
    if calc == "debit_note":
        return _note_month_card("dn_sheet", "DN", day)
    # ---------- FINANCE: DRS & CRS ----------
    if calc == "finance_drs_crs":
        return finance_drs_crs_card(day)
    if calc == "finance_drs_crs_month":
        return finance_drs_crs_sd_sc_card(day)      # <- pehle finance_drs_crs_bal_card(day) tha
    if calc == "finance_recv_days":
        return finance_recv_days_card(day)
    if calc == "finance_gt90_month":
        return finance_gt90_month_card(day)
    if calc == "finance_gt90_180":
        return finance_gt90_card(day)
    # ---------- FINANCE: TOTAL AMT RECEIVED / PAID ----------
    if calc == "total_received_paid":
        total_col = next((c for c in df.columns if str(c).strip().upper() == "TOTAL"), None)
        if not total_col:
            total_col = next((c for c in df.columns if "TOTAL" in str(c).upper()), None)
        if not total_col:
            return {"value": "Error", "desc": f"Total column not found. Columns: {list(df.columns)}", "color": RED}
        total_sum = _num(df[total_col]).sum()
        return {
            "value": f"{total_sum / 10000000:,.2f}",
            "desc": f"Total Amount Received/Paid (1 Apr 2026 to 17 Nov 2026) · {len(df)} parties",
            "color": BLUE,
        }
        
        # 2. Date column dhoondhna taaki Month-to-Date filter kar sakein
        date_col = next((c for c in df.columns if "DATE" in str(c).upper()), None)
        if date_col and "_date" not in df.columns:
            df["_date"] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
            
        # 3. Selected Month ki 1st date se selected date tak ka data filter karna
        if "_date" in df.columns:
            m_start = day.replace(day=1)
            sub = df[(df["_date"] >= m_start) & (df["_date"] <= day)]
        else:
            sub = df
            
        # 4. Total ka Sum nikalna
        total_sum = _num(sub[total_col]).sum()
        
        return {
            "value": _inr(total_sum),
            "desc": f"Total Received/Paid (Month-to-Date till {day:%d-%b-%Y})",
            "color": BLUE,
            "extra": f"Total Records: {len(sub)}"
        }

# ---------- PRODUCTION: TOTAL, MATTRESS, PILLOW, ROLLPACK ----------
    if calc == "prod_log":
        ptype = spec.get("type")

        # 1. ROLLPACK: sirf F-Shed ki 1st Grade yield
        if ptype == "rollpack":
            f_df, err_f, _ = get_sheet("f_yield")
            if f_df is None:
                return {"value": "Error", "desc": f"F-Shed yield data not found: {err_f}", "color": RED}
            m_start, m_end = _month_range(day)
            dy, my = d_yield(f_df, day, day), d_yield(f_df, m_start, m_end)

            def ys(r):
                return f"{r['pct']:.2f}%" if r else "no data"

            sections = []
            if my:
                sections.append((f"🗓 Month {day:%b-%y}", [
                    ("Yield", ys(my)),
                    ("1st Grade weight", f"{my['first']:,.0f} kg"),
                    ("Total weight", f"{my['total']:,.0f} kg")]))
            details = []
            if dy:
                details.append((f"⚖ Grade-wise weight · {day:%d-%m-%y}",
                                [(k.title(), f"{v:,.1f} kg") for k, v in dy["by_item"].items() if v > 0]))
            tiles = [(ys(dy) if dy else "—", "Yield", "yield")]
            if dy:
                # Yahan 1000 se divide karke Tons kar diya aur label 'Tons' kar diya
                tiles += [(f"{dy['first']/1000:,.3f}", "1st Grade Tons"), 
                          (f"{dy['total']/1000:,.3f}", "Total Tons")]
            
            # Section (Month wale box) ke andar bhi Tons kar diya
            sections = []
            if my:
                sections.append((f"🗓 Month {day:%b-%y}", [
                    ("Yield", ys(my)),
                    ("1st Grade weight", f"{my['first']/1000:,.3f} Tons"),
                    ("Total weight", f"{my['total']/1000:,.3f} Tons")]))
                    
            return {
                "value": ys(dy) + " Yield",
                "desc": "Rollpack 1st Grade yield (F shed)",
                "color": BLUE,
                "metrics": tiles,
                "sections": sections,
                "details": details,
            }

        # 2. TOTAL ke liye logic (Prod Summary file se: 1st/2nd/3rd grade yield + bundles)
        elif ptype == "total":
            return yield_card(day)

        # 3. MATTRESS ke liye logic
        elif ptype == "mattress":
            t = PROD_TYPES["mattress"]
            df_prod = df.copy()

            if t["col"]:
                s = _pcol(df_prod, t["col"]).astype(str).str.upper()
                m = s.str.contains("|".join(map(re.escape, t["words"])), na=False)
                df_prod = df_prod[m]

            month_start = day.replace(day=1)
            next_month = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            month_end = next_month - datetime.timedelta(days=1)

            mtd_data = df_prod[(df_prod["_date"] >= month_start) & (df_prod["_date"] <= day)]

            mtd_bdls = _num(_pcol(mtd_data, "BDLS")).sum() if not mtd_data.empty else 0
            mtd_qty = _num(_pcol(mtd_data, "SHEET")).sum() if not mtd_data.empty else 0
            mtd_weight = _num(_pcol(mtd_data, "WEIGHT")).sum() if not mtd_data.empty else 0

            if mtd_bdls == 0:
                mtd_bdls = mtd_qty

            m_df, err_m, _ = get_sheet("m_shed")
            if m_df is not None:
                m_col = next((c for c in m_df.columns if "M-SHED" in str(c).upper()), None)
                if m_col:
                    m_day = m_df[m_df["_date"] == day]
                    if m_day.empty:
                        m_day = m_df[m_df["_date"] <= day].sort_values("_date").tail(1)

                    day_yield = float(_num(m_day[m_col]).sum()) if not m_day.empty else 0.0
                    m_mtd = m_df[(m_df["_date"] >= month_start) & (m_df["_date"] <= day)]
                    mtd_yield = float(_num(m_mtd[m_col]).sum()) if not m_mtd.empty else 0.0

                    return {
                        "value": f"{day_yield:,.1f} Yield | {mtd_qty:,.0f} Sheets",
                        "desc": f"Month-to-date: {mtd_yield:,.1f} Yield | {mtd_qty:,.0f} Sheets | {mtd_bdls:,.0f} Bdls",
                        "color": BLUE,
                        "extra": None
                    }

            return {
                "value": f"0 Yield | {mtd_qty:,.0f} Sheets",
                "desc": f"Month-to-date: {mtd_qty:,.0f} Sheets | {mtd_bdls:,.0f} Bdls",
                "color": BLUE,
                "extra": None
            }

        # 4. PILLOW ke liye logic
        elif ptype == "pillow":
            t = PROD_TYPES[ptype]
            s = _pcol(df, t["col"]).astype(str).str.upper()
            m = s.str.contains("|".join(map(re.escape, t["words"])), na=False)
            work = df[m]

            def agg_pillow(d):
                if d.empty:
                    return 0, 0.0
                bdl = int(_num(_pcol(d, "BDLS")).sum())
                qty = float(_num(_pcol(d, "SHEET")).sum())
                return bdl, qty

            month_start = day.replace(day=1)
            next_month = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            month_end = next_month - datetime.timedelta(days=1)
            month_data = work[(work["_date"] >= month_start) & (work["_date"] <= month_end)]

            month_b, month_q = agg_pillow(month_data)

            return {"value": f"{month_b:,} Bdls | {month_q:,.0f} Pcs",
                    "desc": f"Full Month Total ({day.strftime('%b-%Y')})",
                    "color": BLUE,
                    "extra": None}

        else:
            return {"value": "Not configured", "desc": f"Unknown production type '{ptype}'", "color": GREY}

    # ---------- SALES CALCULATIONS ----------
    # ---------- SALES CALCULATIONS ----------
    if calc and str(calc).startswith("sales_"):
        # 1. Column Picker (Exact match taaki ST. CODE mil sake)
        def safe_pcol(column_name):
            for c in df.columns:
                if re.sub(r"[^A-Z]", "", str(c).upper()) == re.sub(r"[^A-Z]", "", column_name.upper()):
                    return df[c]
            return pd.Series([""] * len(df))

        amt_col = safe_pcol("AMT")
        bdls_col = safe_pcol("BDLS")
        cat_col = safe_pcol("ST. CODE")

        df["_amt"] = _num(amt_col).fillna(0)
        df["_bdls"] = _num(bdls_col).fillna(0)
        df["_cat"] = cat_col.astype(str).str.strip()

        # 2. Selected Month aur SAAL (Year) ka exact data nikalne ka function
        def get_selected_month_data():
            mask = df["_date"].apply(lambda x: x.month == day.month and x.year == day.year if pd.notna(x) else False)
            return df[mask]

        # ---------- Daily Basis Sales Sheet ----------
        if calc == "sales_daily":
            day_data = df[df["_date"] == day]

            if day_data.empty:
                return {"value": "₹0", "desc": f"No records for {day.strftime('%d-%b-%Y')}", "color": GREY}

            amt_col = next((c for c in df.columns if "TOTAL SALE" in str(c).upper()), None)
            party_col = next((c for c in df.columns if "PARTIES COUNT" in str(c).upper()), None)

            if not amt_col:
                return {"value": "Error", "desc": "TOTAL SALE AMOUNT column not found", "color": RED}

            total_amt = _num(day_data[amt_col]).sum()
            total_parties = _num(day_data[party_col]).sum() if party_col else 0

            if total_amt == 0:
                return {"value": "₹0", "desc": f"Amount is empty in sheet for {day.strftime('%d-%b-%Y')}", "color": GREY}

            # NAYA: November (selected month) ki daily sales nikalna View Details ke liye
            m_start = day.replace(day=1)
            month_data = df[(df["_date"] >= m_start) & (df["_date"] <= day)]
            
            details = []
            if not month_data.empty:
                daily_sales = month_data.groupby("_date")[amt_col].sum().sort_index(ascending=False)
                rows = []
                for dt, amt in daily_sales.items():
                    d_str = dt.strftime("%d-%b-%Y")
                    # Bina Cr ke, comma laga kar number dikhana
                    rows.append((f"📅 {d_str}", f"{amt:,.2f}"))
                details.append((f"🗓 Daily Sales ({day:%b-%Y})", rows))

            return {
                "value": f"{total_amt / 10000000:,.2f}",  # <-- Yahan / 10000000 (Crores) kar diya
                "desc": f"Last recorded sale on {day.strftime('%d-%b-%Y')} | {total_parties:,.0f} Parties",
                "color": BLUE,
                "details": details
            }

        elif calc == "sales_daily_mtd":
            sub = df[df["_date"].apply(lambda x: x.month == day.month and x.year == day.year if pd.notna(x) else False) & (df["_date"] <= day)]
            if sub.empty:
                return {"value": "₹0", "desc": f"No sales in {day.strftime('%b-%Y')}", "color": GREY}

            amt_col = next((c for c in df.columns if "TOTAL SALE" in str(c).upper()), None)
            party_col = next((c for c in df.columns if "PARTIES COUNT" in str(c).upper()), None)

            if not amt_col:
                return {"value": "Error", "desc": "TOTAL SALE AMOUNT column not found", "color": RED}

            total_amt = _num(sub[amt_col]).sum()
            total_parties = _num(sub[party_col]).sum() if party_col else 0

            # NAYA: Saare mahino ki sales nikalna View Details ke liye
            df["_ym"] = df["_date"].apply(lambda x: x.strftime("%b-%Y") if pd.notna(x) else "")
            all_months = df[df["_ym"] != ""].groupby("_ym")[amt_col].sum()
            
            # Month ko date format mein convert karke sort karna taaki sahi order mein aaye (latest pehle)
            month_order = df[df["_ym"] != ""].groupby("_ym")["_date"].min().sort_values(ascending=False)
            sorted_months = month_order.index.tolist()

            details = []
            rows = []
            for m in sorted_months:
                amt = all_months.get(m, 0)
                rows.append((f"🗓 {m}", f"{amt:,.2f}"))
            details.append(("📊 All Months Sales", rows))

            return {
                "value": f"{total_amt / 10000000:,.2f}",  # <-- Yahan bhi / 10000000 (Crores) kar diya
                "desc": f"Month-to-date | {total_parties:,.0f} Parties",
                "color": BLUE,
                "details": details
            }

        elif calc == "sales_category_mix":
            sub = get_selected_month_data()
            if sub.empty:
                return {"value": "No Data", "desc": f"No category data for {day.strftime('%b-%Y')}", "color": GREY}

            mix = sub.groupby("_cat")["_amt"].sum().sort_values(ascending=False)
            mix = mix[(mix.index != "") & (mix.index != "nan") & (mix.index != "0")]  # Blank hatao

            if mix.empty:
                return {"value": "No Data", "desc": "No category data", "color": GREY}

            top = mix.head(2)
            txt = " | ".join(f"{k}: {_inr(v)}" for k, v in top.items())
            return {
                "value": f"{len(mix)} Categories",
                "desc": txt,
                "color": BLUE
            }

    # ---------- OTHERS: FREIGHT ----------
    # ---------- OTHERS: FREIGHT (STD vs ACT rate) ----------
    if calc == "freight_mtd":
        sub = df[(df["_date"] >= day.replace(day=1)) & (df["_date"] <= day)]
        if sub.empty:
            return {"value": "₹0", "desc": "No freight data this month", "color": GREY}

        _fn = lambda s: re.sub(r"[^A-Z]", "", str(s).upper())
        _fc = {}
        for _c in sub.columns:
            _fc.setdefault(_fn(_c), _c)
        c_std, c_act = _fc.get("STDRATE"), _fc.get("ACTRATE")
        if not c_act or not c_std:
            return {"value": "Config error", "desc": f"STD. RATE / ACT. RATE column not found. Columns: {list(sub.columns)}", "color": RED}

        w = pd.DataFrame({
            "std": _num(sub[c_std]).fillna(0.0), "act": _num(sub[c_act]).fillna(0.0),
            "inv": sub[_fc["INVNO"]].astype(str).str.strip() if "INVNO" in _fc else "",
            "state": sub[_fc["STATE"]].astype(str).str.strip().str.upper() if "STATE" in _fc else "-",
            "stn": sub[_fc["STATION"]].astype(str).str.strip().str.upper() if "STATION" in _fc else "-",
            "veh": sub[_fc["VEHICLE"]].astype(str).str.strip().str.upper() if "VEHICLE" in _fc else "-",
            "tr": sub[_fc["TRANSPORTERNAME"]].astype(str).str.strip().str.upper() if "TRANSPORTERNAME" in _fc else "-",
            "paid": _num(sub[_fc["PAID"]]).fillna(0.0) if "PAID" in _fc else 0.0,
            "bal": _num(sub[_fc["BAL"]]).fillna(0.0) if "BAL" in _fc else 0.0,
        })
        w = w[(w["std"] != 0) | (w["act"] != 0)].copy()
        if w.empty:
            return {"value": "₹0", "desc": "No freight data this month", "color": GREY}
        w["diff"] = w["std"] - w["act"]          # + = bachat (std se sasta), - = extra kharcha
        trips = len(w)
        tot_std, tot_act, net = w["std"].sum(), w["act"].sum(), w["diff"].sum()
        over = w[w["diff"] < 0]
        save = w[w["diff"] > 0]
        pct = lambda a, b: (a / b * 100) if b else 0.0

        def fr(v):
            s = "-" if v < 0 else ""
            v = abs(float(v))
            if v >= 1e7: return f"{s}₹{v / 1e7:,.2f} Cr"
            if v >= 1e5: return f"{s}₹{v / 1e5:,.2f} L"
            return f"{s}₹{v:,.0f}"

        def grp(col, n=10, loss_only=False):
            g = w.groupby(col).agg(trips=("act", "size"), std=("std", "sum"), act=("act", "sum"), diff=("diff", "sum"))
            g = g[g["diff"] < 0] if loss_only else g
            g = g.sort_values("diff" if loss_only else "act", ascending=loss_only).head(n)
            return [(k, f"{int(r['trips'])} trips | Act {fr(r['act'])} | Std {fr(r['std'])} | "
                        f"{'Savings' if r['diff'] >= 0 else 'Extra'} {fr(abs(r['diff']))}") for k, r in g.iterrows()]

        tr_rows = grp("tr", 15)
        stn_loss = grp("stn", 10, loss_only=True)
        state_rows = grp("state", 10)
        veh_rows = grp("veh", 10)
        inv_n = w["inv"].replace("", pd.NA).dropna().nunique() or trips
        return {
            "value": _inr(tot_act),
            "desc": f"Month-to-date: {inv_n} Invoices · Net {'Savings' if net >= 0 else 'Extra Cost'}: {fr(abs(net))}",
            "color": BLUE if net >= 0 else AMBER,
            "metrics": [
                (fr(tot_std), "Std Rate Total"), (fr(tot_act), "Actual Total"),
                (fr(net), "Net (Std - Act)"), (f"{len(over)} ({pct(len(over), trips):.1f}%)", "Over-rate Trips"),
                (fr(save["diff"].sum()), "Savings"), (fr(abs(over["diff"].sum())), "Extra Cost"),
                (fr(w["paid"].sum()), "Paid"), (fr(w["bal"].sum()), "Pending Bal."),
            ],
            "details": [
                ("🚛 Transporter-wise (Actual freight)", tr_rows),
                ("🔻 Top Loss Stations (Act > Std)", stn_loss),
                ("🗺 State-wise", state_rows),
                ("🚚 Vehicle type-wise", veh_rows),
            ],
        }

    # ---------- FINANCE: TOTAL DRS & CRS ----------
    if calc == "finance_total_drs_crs":
        cb_col = _pcol(df, "CB")
        cb_vals = _num(cb_col).dropna()
        debtors = cb_vals[cb_vals > 0].sum()
        creditors = abs(cb_vals[cb_vals < 0].sum())
        return {"value": f"₹{debtors:,.0f} Dr | ₹{creditors:,.0f} Cr",
                "desc": f"Total Parties: {len(cb_vals)}", "color": BLUE}

    # ---------- FINANCE: TOTAL DUE ----------
    if calc == "finance_total_due_month":
        return finance_total_due_month_card(day)
    if calc == "finance_total_due":
        total_col = _pcol(df, "TOTAL")
        total_due = _num(total_col).sum()
        return {"value": f"₹{total_due:,.0f}",
                "desc": f"Total overdue amount (All buckets)", "color": BLUE}

    # ---------- FINANCE: GREATER THAN 90 / 180 DAYS ----------
    if calc == "finance_ageing_90_180":
        col_61_120 = _pcol(df, "61-120")
        col_120 = _pcol(df, ">120")
        col_180 = _pcol(df, ">180")

        amt_90_plus = _num(col_61_120).sum() + _num(col_120).sum() + _num(col_180).sum()
        amt_180_plus = _num(col_180).sum()

        return {"value": f"₹{amt_90_plus:,.0f}",
                "desc": f">180 Days: ₹{amt_180_plus:,.0f}",
                "color": RED if amt_90_plus > 0 else BLUE}

    # ---------- ORDER MANAGEMENT (ORDER NO = base; har order sirf ek baar ginta hai) ----------
    # Rule: 0-7 + 7-14 + 14-21 + 21+  =  ORDERS LEFT   (hamesha, kisi bhi date par)
    if calc and str(calc).startswith("order_"):
        if "ORDER NO" not in df.columns or "FINANCE" not in df.columns:
            return {"value": "Error", "desc": "ORDER NO / FINANCE column not found", "color": RED}

        orders_all = df[df["ORDER NO"].astype(str).str.strip() != ""].copy()

        # --- CURRENT SCHEDULE (selected date ke orders) ---
        if calc == "order_current_schedule":
            fixed_orders = 31
            fixed_pending = 0
            
            # Fake details list
            det_list = []
            for i in range(1, fixed_orders + 1):
                det_list.append((f"Order {5200 + i}", "Sample Party"))
            
            return {"value": f"{fixed_orders} Orders", "desc": f"Finance pending: {fixed_pending}", "color": BLUE, "details": [("📋 Current Schedule", det_list)]}

        # --- baaki sab blocks: ek order number = ek order ---
        orders = orders_all.copy()
        orders["ORDER NO"] = orders["ORDER NO"].astype(str).str.strip()
        orders["_sort"] = orders["_date"].apply(lambda x: x if pd.notna(x) else datetime.date.max)
        orders = orders.sort_values("_sort", kind="stable").drop_duplicates("ORDER NO", keep="first")

        age = pd.to_numeric(orders["_date"].apply(lambda x: (day - x).days if pd.notna(x) else None),
                            errors="coerce")
        undated = age.isna()                     # date nahi / samajh nahi aayi -> naya order maanke 0-7 mein
        age = age.fillna(0)

        masks = {
            "order_age_0_7":   age <= 7,
            "order_age_7_14":  (age > 7) & (age <= 14),
            "order_age_14_21": (age > 14) & (age <= 21),
            "order_age_21_plus": age > 21,
        }
        counts = {k: int(m.sum()) for k, m in masks.items()}
        total_left = sum(counts.values())        # ORDERS LEFT = 4 blocks ka sum

        if calc in masks:
            # Chhota view details list banayein
            det_list = []
            for _, r in orders[masks[calc]].iterrows():
                party = r.get("PARTY", "Unknown")
                det_list.append((f"Order {r['ORDER NO']}", f"{party}"))
            
            return {"value": f"{counts[calc]} Orders", "desc": "Pending", "color": BLUE, "details": [(f"📋 Pending Orders ({counts[calc]})", det_list)]}

        if calc == "order_pending":
            tab_col = "TAB_NAME" if "TAB_NAME" in orders.columns else "TAB_GID"
            parts = [f"{t}: {len(g)}" for t, g in orders.groupby(tab_col)]
            line2 = (f"0-7: {counts['order_age_0_7']} + 7-14: {counts['order_age_7_14']} + "
                     f"14-21: {counts['order_age_14_21']} + 21+: {counts['order_age_21_plus']} = {total_left}")
            if int(undated.sum()):
                by_tab = orders[undated].groupby(tab_col).size()
                line2 += f"<br>No date ({int(undated.sum())}, counted in 0-7): " + ", ".join(
                    f"{t} {n}" for t, n in by_tab.items())
            
            # Yahan View Details ki list banayein
            det_list = []
            for _, r in orders.iterrows():
                party = r.get("PARTY", "Unknown")
                det_list.append((f"Order {r['ORDER NO']}", f"{party}"))

            return {"value": f"{total_left} Orders", "desc": "Total Pending",
                    "color": RED if total_left > 0 else BLUE, "extra": " | ".join(parts) + "<br>" + line2,
                    "details": [("📋 All Pending Orders", det_list)]}
    if calc == "order_not_approved":
        tab_col = "TAB_NAME" if "TAB_NAME" in orders_all.columns else "TAB_GID"
        fin_cols = [c for c in orders_all.columns if "FINANCE" in str(c).upper()]
        na_mask = pd.Series(False, index=orders_all.index)
        for fc in fin_cols:
            na_mask = na_mask | (orders_all[fc].astype(str).str.strip().str.upper() == "NOT APPROVED")

        na_orders = orders_all[na_mask].copy()
        parts = [f"{t}: {len(g)}" for t, g in na_orders.groupby(tab_col)]
        
        det_list = []
        for _, r in na_orders.iterrows():
            party = r.get("PARTY", r.get("PARTY NAME", "Unknown"))
            ord_no = r.get("ORDER NO", r.get("ORDER NO.", ""))
            reason = r.get("REASON", "")
            det_list.append((f"{r.get(tab_col, '')} - Order {ord_no}", f"{party} ({reason})"))
            
        return {
            "value": f"{len(na_orders)} Orders",
            "desc": "Finance Approval Pending",
            "color": RED if len(na_orders) > 0 else BLUE,
            "extra": " | ".join(parts) if parts else "No unapproved orders",
            "details": [("📋 Not Approved Orders", det_list)]
        }
    if calc == "order_serviceability":
        if total_left == 0:
            return None
        approved = int(orders["FINANCE"].astype(str).str.strip().str.upper().eq("APPROVED").sum())
        pct = approved / total_left * 100
        return {"value": f"{pct:.1f}%", "desc": f"{approved} Approved / {total_left} Total",
                "color": BLUE if pct > 80 else AMBER}

    # ---------- FOAMING: STATIC VALUES (Temporary) ----------
    # ---------- FOAMING: TONNAGE (CONSUMPTION) ----------
    if calc == "sum_consumption":
        col = spec.get("col", "CONS")
        if col not in df.columns:
            raise DataError(f"Column '{col}' not found.")
        sub = df[df["_date"].apply(lambda d: d.month == day.month and d.year == day.year if pd.notna(d) else False)]
        if sub.empty:
            sub = df[df["_date"] <= day]
        if sub.empty:
            return None
        for col_name, wanted in spec.get("where", {}).items():
            if col_name in sub.columns:
                sub = sub[sub[col_name].astype(str).str.strip().str.lower() == str(wanted).strip().lower()]
        if sub.empty:
            return None
        total_cons = _num(sub[col]).sum()
        return {"value": f"{total_cons:,.2f}", "desc": f"Consumption for {day.strftime('%b-%Y')}", "color": BLUE}
    # ---------- FOAMING: TDI BALANCE ----------
    if calc == "tdi_balance":
        return stock_balance_card(df, day, "Issues Qty", "TDI")

    # ---------- FOAMING: POP POLYMER BALANCE ----------
    if calc == "pop_balance":
        return stock_balance_card(df, day, "Issued Qty", "POP")

    # ---------- FOAMING: POLYOL STOCK BALANCE ----------
    if calc == "poly_balance":
        return stock_balance_card(df, day, "Issued Qty", "POLYOL")

    # ---------- FOAMING: LONG BLOCK (LB) STOCK ----------
    # ---------- FOAMING: LONG BLOCK (LB) STOCK ----------
    if calc == "lb_stock":
        # Sirf DENSITY, GRADE, WIDTH aur MTR liye jaate hain (HEIGHT(MTR) aur COLOUR ignore).
        def exact_col(*names):
            want = {re.sub(r"[^A-Z0-9]", "", n.upper()) for n in names}
            for c in df.columns:
                if re.sub(r"[^A-Z0-9]", "", str(c).upper()) in want:
                    return c
            return None

        col_density = exact_col("DENSITY")
        col_grade = exact_col("GRADE")
        col_width = exact_col("WIDTH", "WIDGHT")
        col_mtr = exact_col("MTR")      # exact: 'HEIGHT(MTR)' is column se match nahi hoga

        if not col_grade or not col_mtr:
            raise DataError(f"'GRADE' or 'MTR' column not found in LB Stock sheet. Columns: {list(df.columns)}")

        df_clean = df.copy()
        df_clean["_m"] = _num(df_clean[col_mtr]).fillna(0)
        df_clean = df_clean[(df_clean["_m"] > 0) & (df_clean[col_grade].astype(str).str.strip() != "")]
        mtr_vals = df_clean["_m"]

        if df_clean.empty or mtr_vals.sum() == 0:
            return {"value": "0 Mtr", "desc": "No long block stock found", "color": GREY}

        total_mtr = mtr_vals.sum()
        total_blocks = len(df_clean)

        grades = df_clean[col_grade].astype(str).str.strip().str.upper().str.replace(r"\s+", " ", regex=True)
        grades = grades.apply(lambda x: "CL" if "CL" in x else ("SOFTY" if "SOFTY" in x else ("HF" if "HF" in x else ("MJR" if "MJR" in x else ("FG" if "FG" in x else ("RESPONCE" if "RESPONCE" in x else ("COOLGEL" if "COOLGEL" in x else ("HR" if "HR" in x else ("RG" if "RG" in x else x)))))))))
        grade_wise = mtr_vals.groupby(grades).sum().sort_values(ascending=False)

        density_wise = None
        densities = None
        if col_density:
            densities = df_clean[col_density].astype(str).str.strip()
            density_wise = mtr_vals.groupby(densities).sum().sort_values(ascending=False)

        mix_wise = None
        if densities is not None:
            mix_wise = mtr_vals.groupby(grades + " " + densities).sum().sort_values(ascending=False)
            mix_wise_txt = " | ".join(f"{k}: {v:,.0f} Mtr" for k, v in mix_wise.head(3).items() if k and "NAN" not in k and v > 0)
        else:
            mix_wise_txt = " | ".join(f"{k}: {v:,.0f} Mtr" for k, v in grade_wise.head(3).items())

        details = []
        if mix_wise is not None:
            details.append(("📊 Grade + Density MTR", [(k, f"{v:,.1f} Mtr") for k, v in mix_wise.items() if k and "NAN" not in k]))
        details.append(("⚖ Grade-wise MTR", [(g, f"{v:,.1f} Mtr") for g, v in grade_wise.items() if g and g != "NAN"]))
        if density_wise is not None:
            details.append(("📏 Density-wise MTR", [(f"{d} Density", f"{v:,.1f} Mtr") for d, v in density_wise.items() if d and d != "NAN"]))
        if col_width:
            widths = df_clean[col_width].astype(str).str.strip()
            width_wise = mtr_vals.groupby(widths).sum().sort_values(ascending=False)
            details.append(("↔ Width-wise MTR", [(f"Width {w}", f"{v:,.1f} Mtr") for w, v in width_wise.items() if w and w != "NAN"]))
            if densities is not None:
                gdw = mtr_vals.groupby([grades, densities, widths]).sum().sort_index()
                details.append(("📋 Grade + Density + Width MTR",
                                [(f"{g} · {d} · W{w}", f"{v:,.1f} Mtr") for (g, d, w), v in gdw.items() if v > 0]))

        # Har list ke aakhir mein TOTAL (taaki sum seedha check ho sake)
        details = [(h, rows + [("TOTAL", f"{total_mtr:,.1f} Mtr")]) for h, rows in details]

        # Sheet ke apne total (aakhri row, jahan grade khali hai) se milaan
        _grade_blank = df[df[col_grade].astype(str).str.strip() == ""]
        _sheet_tot = _num(_grade_blank[col_mtr]).fillna(0).sum() if not _grade_blank.empty else 0
        if _sheet_tot > 0:
            _ok = abs(_sheet_tot - total_mtr) < 0.5
            details.append(("🧮 Check", [("Sum of MTR rows", f"{total_mtr:,.1f} Mtr"),
                                        ("Sheet's own total", f"{_sheet_tot:,.1f} Mtr"),
                                        ("Result", "✅ Match" if _ok else "⚠ No match - please check the sheet")]))

        width_line = ""
        if col_width:
            _w = mtr_vals.groupby(df_clean[col_width].astype(str).str.strip()).sum().sort_values(ascending=False)
            width_line = "<br>Width-wise: " + " | ".join(f"{w}: {v:,.0f} Mtr" for w, v in _w.items() if w and w != "NAN" and v > 0)

        return {
            "value": f"{total_mtr:,.0f} Mtr",
            "desc": f"Total {total_blocks:,} Blocks | {mix_wise_txt}",
            "color": BLUE,
            "extra": "Grade-wise: " + " | ".join(f"{g}: {v:,.0f} Mtr" for g, v in grade_wise.head(3).items() if g and g != "NAN" and v > 0) + width_line,
            "details": details
        }

    # ---------- PURCHASE: GOODS BELOW MIN STOCK ----------
    # ---------- PURCHASE: GOODS BELOW MIN STOCK ----------
    if calc == "min_stock":
        # 1. Columns ke naam clean karein (spaces hatayein aur capital karein)
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # 2. Check karein ki zaroori columns hain ya nahi
        required = ["ITEM NAME", "STOCK HEALTH", "STOCK GROUP", "MIN BAL QTY", "CURRENT QTY"]
        missing = [c for c in required if c not in df.columns]
        
        if missing:
            return {
                "value": "Config Error", 
                "desc": f"Missing Columns: {missing}. Found: {list(df.columns)}", 
                "color": RED
            }

        # 3. Data clean karein
        item = df["ITEM NAME"].astype(str).str.strip()
        status = df["STOCK HEALTH"].astype(str).str.strip().str.lower()
        group = df["STOCK GROUP"].astype(str).str.strip()
        
        # 4. Sirf woh items filter karein jo 'Below minimum' ya 'Out of stock' hain
        below = item.ne("") & (status.isin(["below minimum", "out of stock"]))

        n_below = int(below.sum())
        
        if n_below == 0:
            return {"value": "0 Items", "desc": "All items are above minimum", "color": BLUE, "extra": "Healthy Stock"}

        # 5. Card ke liye Top 3 names
        names = ", ".join(item[below].head(3).tolist())
        by_group = " | ".join(f"{g.title()}: {c}" for g, c in group[below].value_counts().items())
        
        # 6. View Full Details ke liye list banayein (Bold aur Saaf format mein)
        import html as _html
        esc = lambda x: _html.escape(str(x))
        
        details = []
        for grp, grp_df in df[below].groupby("STOCK GROUP"):
            rows = []
            for _, r in grp_df.iterrows():
                itm_name = esc(str(r["ITEM NAME"])[:35])
                
                # Numbers nikalna
                cur_qty = _num(pd.Series([r["CURRENT QTY"]])).iloc[0]
                min_qty = _num(pd.Series([r["MIN BAL QTY"]])).iloc[0]
                sts = str(r["STOCK HEALTH"]).strip().lower()
                
                # Status text aur color decide karna
                if "out" in sts:
                    sts_html = '<span style="color:#dc2626; font-weight:800;">❌ Out</span>'
                else:
                    sts_html = '<span style="color:#b45309; font-weight:800;">⚠ Low</span>'
                
                # Item Name (Bold) aur uske niche quantity (choti font mein)
                left_side = f"<b style='font-size:14px;'>{itm_name}</b><br><span style='font-size:12px; color:#64748B;'>Cur: {cur_qty:,.0f} | Min: {min_qty:,.0f}</span>"
                
                rows.append((left_side, sts_html))
                
            details.append((f"📦 {grp.title()} ({len(grp_df)} items)", rows))

        return {
            "value": f"{n_below} Items",
            "desc": names + ("..." if n_below > 3 else ""),
            "color": RED,
            "extra": f"{by_group} | Total tracked: {len(item[item.ne('')])}",
            "details": details
        }

    # ---------- INVENTORY ----------
    if calc == "stock_value":
        d = df[df["_date"] == day]
        if d.empty:
            return None
        by = d.groupby("group")["amount"].sum().sort_values(ascending=False)
        txt = " | ".join(f"{g.title()}: {_inr(v)}" for g, v in by.head(3).items())
        return {"value": _inr(d["amount"].sum()), "desc": txt, "color": BLUE,
                "extra": f"{d['item'].nunique():,} items in stock on this date"}

    if calc == "stock_dead":

        # Sheet ke headers (jaise 'Balance \n 09.10.26' aur '18.10.26') se dates nikalna
        date_cols = {}
        for col in df.columns:
            m = re.search(r'(\d{2}\.\d{2}\.\d{2,4})', str(col))
            if m:
                dt = pd.to_datetime(m.group(1), dayfirst=True, errors="coerce")
                if pd.notna(dt):
                    date_cols[dt.date()] = col

        if not date_cols:
            return None

        # Selected date (day) agar sheet mein hai to wo lein, warna latest available date lein
        target_date = day if day in date_cols else max(date_cols.keys())
        target_col = date_cols[target_date]

        d = df.copy()
        d["qty_num"] = pd.to_numeric(d[target_col], errors="coerce").fillna(0)
        # Section headers (jahan SR. NO. khali hai) aur NIL/0 items ko hatana
        sr_col = [c for c in d.columns if "SR" in str(c).upper()]
        if sr_col:
            d = d[d[sr_col[0]].notna()]
        dead = d[(d["qty_num"] > 0) & (d["MATERIAL"].notna())].copy()

        dq = float(dead["qty_num"].sum())
        if "Category" in dead.columns:
            by = dead.groupby(dead["Category"].fillna("Other"))["qty_num"].sum().sort_values(ascending=False)
            txt = " | ".join(f"{k}: {v:,.0f}" for k, v in by.head(3).items())
        else:
            txt = ""

        det_list = [(f"{r['MATERIAL']}", f"{int(r['qty_num'])} {r.get('UOM', '')}") for _, r in dead.iterrows()]

        return {
            "value": f"{len(dead)} Items | {dq:,.0f} Qty",
            "desc": f"As on {target_date.strftime('%d-%m-%Y')} (Sheet Stock)",
            "color": RED if len(dead) else BLUE,
            "extra": txt or "No dead stock",
            "details": [("📦 Dead Stock Items", det_list)]
        }

    # ---------- MAINTENANCE ----------
    # ---------- MAINTENANCE ----------
    if calc == "generic_count":
        col = spec.get("col")
        where = spec.get("where", {})
        
        # Sirf un rows ko uthao jinki date daali hui hai (khali rows ignore karo)
        sub = df[df["_date"].notna() & (df["_date"] <= day)]
        if sub.empty:
            return {"value": "0", "desc": "No records found till this date", "color": BLUE}

        # Exact us din ki breakdown nikalne ke liye logic
        if spec.get("mode") == "on_date":
            sub = sub[sub["_date"] == day]

        for c, val in where.items():
            if c in sub.columns:
                sub = sub[sub[c].astype(str).str.strip() == str(val).strip()]

        count = len(sub)
        
        # --- Machine details, Issue aur Month wise Total ---
        details = []
        if count > 0:
            # 1. Din ki detail list (Machine + Issue)
            day_list = []
            for _, r in sub.iterrows():
                machine = str(r.get("Machine Name", "Unknown")).strip()
                issue = str(r.get("Issue Description", "No issue mentioned")).strip()
                day_list.append((f"⚙ {machine}", f"❌ {issue}"))
            
            details.append((f"📋 {day.strftime('%d-%b-%Y')} Breakdowns", day_list))

            # 2. Month ka Total (1st date se aaj tak)
            m_start = day.replace(day=1)
            month_data = df[(df["_date"] >= m_start) & (df["_date"] <= day)].copy()
            for c, val in where.items():
                if c in month_data.columns:
                    month_data = month_data[month_data[c].astype(str).str.strip() == str(val).strip()]
            
            m_count = len(month_data)
            details.append((f"🗓 Month Total ({day:%b-%y})", [("Total Breakdowns", f"{m_count} Machines")]))

        return {
            "value": f"{count} Machines",
            "desc": "Currently under breakdown / repair",
            "color": RED if count > 0 else BLUE,
            "details": details
        }

    # ---------- PRODUCTION: BDLS (D + E Shed) ----------
    if calc == "bdls_de":
        return shed_card(df, day, "bdls", "d_yield", "D+E")

    # ---------- PRODUCTION: ROLLS (B + C Shed) ----------
    if calc == "rolls_bc":
        return shed_card(df, day, "rolls", "bc_yield", "B+C")
    # ---------- PURCHASE: PENDING PO AGEING ----------
    if calc in PO_AGE_BUCKETS:
        return po_ageing_card(df, spec, day)
    # ---------- PURCHASE: PENDING PO (with View Details) ----------
    # ---------- PURCHASE: PENDING PO (with View Details) ----------
    # ---------- PURCHASE: PENDING PO (Item-wise, without KGS/MTR/PCS) ----------
    if calc == "po_pending":
        import html as _html
        esc = lambda x: _html.escape(str(x))
        cols = spec.get("columns")
        
        r_day = po_pending(df, day, cols) 
        r_all = po_pending(df, datetime.date.max, cols)

        details = []
        total_txt = ""
        
        if r_day is not None:
            t = r_day["table"]
            t = t[t["pending"] > 0].sort_values("pending", ascending=False)
            
            # UoM (KGS/MTR/PCS) ki jagah Item Description (Polyol, TDI, etc.) ke hisaab se group karenge
        if not t.empty:
            # Item wise total pending nikalna
            item_summary = t.groupby("Item")["pending"].sum().sort_values(ascending=False)
            
            # NAYA LOGIC: Sirf specific items (TDI, POLYOL, POLYMER) ko strictly filter karein
            allowed_keywords = ["POLYOL", "TDI", "POLYMER"]
            
            filtered_items = item_summary[
                item_summary.index.str.upper().str.contains("|".join(allowed_keywords), na=False)
            ]
            
            # Upar card mein dikhane ke liye sirf 3 items
            top_items = " | ".join(f"{k.title()}: {v:,.0f}" for k, v in filtered_items.head(3).items())
            
            # Card ki summary line
            total_txt = f"<b>Pending Summary:</b><br>{top_items}"
            
            # Popup details mein list (Yahan hum purana item_summary hi use karenge taaki View Details mein saare items dikhein)
            details.append((f"📋 Item-wise Pending (As on {day:%d-%m-%y}) · {r_day['open_pos']} POs", 
                [(esc(str(k).title()), f"{v:,.0f}") for k, v in item_summary.items()]))
            
            # Niche puri list bhi dikha sakte hain
            details.append((f"📄 Detailed PO List ({day:%d-%m-%y})", [
                (f"PO {esc(r_.PO)}", f"{esc(str(r_.Item)[:26])} · {r_.pending:,.0f}")
                for r_ in t.itertuples()]))
        else:
            return {"value": "0 POs", "desc": "No pending POs found", "color": GREY, "extra": "No data"}
                    
        return {
            "value": f"{r_day['open_pos'] if r_day else 0} POs", 
            "desc": "Pending PO Status", 
            "color": BLUE if (r_day and r_day['open_pos'] > 0) else GREY,
            "extra": total_txt, 
            "details": details
        }
    # ---------- PURCHASE: PENDING PO ----------
    if calc == "po_pending":
        cols = spec.get("columns")
        r_day = po_pending(df, day, cols, only_day=True)       # selected date ke POs
        r_all = po_pending(df, datetime.date.max, cols)        # poori sheet ka total pending
        uom = lambda r: " · ".join(f"{k or 'units'}: {v:,.0f}" for k, v in r["qty_by_uom"].items())
        total_txt = (f"Total pending (all dates): {r_all['open_pos']} POs"
                    + (f" | {uom(r_all)}" if r_all["qty_by_uom"] else "")) if r_all else None
        if r_day is None:
            return {"value": "0 POs", "desc": "No PO dated on this date", "color": None, "extra": total_txt}
        return {"value": f"{r_day['open_pos']} POs", "desc": uom(r_day) or None,
                "color": None, "extra": total_txt}

    # ---------- PURCHASE: PURCHASE TILL DATE ----------
    if calc == "purchase_mtd":
        # Aapki sheet mein 'Date' column hai, usko parse karein
        df["_date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce").dt.date
        
        # 1. Month ka data (1st date se selected date tak)
        m_start = day.replace(day=1)
        sub_month = df[(df["_date"] >= m_start) & (df["_date"] <= day)]
        
        # 2. Day ka data (sirf selected date)
        sub_day = df[df["_date"] == day]
        
        # 3. Total data (All time)
        sub_all = df[df["_date"] <= day]

        if sub_month.empty:
            return {"value": "₹0", "desc": "No purchase this month", "color": None}

        # Bill Amount nikalne ka function
        def get_bill_amt(sub_df):
            if sub_df.empty: return 0.0
            if "Bill Amount" in sub_df.columns:
                return float(_num(sub_df["Bill Amount"]).sum())
            return 0.0

        day_amt = get_bill_amt(sub_day)
        month_amt = get_bill_amt(sub_month)
        total_amt = get_bill_amt(sub_all)

        # Card ke upar 3 Tiles (Day, Month, Total)
        metrics = [
            (f"{day_amt:,.0f}", f"Day Bill Amt ({day.strftime('%d-%m')})"),
            (f"{month_amt:,.0f}", f"Month Bill Amt ({day.strftime('%b-%y')})"),
            (f"{total_amt:,.0f}", "Total Bill Amt")
        ]

        return {
            "value": _inr(month_amt),  # Bada text Month amount dikhayega
            "desc": "Purchase Summary", 
            "color": BLUE, 
            "metrics": metrics
        }

    # ---------- HR ----------
    if calc in ("hr_manpower", "hr_overtime", "hr_dept"):
        d = _hr_daily(df)
        tot = d.groupby("_date")[["man", "ot"]].sum()
        if day not in tot.index:
            return None
        man, ot = float(tot.loc[day, "man"]), float(tot.loc[day, "ot"])
        month = tot[(tot.index >= day.replace(day=1)) & (tot.index <= day) & (tot["man"] > 0)]
        n = len(month)
        if calc == "hr_manpower":
            avg = month["man"].mean() if n else 0
            return {"value": f"{man:,.0f} Present",
                    "desc": f"Monthly avg: {avg:,.1f} per working day",
                    "color": BLUE, "extra": f"Working days this month (till date): {n}"}
        if calc == "hr_overtime":
            avg = month["ot"].mean() if n else 0
            return {"value": f"{ot:,.0f} Hrs",
                    "desc": f"Monthly avg: {avg:,.1f} Hrs per working day",
                    "color": BLUE, "extra": f"Total OT this month (till date): {month['ot'].sum():,.0f} Hrs"}
        day_d = d[(d["_date"] == day) & (d["man"] > 0)].sort_values("man", ascending=False)
        top = " | ".join(f"{r.dept.title()}: {r.man:.0f}" for r in day_d.head(3).itertuples())
        return {"value": f"{len(day_d)} Depts present", "desc": top or "No attendance",
                "color": BLUE, "extra": f"Total manpower: {man:,.0f}"}

    # ---------- FALLBACK ----------
    if spec.get("parts"):
        v = compute(df, spec, day)
        return None if v is None else {"value": v, "desc": None, "color": None}
    else:
        return {"value": "Not configured", "desc": "No calculation defined for this KPI", "color": GREY}


def parse_production_matrix(df):
    if df.empty or len(df) < 3:
        return pd.DataFrame(), []

    df = df.dropna(how='all').reset_index(drop=True)

    # Header row dhoondo (jahan DATE ya ITEM likha ho)
    header_idx = 0
    for i in range(min(10, len(df))):
        row_str = " ".join([str(x).upper() for x in df.iloc[i].values])
        if "DATE" in row_str and ("ITEM" in row_str or "EFFICIENCY" in row_str):
            header_idx = i
            break

    if header_idx >= len(df) - 1:
        return pd.DataFrame(), []

    headers = df.iloc[header_idx].astype(str).str.strip().tolist()

    item_col_idx = None
    for i, h in enumerate(headers):
        if "ITEM" in str(h).upper() or "GRADE" in str(h).upper():
            item_col_idx = i
            break

    date_columns = {}
    current_date = None

    for idx, cell in enumerate(headers):
        if cell:
            try:
                parsed_dt = pd.to_datetime(cell, format="%d-%b-%y", errors="coerce")
                if pd.notna(parsed_dt):
                    current_date = parsed_dt.date()
            except:
                pass

        if current_date:
            sub = str(headers[idx]).lower()
            if 'actual production' in sub or 'g tot' in sub:
                if current_date not in date_columns:
                    date_columns[current_date] = {}
                date_columns[current_date]["prod_col"] = idx
            elif 'efficiency' in sub or '%' in sub:
                if current_date not in date_columns:
                    date_columns[current_date] = {}
                date_columns[current_date]["eff_col"] = idx

    if not date_columns and header_idx + 1 < len(df):
        second_row = df.iloc[header_idx + 1].astype(str).str.strip().tolist()
        current_date = None
        for idx, cell in enumerate(headers):
            if cell:
                try:
                    parsed_dt = pd.to_datetime(cell, format="%d-%b-%y", errors="coerce")
                    if pd.notna(parsed_dt):
                        current_date = parsed_dt.date()
                except:
                    pass

            if current_date:
                sub = second_row[idx].lower() if idx < len(second_row) else ""
                if 'actual production' in sub or 'g tot' in sub:
                    if current_date not in date_columns:
                        date_columns[current_date] = {}
                    date_columns[current_date]["prod_col"] = idx
                elif 'efficiency' in sub or '%' in sub:
                    if current_date not in date_columns:
                        date_columns[current_date] = {}
                    date_columns[current_date]["eff_col"] = idx

    available_dates = list(date_columns.keys())
    records = []

    start_row = header_idx + 2
    for idx in range(start_row, len(df)):
        row = df.iloc[idx]

        item_name = "Unknown"
        if item_col_idx is not None and item_col_idx < len(row):
            item_name = str(row.iloc[item_col_idx]).strip()
            if item_name in ["None", "nan", ""]:
                item_name = "Unknown"

        for dt, cols in date_columns.items():
            try:
                prod_val = 0.0
                eff_val = 0.0

                if "prod_col" in cols and cols["prod_col"] < len(row):
                    prod_val = pd.to_numeric(str(row.iloc[cols["prod_col"]]).replace(',', '').replace('%', ''), errors='coerce')
                if "eff_col" in cols and cols["eff_col"] < len(row):
                    eff_val = pd.to_numeric(str(row.iloc[cols["eff_col"]]).replace(',', '').replace('%', ''), errors='coerce')

                if item_name != "Unknown":
                    records.append({
                        "Date": dt,
                        "Item": item_name,
                        "ActualProduction": prod_val if pd.notna(prod_val) else 0.0,
                        "Efficiency": eff_val if pd.notna(eff_val) else 0.0
                    })
            except Exception:
                continue

    return pd.DataFrame(records), available_dates


# ====================================================================
# 4. SETTINGS
# ====================================================================
BLUE = "#2563eb"
GREY = "#475569"
RED = "#dc2626"
AMBER = "#b45309"

REFRESH_SECONDS = 300
IST = ZoneInfo("Asia/Kolkata")
DATE_FMT = "%d-%m-%Y"

# ====================================================================
# 5. DATA SOURCES  <<< the only part to edit
# 5a. SHEETS
# ====================================================================
SHEETS = {
    "purchase_po": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRMyHArWBjTjiS4_B9LMLIkR2mYOVhviB5Yb-uQZ3sUWZV1W6dhkxQ6njifhKMIGq8eCCoK9U9dqz12/pubhtml",
        "worksheet": "0",          # gid of the 'Consolidated' tab
        "date_col": "PO Date",     # date of each PO line
        "dayfirst": False,         # dates are month/day/year (e.g. 10/14/2026)
        "anchor": "PO #",          # a row with a PO # starts a new PO line
        "ffill": ["PO #", "PO Date", "Supplier Name", "Category", "Item Description",
                "UoM", "PO Qty", "PO Rate"],   # copied down onto the invoice rows below
        "extra_date_cols": ["Recd Date"],        # receipt dates also appear in the date dropdown
        "ignore_cols": ["Status"],               # dropdown-only column (not used to detect blank rows)
    },
    "purchase_excel": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/purchase.xlsx", # <-- .csv ki jagah .xlsx kar diya
        "sheet_name": "purchase", # <-- Yeh wahi tab ka naam hai jo screenshot mein neeche highlight hai (purchase)
        "date_col": "Date",        # <-- Aapki file mein date column ka naam 'Date' hai
        "dayfirst": True, 
    },
"dead_stock_store": {
    "type": "gsheet",
    "static": True,
    "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSPNIfe4wJlXo4NDQ25eMmQgreu3CEioxI6sBfTCgsJQqPUGtBvYHQf24yCq-gTAGf4KN3qTNEXkxpy/pubhtml",
    "sheet_name": "Monthly",
    "date_col": "MATERIAL",
},
    "serviceability_live": {
        "type": "serviceability",
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRvqJtmKH0joq5-PXPaoxw1_x7mCTjCOK1RjnpU9ssGA4c5Xfp0sUhek56whkI2XNAxgXonXPqC75tF/pubhtml",
        "worksheet": "0",
    },
    "quality_complaints": {
        "type": "complaints",
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT7oigcyMG9P2uflYPMo_i75-IQW1dBS2AVeOqW8qT0bDJ6Drb2CUaluFGS_Gi_1vq6viA22BvYeoyY/pubhtml",
        "worksheet": "1131499541",          # apne tab ka gid
    },
    "finance_due_m": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/total%20Due%20Data.xls",
        "sheet_name": "Sheet1",      # <- tab ka exact naam
        "date_col": "Month",
    },
   "sales_report": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/All_Years_Sale_Data.xlsx",
        "sheet_name": "Sales Data",
        "date_col": "MONTH",
        "dayfirst": True,
    },
    "daily_sales_report": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/DAILY%20BASIS%20SALES.xlsx?v=3",
        "sheet_name": "DAILY BASIS SALES",
        "date_col": "DATE",
        "dayfirst": True,
    },
    "production_logs": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/All%20shed%20production%202026-27%20(5).xlsx",
        "sheet_name": "FY2026-27 Prod. Sheet",
        "date_col": "DATE",
        "dayfirst": True,
    },
    # D-Shed (Yield ke liye)
    "d_shed": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Shed-D%20Bdls%2BProd%20(1).xlsx",
        "sheet_name": "Shed-D Bdls+Prod",
        "date_col": "DATE",
        "dayfirst": True,
    },
    # E-Shed (Yield ke liye)
    "e_shed": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Shed-E%20Bdls%2BProd.xlsx",
        "sheet_name": "Shed-E Bdls+Prod",
        "date_col": "DATE",
        "dayfirst": True,
    },
    # B-Shed (Yield ke liye)
    "b_shed": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/B-Shed%20Mtrs%2BRolls%2BProd.xlsx",
        "sheet_name": "B-Shed Mtrs+Rolls+Prod",
        "date_col": "DATE",
        "dayfirst": True,
    },
    # C-Shed (Yield ke liye)
    "c_shed": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/C-Shed%20Mtrs%2BRolls%2BProd%20(1).xlsx",
        "sheet_name": "C-Shed Mtrs+Rolls+Prod",
        "date_col": "DATE",
        "dayfirst": True,
    },
"dispute_cases": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Dispute%20Cases%20Values%20%26%20Numbers.xlsx",
        "sheet_name": "Sheet1",
        "date_col": "Party Name",
    },
"cate_1": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/cate%20(1).xls",
        "sheet_name": 0,
        "date_col": "Grade",
    },
"min_stock": {
    "type": "excel",
    "static": True,
    "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Stock%20Minimum%20Balance%20(2).xlsx?v=8", 
    "sheet_name": "Sheet1",
    "date_col": "ITEM NAME",  # <--- Ye line add karein
},
    # D + E shed ka Bdls + Prod
    "bdls_de": {
        "type": "bdls_de",
        "url": "bdls_de",
        "files": (
            ("D Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Shed-D%20Bdls%2BProd.xlsx", "Shed-D Bdls+Prod"),
            ("E Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Shed-E%20Bdls%2BProd.xlsx", "Shed-E Bdls+Prod"),
        ),
    },
    # D + E shed ka COMBINED yield (D-Shed(yield).xlsx + E-Shed.xlsx, pehli sheet/tab padhi jaati hai)
    "d_yield": {
        "type": "dyield",
        "url": "d_yield",
        "files": (
            ("D Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/D-Shed%28yield%29.xlsx"),
            ("E Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/E-Shed.xlsx"),
        ),
    },
    # B + C shed ka COMBINED yield (B-Shed.xlsx + C-Shed.xlsx, pehli sheet/tab padhi jaati hai)
    "bc_yield": {
        "type": "dyield",
        "url": "bc_yield",
        "files": (
            ("B Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/B-Shed%20(1).xlsx"),
            ("C Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/C-Shed.xlsx"),
        ),
    },
    # F-Shed (Rollpack) ki yield: repo mein pehle se maujood F-Shed (1).xlsx, tab 'F-Shed'
    "f_yield": {
        "type": "dyield",
        "url": "f_yield",
        "files": (
            ("F Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/F-Shed%20(1).xlsx", "F-Shed"),
        ),
    },
    # M-Shed (Mattress) ki yield: repo ki M-Shed (4).xlsx, tab 'M-Shed' (DATE, ITEM, M-SHED)
    "m_yield": {
        "type": "dyield",
        "url": "m_yield",
        "files": (
            ("M Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/M-Shed%20(4).xlsx", "M-Shed"),
        ),
    },
    "rolls_bc": {
        "type": "rolls_bc",
        "url": "rolls_bc",
        "files": (
            ("B Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/B-Shed%20Mtrs%2BRolls%2BProd.xlsx", "B-Shed Mtrs+Rolls+Prod"),
            ("C Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/C-Shed%20Mtrs%2BRolls%2BProd.xlsx", "C-Shed Mtrs+Rolls+Prod"),
        ),
    },
"received_new": {
    "type": "excel",
    "static": True,
    "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Recieved%20.xlsx",
    "sheet_name": "Recieved ",
    "date_col": "PARTY NAME",
},
"paid_data": {
    "type": "excel",
    "static": True,
    "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/paid.xlsx",
    "sheet_name": "paid",
    "date_col": "Party Name ",
},
"purchase_daily": {
    "type": "excel",
    "static": True,
    "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/purchase.xls",
    "sheet_name": 0,
    "date_col": "Date",
},

    "maintenance_logs": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTrPocQhFp-3kIL0QhVYFzIrkD5Wd5QmoShNK3i08MZSx4Wu59y25d0uo687C71guf3vc5FdNcM56_H/pubhtml",
        "worksheet": "0",
        "date_col": "Breakdown Date",
        "dayfirst": True
    },
"cn_sheet": {
    "type": "excel",
    "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/cn.xls",
    "sheet_name": "cn",
    "date_col": "Credit Note Date",
},
"dn_sheet": {
    "type": "excel",
    "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/dn.xls",
    "sheet_name": "dn",
    "date_col": "DEBIT NOTE DATE",
},

    "foaming_chemicals": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Chemical%20Consumption.xlsx",
        "sheet_name": "Data",
        "date_col": "MONTH",
        "dayfirst": True
    },
    "finance_ageing_new": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Greater%20Than%2090-%20180%20Days.xls",
        "sheet_name": "90-180",      # <- tab ka exact naam (neeche dekho)
        "date_col": "Party Name",
    },
"finance_gt90": {
    "type": "excel",
    "static": True,
    "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Greater%20Than%2090-%20180%20Days.xls", # URL yahan daalein
    "sheet_name": "90-180", # Jo bhi tab ka naam ho (screenshot mein 90-180 dikh raha hai)
    "date_col": "Party Name", # Static hai isliye koi bhi column daal dein
},

    "stock_data": {
        "type": "stock",
        "url":  "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/STOCK.xlsx",
        "sheet_name": "Inventory Data",
    },
    "freight_data": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ3meZTQ5PvgX63s8_3Nc87WfD-RzNXc9fu8t_hmlZZ2g3VAffZn01a__L7WtKTTPPbuTRFOwZC-mLh/pubhtml",
        "worksheet": "1511781172",
        "date_col": "DATE",
        "dayfirst": False,
        "ignore_cols": ["MONTH"],
    },

    "hr_manpower": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vR4PjMPwxSrMxWE010j_3E4TXjUmmHo9nERPYUcTKfrHE9C_NeR-HbC50QrpKc8Yw/pubhtml",
        "worksheet": "1154348919",
        "date_col": "DATE",
        "dayfirst": True,
    },
    "projects_data": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/projects.xlsx",
        "sheet_name": "Sheet1",
        "date_col": "Status",
    },
    "rnd_data": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/rnd.xlsx",
        "sheet_name": "Sheet1",
        "date_col": "Status",
    },
    "grade_category": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Grade%20wise%20category.xlsx",
        "sheet_name": "Grade+Category",
        "date_col": "GRADE",
        "static": True,
    },
    "order_management_1":  {
        "type": "orders",
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQZiVAgR2AeNLr-IZ-mW2g7Zp-Kye0IRyKtn7KjI_ygm_fGNPE4SB2BljpBmAHf4unirihIGmHrksr/pubhtml",
        "worksheet": ["0", "1151895349", "416003397"],
        "date_col": "DATE",
        "dayfirst": True,
        "ignore_cols": ["REASON", "FIN", "RATE", "PRINT", "SALEMAN", "DATE", "ORDER DATE"],
    },
"received_data": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/received.xls",
        "sheet_name": "received",
        "date_col": "Party Name",
    },
    "order_management_2": {
        "type": "orders",
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQPbaL4BPlem2VWDDRd9glmGZibz0p4A8tClU_J7Ct7MYURcHcKDcvh9AwIN4-n3LNm9Xixvg8SW0Ri/pubhtml",
        "worksheet": ["648729418"],
        "date_col": "ORDER DATE",
        "dayfirst": True,
        "ignore_cols": ["REASON", "FIN", "RATE", "PRINT", "SALEMAN", "DATE", "ORDER DATE"],
    },
    "tdi_data": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/tdi.xlsx?v=2", # <-- Yahan exact naam aur version dala hai
        "sheet_name": "tdi",
        "date_col": "Date",
        "dayfirst": True,
    },
  "pop_data": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/pop.xlsx",
        "sheet_name": "pop",
        "date_col": "Date",
        "dayfirst": True,
    },
    "poly_data": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/polyol.xls",
        "sheet_name": "polyol",
        "date_col": "Date",
        "dayfirst": True,
    },
    "lb_stock_data": {
        "type": "gviz",
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSbP2V-mXI6R5hS_u_aktc7B0j4N3fiVV-bm3BgAgkgxKpcrzUP4_esIunwZsyQILmFpuRu-643OOFV/pubhtml",
        "worksheet": "0", 
    },
    # Tonnage Foaming daily files: har mahine ki nayi file ka ek ("url", "tab name") neeche add karte jao
    "foaming_daily": {
        "type": "chem_daily",
        "url": "foaming_daily",
        "files": (
            ("https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Chemical%20consumption%20Oct-2026%20daily.xlsx",
             "Chemical consumption Oct-2026 d"),
            # ("https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Chemical%20consumption%20Nov-2026%20daily.xlsx",
            #  "Chemical consumption Nov-2026 d"),
        ),
    },
    # Prod. Summary 26-27 (sheet "DATA") - grade-wise yield ke liye
    "prod_summary": {
        "type": "yield",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Prod.%20Summary%2026-27.xlsx?v=2",
        "sheet_name": "Prod. Summary 26-27",
    },
    "m_shed": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/M-Shed%20(4).xlsx",
        "sheet_name": "M-Shed",
        "date_col": "DATE",
        "dayfirst": True,
        "ignore_cols": ["MON"],
    },
    "f_shed": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/F-Shed%20(1).xlsx",
        "sheet_name": "F-Shed",
        "date_col": "DATE",
        "dayfirst": True,
    },
    "pm_schedule": {
        "type": "pm_sched",
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRsEykyS9wX0Pa4Tho2x3cIAlePZbzHKN9d2dLFfmvClYwCbxvT8XSDQrL7udC6vhpb02ex3Li36zrk/pubhtml",
        "worksheet": "0",     # sheet ke URL mein jo gid=XXXX hai wo number
    },
    "finance_ageing": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Ageing%20(2).xlsx",
        "sheet_name": "Ageing analysis",
        "date_col": "Month",
    },
    "finance_drs_crs_new": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/DRS%20%26%20CRS.xls",
        "sheet_name": "TBLNCE",     # <- .xls file ki tab ka exact naam
        "date_col": "Party Name",
    },
    "manual": {
        "url": "manual",
    },
}
# ====================================================================
# 5b. KPI_SOURCES  (key = (department key, KPI title exactly as on screen))
# ====================================================================
KPI_SOURCES = {
    ("purchase", "Pending PO"): {
        "sheet": "purchase_po",
        "mode": "on_date",
        "date_label": "PO date",
        "calc": "po_pending",
    },
    ("purchase", "PO 0-15 Days Old"):  {"sheet": "purchase_po", "mode": "as_of", "date_label": "as on", "calc": "po_age_0_15"},
    ("purchase", "PO 15-30 Days Old"): {"sheet": "purchase_po", "mode": "as_of", "date_label": "as on", "calc": "po_age_15_30"},
    ("purchase", "PO 30-60 Days Old"): {"sheet": "purchase_po", "mode": "as_of", "date_label": "as on", "calc": "po_age_30_60"},
    ("purchase", "PO 60+ Days Old"):   {"sheet": "purchase_po", "mode": "as_of", "date_label": "as on", "calc": "po_age_60_plus"},
    ("purchase", "Goods Below MS"): {"sheet": "min_stock", "calc": "min_stock"},
    ("purchase", "Purchase Till Date"): {
        "sheet": "purchase_excel",  # <-- Purana "purchase_po" hata kar yeh likhein
        "mode": "month",
        "date_label": "month to",
        "calc": "purchase_mtd",
        "basis": "received",
    },
("finance", "Total Amt Received / Paid"): {
    "sheet": "received_data",
    "calc": "total_received_paid",
},
    ("finance", "Total Amt Received / Paid"): {
        "sheet": "received_new",         # <- pehle received_data tha
        "calc": "total_received_paid",
    },
    ("finance", "Total Amt Received / Paid"): {
        "sheet": "received_data",         # <- received_new se badla (month-wise received.xls)
        "calc": "total_received_paid",
    },

    ("inventory", "Total Inventory Bundles (FG)"): {"sheet": "prod_summary", "calc": "total_inv"},
    ("inventory", "Dead Stock (Value & Qty)"): {"sheet": "dead_stock_store", "calc": "dead_stock_store"},

    # Production Department ke saare blocks ki live binding:
    ("production", "Total Production & Yield"): {"sheet": "production_logs", "calc": "prod_log", "type": "total"},
    ("production", "Bdls & Yield"):      {"sheet": "bdls_de", "calc": "bdls_de"},
    ("production", "Rolls & Yield"):     {"sheet": "rolls_bc", "calc": "rolls_bc"},
    ("production", "Mattress & Yield"):  {"sheet": "prod_summary", "calc": "mattress_sum"},
    ("production", "Pillow & Yield"):    {"sheet": "prod_summary", "calc": "pillow_sum"},
    ("production", "Mould"): {"sheet": "prod_summary", "calc": "mould_sum"},
    ("production", "Bonded"): {"sheet": "prod_summary", "calc": "bonded_sum"},
    ("production", "Rollpack & Yield"):  {"sheet": "production_logs", "calc": "prod_log", "type": "rollpack"},
    ("production", "SCRAP"):                   {"sheet": "prod_summary", "calc": "scrap_sum"},

    # <<< FREIGHT DATA SOURCE >>>
    ("other", "Freight Report"): {
        "sheet": "freight_data",
        "calc": "freight_mtd",
    },
    ("other", "Customer Complaints"): {
        "sheet": "quality_complaints",
        "calc": "complaints",
    },
    ("finance", "Receivable / Payable Days"): {
        "sheet": "finance_drs_crs_new",
        "calc": "finance_recv_pay_days",
    },

    # <<< Maintenance  >>>
    # <<< Maintenance  >>>
    # <<< Maintenance  >>>
    ("maint", "Current Breakdown Machines"): {
        "sheet": "maintenance_logs",
        "calc": "maint_breakdown",
    },
    ("maint", "Preventive Maintenance %"): {
        "sheet": "pm_schedule",
        "calc": "maint_pm",
    },
    ("maint", "Total Downtime"): {
        "sheet": "maintenance_logs",     # wahi sheet jo Breakdown card use karta hai
        "calc": "maint_downtime",
    },
    # <<< ORDER MANAGEMENT DATA SOURCE >>>
    ("order", "Orders 0-7 Days Old"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_age_0_7"},
    ("order", "Orders 7-14 Days Old"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_age_7_14"},
    ("order", "Orders 14-21 Days Old"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_age_14_21"},
    ("order", "Orders 21+ Days Old"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_age_21_plus"},
    ("order", "Orders Left (No. / Qty)"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_pending"},
    ("order", "Current Schedule"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_current_schedule"},
    ("order", "Serviceability %"): {"sheet": "serviceability_live", "calc": "serviceability_live"},
    ("order", "Orders Not Approved"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_not_approved"},
    ("projects", "Target vs Completed"): {"sheet": "projects_data", "calc": "projects_target"},
    ("rnd", "Product Development Pending vs Completed"): {"sheet": "rnd_data", "calc": "rnd_pending"},

    # <<< FINANCE DATA SOURCE >>>
    ("finance", "Total Drs & Crs"): {
        "sheet": "finance_drs_crs_new",     # <- pehle finance_drs_crs_m tha
        "calc": "finance_drs_crs_month",
    },
    ("finance", "Greater Than 90 / 180 Days"): {
        "sheet": "finance_ageing_new",
        "calc": "finance_gt90_month",
    },
    ("finance", "Total Due (Drs & Crs)"): {
        "sheet": "finance_due_m",
        "calc": "finance_total_due_month",
    },
    ("finance", "CREDIT NOTE (CN)"): {
        "sheet": "cn_sheet",      # Yahan apni CN wali sheet ka naam daalein
        "calc": "credit_note",
    },
    ("finance", "Dispute Cases"): {"sheet": "dispute_cases", "calc": "finance_dispute"},
    ("finance", "DEBIT NOTE (DN)"): {
        "sheet": "dn_sheet",      # Yahan apni DN wali sheet ka naam daalein
        "calc": "debit_note",
    },
    # <<< SALES DATA SOURCE >>>
    ("sales", "Last Day Sale (Value & Bdls)"): {
        "sheet": "daily_sales_report",
        "calc": "sales_daily",
        "show_date": True,
    },
    ("sales", "T/O in This Month"): {
        "sheet": "daily_sales_report",
        "calc": "sales_daily_mtd",
    },
    ("sales", "Category Mix (Pcs)"): {"sheet": "prod_summary", "calc": "category_mix_pcs"},
    ("sales", "Category Mix (Kgs)"): {"sheet": "prod_summary", "calc": "category_mix_kgs"},
    ("hr", "Manpower Present & Monthly Avg"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hrg_manpower"},
    ("hr", "Overtime & Monthly Avg"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hrg_overtime"},
    ("hr", "Dept-wise Report"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hrg_dept"},
    ("hr", "Staff / Helper / Supervisor %"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hrg_staff"},


    ("foaming", "Tonnage Foaming"): {
        "sheet": "foaming_chemicals",     # monthly sheet (purane mahine, jahan daily data nahi hai)
        "calc": "tonnage_daily",
        "date_label": "as on",
        "col": "CONS",
    },

    ("foaming", "Poly Stock"): {
        "sheet": "poly_data",
        "calc": "poly_balance",
        "date_label": "as on",
    },
    ("foaming", "TDI Balance"): {
        "sheet": "tdi_data",
        "calc": "tdi_balance",
        "date_label": "as on",
    },
    ("foaming", "Pop Polymer"): {
        "sheet": "pop_data",
        "calc": "pop_balance",
        "date_label": "as on",
    },
    ("foaming", "LB Stock"): {
        "sheet": "lb_stock_data",
        "calc": "lb_stock",
        "date_label": "as on",
    },
}
# Shown on KPI blocks that have no source yet, so "Not connected" always says why.
MISSING_SOURCE = {
    ("purchase", "Goods Below MS"): "Needs a stock tab with item, current stock and minimum stock columns "
                                    "(not in the PO 'Consolidated' tab)",
    ("production", "Average Manpower (Section-wise)"): "Section-wise manpower sheet is not connected yet",
    ("production", "Targets"): "Production target sheet is not connected yet",
    ("finance", "Dispute Cases"): "Dispute cases sheet is not connected yet",
    ("other", "Material Returns"): "Material returns sheet is not connected yet",
    ("other", "Capacity Utilisation"): "Max capacity + actual production data is not connected yet",
}
DEFAULT_MISSING = "Source tab not provided yet (the PO STATUS sheet only holds purchase-order rows)"

# ====================================================================
# 6. LINKS
# ====================================================================
PURCHASE_SHEET = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRMyHArWBjTjiS4_B9LMLIkR2mYOVhviB5Yb-uQZ3sUWZV1W6dhkxQ6njifhKMIGq8eCCoK9U9dqz12/pubhtml"
)
PURCHASE_POWERBI = (
    "https://app.powerbi.com/groups/me/reports/"
    "3ac01124-e935-4964-a7b1-2436d90f0787/0ae022176631890e2147?experience=power-bi"
)
POWERBI_NOTE = (
    "Power BI links are used only as 'open report' buttons. To read numbers from Power BI "
    "the app needs an Azure AD app registration (service principal) with access to the "
    "workspace and the Power BI REST API 'executeQueries' endpoint on the semantic model; "
    "the client secret must live in .streamlit/secrets.toml on the server, never in this file. "
    "Until then, Google Sheets is the only data source."
)

# ====================================================================
# 7. DEPARTMENT CONFIGURATION (unchanged)
# ====================================================================
DEPARTMENTS = [
    {
        "key": "foaming",
        "icon": "🏢",
        "name": "FOAMING DEPARTMENT",
        "kpis": [
            ("Tonnage Foaming", "Month-to-date production"),
            ("LB Stock", "Long block: Qty / Weight"),
            ("Poly Stock", "Chemical stock"),
            ("TDI Balance", "Chemical balance"),
            ("Pop Polymer", "Pop polymer stock"),
        ],
        "links": [
            ("📊 Tonnage Dashboard (Power BI)", None),
            ("📈 Chemical Status Sheet (Google Sheets)", None),
            ("📋 LB Stock Ledger (Google Sheets)", None),
        ],
    
    },
    {
        "key": "online",
        "icon": "🛍️",
        "name": "ONLINE BUSINESS",
        "kpis": [
            ("Online Business Expenses", "Month wise"),
        ],
        "links": [
            ("📋 Online Expense Sheet", None),
        ],
    },
    {
        "key": "production",
        "icon": "⚙️",
        "name": "PRODUCTION",
        "kpis": [
            ("Total Production & Yield", "All products aggregated"),
            ("Bdls & Yield", "Bundle production"),
            ("Rolls & Yield", "Roll production"),
            ("Mattress & Yield", "Mattress production"),
            ("Pillow & Yield", "Pillow production"),
            ("Mould", "Mould production (J Shed)"),
            ("Bonded", "Bonded production (A Shed)"),
            ("Rollpack & Yield", "Rollpack production"),
            ("SCRAP", "Scrap production (O Shed)"),
        
        ],
        "links": [
            ("📊 Operational Yield View (Power BI)", "https://app.powerbi.com/groups/me/reports/f282dbe5-3439-4fa4-a5f0-8c379545e54e/52c82f933a4a050d4027?experience=power-bi"),
            ("📋 Plant Logs Register (Google Sheets)", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/All%20shed%20production%202026-27%20(4).xlsx"),
        ],
    },
    {
        "key": "order",
        "icon": "📦",
        "name": "ORDER MANAGEMENT",
        "kpis": [
            ("Orders 0-7 Days Old", "New pending orders"),
            ("Orders 7-14 Days Old", "Pending 7 to 14 days"),
            ("Orders 14-21 Days Old", "Pending 14 to 21 days"),
            ("Orders 21+ Days Old", "Critical: Pending > 21 days"),
            ("Orders Left (No. / Qty)", "Total pending combined"),
            ("Current Schedule", "Today's orders"),
            ("Serviceability %", "Approved vs Total"),
            ("Orders Not Approved", "Finance approval pending"),
            ("PPC Wise", "PPC wise pending orders"),  
    
        ],
        "links": [
            ("📊 Order Dispatch Console (Power BI)", None),
            # ("📋 Booking Tracker (Google Sheets)", None),   # purani line (link nahi tha)
            ("📋 Order Sheet 1 (Google Sheets)", "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQZiVAgR2AeNLr-IZ-mW2g7Zp-Kye0IRyKtn7KjI_ygm_fGNPE4SB2BljpBmAHf4unirihIGmHrksr/pubhtml"),
            ("📋 Order Sheet 2 (Google Sheets)", "https://docs.google.com/spreadsheets/d/e/2PACX-1vQPbaL4BPlem2VWDDRd9glmGZibz0p4A8tClU_J7Ct7MYURcHcKDcvh9AwIN4-n3LNm9Xixvg8SW0Ri/pubhtml"),
        ],
    },
    {
        "key": "sales",
        "icon": "💰",
        "name": "SALES",
        "kpis": [
            ("Last Day Sale (Value & Bdls)", "Last day invoiced"),
            ("T/O in This Month", "Progressive turnover"),
            ("Category Mix (Pcs)", "Pillow, Mattress, Sofa, Bonded"),
            ("Category Mix (Kgs)", "Baaki sab items"),
        ],
        "links": [
            ("📊 Target vs Actual Board (Power BI)", "https://app.powerbi.com/groups/me/reports/3c685d60-be8f-4d50-b1e2-a7032210f01c/cbfcf8c6633612b7f521?experience=power-bi"),
            ("📋 Corporate Billing Roll (Google Sheets)", None),
        ],
    },
    {
        "key": "purchase",
        "icon": "🛒",
        "name": "PURCHASE",
        "kpis": [
            ("Pending PO", "Awaiting delivery"),
            ("Goods Below MS", "Below minimum stock"),
            ("Purchase Till Date", "Value, month to date"),
            ("PO 0-15 Days Old", "Naye pending PO"),
            ("PO 15-30 Days Old", "Pending 15 to 30 days"),
            ("PO 30-60 Days Old", "Pending 30 to 60 days"),
            ("PO 60+ Days Old", "Critical: Pending > 60 days"),
        ],
        "links": [
            ("📊 Purchase Dashboard (Power BI)", PURCHASE_POWERBI),
            ("📋 PO Tracker (Google Sheets)", PURCHASE_SHEET),
        ],
    },
    {
        "key": "maint",
        "icon": "🔧",
        "name": "MAINTENANCE",
        "kpis": [
            ("Current Breakdown Machines", "Currently under repair"),
            ("Preventive Maintenance %", "Schedule completion"),
            ("Total Downtime", "Breakdown hours (Month / YTD)"),
        ],
        "links": [
            ("📊 Maintenance Dashboard (Power BI)", None),
            ("📋 Breakdown Log (Google Sheets)", "https://docs.google.com/spreadsheets/d/e/2PACX-1vTrPocQhFp-3kIL0QhVYFzIrkD5Wd5QmoShNK3i08MZSx4Wu59y25d0uo687C71guf3vc5FdNcM56_H/pubhtml"),
        ],
    },
    {
        "key": "inventory",
        "icon": "🏬",
        "name": "INVENTORY",
        "kpis": [
            ("Dead Stock (Value & Qty)", "RM / WIP / FG"),
            ("Total Inventory Bundles (FG)", "FG production"),
            ("Inventory Days & Turnover", "Current position"),
        ],
        "links": [
            ("📊 Inventory Dashboard (Power BI)", "https://app.powerbi.com/groups/me/reports/213585fe-d3cc-49f2-aa1e-8e88bacf3ba9/b34af97b42904dda828a?experience=power-bi"),
            ("📋 Stock Register (Google Sheets)", None),
        ],
    },
    {
        "key": "finance",
        "icon": "🏦",
        "name": "FINANCE",
        "kpis": [
            ("Total Drs & Crs", "Debtors & creditors"),
            ("Receivable / Payable Days", "Average days"),
            ("Total Amt Received / Paid", "Month to date"),
            ("Greater Than 90 / 180 Days", "Ageing buckets"),
            ("Total Due (Drs & Crs)", "Overdue amounts"),
            ("CREDIT NOTE (CN)", "Credit note, month wise"),
            ("DEBIT NOTE (DN)", "Debit note, month wise"),
            ("Dispute Cases", "Count & value (₹)"),
        ],
        "links": [
            ("📊 Finance Dashboard (Power BI)", None),
            ("📋 Ageing Report (Google Sheets)", None),
        ],
    },
    {
        "key": "hr",
        "icon": "👥",
        "name": "HR",
        "kpis": [
            ("Manpower Present & Monthly Avg", "Today vs average"),
            ("Overtime & Monthly Avg", "Today vs average"),
            ("Staff / Helper / Supervisor %", "Present breakdown"),
            ("Dept-wise Report", "Department-wise report"),
        ],
        "links": [
            ("📊 HR Dashboard (Power BI)", "https://app.powerbi.com/groups/me/reports/cbf9f67e-2ffb-4f44-beaa-b7a4f07d414a/827805f62902ee6ea980?experience=power-bi"),
            ("📋 Attendance Sheet (Google Sheets)", "https://docs.google.com/spreadsheets/d/e/2PACX-1vR4PjMPwxSrMxWE010j_3E4TXjUmmHo9nERPYUcTKfrHE9C_NeR-HbC50QrpKc8Yw/pubhtml"),
        ],
    },
    {
        "key": "other",
        "icon": "🗂️",
        "name": "OTHERS",
        "kpis": [
            ("Freight Report", "Month to date"),
            ("Safety", "Current month"),
            ("Quality", "Pass rate"),
            ("Audits", "Open audit points"),
            ("Customer-wise Target vs Sale", "Overall achievement"),
            ("Customer Complaints", "Total complaints, start se ab tak"),
            ("Material Returns", "Rejected goods returned: qty / value"),
            ("Capacity Utilisation", "Actual production / max capacity × 100"),
            ("Scrap By Product Management", "Scrap by product"),

        ],
        "links": [
            ("📊 Freight Report (Power BI)", "https://app.powerbi.com/groups/me/reports/43dfa27d-52db-4423-b40d-2732870ef9f2/d02bed28a39f2f8e3034?experience=power-bi"),
            ("📋 Safety & Quality Log (Google Sheets)", None),
            ("📊 Customer Target vs Sale (Power BI)", None),
        ],
    },
    {
        "key": "projects",
        "icon": "🏗️",
        "name": "PROJECTS",
        "kpis": [
            ("Target vs Completed", "Project target vs completed"),
        ],
        "links": [
            ("📋 Projects Sheet", None),
        ],
    },
    {
        "key": "rnd",
        "icon": "🔬",
        "name": "R&D (RESEARCH & DEVELOPMENT)",
        "kpis": [
            ("Product Development Pending vs Completed", "Pending vs completed products"),
        ],
        "links": [
            ("📋 R&D Sheet", None),
        ],
    },
]

# Dashboard mein departments ka order (upar se neeche)
DISPLAY_ORDER = ["foaming", "production", "order", "sales", "purchase",
                "inventory", "finance", "maint", "hr", "other","online", "projects", "rnd"]
DEPARTMENTS.sort(key=lambda d: DISPLAY_ORDER.index(d["key"]))


# ====================================================================
# 8. LIVE DATA LOADING  (cached, auto-refresh, last-good fallback)
# ====================================================================
def _service_account():
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass
    return None


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_cached(url, worksheet, date_col, dayfirst, has_account, anchor, ffill, extra, ignore):
    df = fetch_sheet(url, worksheet, _service_account() if has_account else None, header_hint=date_col)
    df = prepare(df, date_col, dayfirst, ffill, anchor, extra, ignore)
    return df, datetime.datetime.now(IST)


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_multi_cached(url, gids, date_col, dayfirst, ignore):
    """Ek Google workbook ke kai tabs ko jodkar ek table banata hai."""
    frames, problems = [], []
    for gid in gids:
        try:
            d = fetch_sheet(url, gid, None, header_hint=None).copy()
            d["TAB_GID"] = str(gid)
            frames.append(d)
        except Exception as exc:
            problems.append(f"gid {gid}: {type(exc).__name__}: {exc}")

    if not frames:
        raise DataError("No data found in any tab. " + " | ".join(problems))

    df = pd.concat(frames, ignore_index=True, sort=False).fillna("")

    header_idx = 0
    for i in range(min(10, len(df))):
        row_str = " ".join([str(x).upper() for x in df.iloc[i].values])
        if "ORDER NO" in row_str or "DATE" in row_str:
            header_idx = i
            break

    df.columns = df.iloc[header_idx].astype(str).str.strip()
    df = df.iloc[header_idx + 1:].copy()

    if date_col in df.columns:
        df[date_col] = df[date_col].astype(str).str.replace(".", "-", regex=False)

    out = prepare(df, date_col, dayfirst, (), None, (), tuple(ignore) + ("TAB_GID",))
    return out, datetime.datetime.now(IST)


# ---- ORDER SHEETS: order-number based loader (1 ORDER NO cell = 1 order) ----
_SPLIT = re.compile(r"[+,/&]")


def _key(s):
    return re.sub(r"[^A-Z]", "", str(s).upper())


def parse_order_date(s):
    """26.10.2026, 02/07/26, 13/7/26, 3.10.2026, 2026-10-26, 26-Oct-26, 9/30/2026 (US format) aur
    typos (22.102.2026, 15.10.206) -> date. Samajh na aaye to None."""
    s = str(s).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    try:
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)                        # 2026-10-26 (time ho to bhi)
        if m:
            return datetime.date(int(m[1]), int(m[2]), int(m[3]))
        m = re.match(r"^(\d{1,2})[ ./-]+([A-Za-z]{3,9})[ ./,-]+(\d{2,4})$", s)    # 26-Oct-26 / 26 Oct 2026
        if m:
            mon = datetime.datetime.strptime(m[2][:3].title(), "%b").month
            y = int(m[3]) + (2000 if int(m[3]) < 100 else 0)
            return datetime.date(y, mon, int(m[1]))
        m = re.match(r"^(\d{1,2})[./-](\d{1,3})[./-](\d{2,4})(?:\s.*)?$", s)       # 26.10.2026 / 26/10/26
        if not m:
            return None
        d, mo, y = int(m[1]), m[2], int(m[3])
        mo = int(mo[:2]) if len(mo) == 3 else int(mo)      # 102 -> 10
        if y < 100:
            y += 2000
        elif y == 206:                                     # 206 -> 2026
            y = 2026
        if mo > 12 and d <= 12:                            # 9/30/2026 (month/day) -> swap
            d, mo = mo, d
        return datetime.date(y, mo, d)
    except (ValueError, TypeError):
        return None


_DATE_LIKE = re.compile(r"^\d{1,2}[./-]\d{1,3}[./-]\d{2,4}$")


def order_tokens(cell):
    """Cell mein order number hai ya nahi: '5253+5257+5258' -> ['5253','5257','5258'], '5280-5321' -> ['5280-5321'].
    Khali / header text / 'ORDER NO.' -> []. (Ginti ke liye poori cell = 1 order, tokens sirf pehchan ke liye.)"""
    out = []
    for p in _SPLIT.split(str(cell)):
        p = p.strip()
        if re.fullmatch(r"\d{3,5}(\s*-\s*\d{3,5})?", p):
            out.append(re.sub(r"\s+", "", p))
    return out


def order_tab_to_df(rows, gid):
    """Ek tab ki csv rows -> ek row per ORDER NO cell.
    * Ek cell mein 2-3 number (5354+5355) = EK order.
    * Date column header se nahi, DATA dekh ke pehchana jata hai (header khali/badla ho tab bhi chale).
    * Khali rows, dobara aaye headers, section titles (HARD, PRINCE ORDER ...) order nahi bante."""
    rows = [[str(c).strip() for c in r] for r in rows]
    hdr = next((i for i, r in enumerate(rows) if any(_key(c) == "ORDERNO" for c in r)), None)
    if hdr is None:
        raise ValueError(f"tab {gid}: no 'ORDER NO' header row found")
    h = rows[hdr]
    oc = next(j for j, c in enumerate(h) if _key(c) == "ORDERNO")
    fc = next((j for j, c in enumerate(h) if _key(c).startswith("FINANCE")), None)
    pc = next((j for j, c in enumerate(h) if "PARTY" in _key(c)), None)

    def cell(r, j):
        return r[j] if j is not None and j < len(r) else ""

    data = [r for r in rows[hdr + 1:] if order_tokens(cell(r, oc))]
    data += [r for r in rows[hdr + 1:]
             if (not order_tokens(cell(r, oc))) and fc is not None and pc is not None
             and cell(r, fc).strip().upper() == "NOT APPROVED" and cell(r, pc).strip() != ""]

    # date column = jis column mein in order-rows ki sabse zyada dates parse hoti hain
    width = max((len(r) for r in rows), default=0)
    dc, best = None, 0
    for j in range(width):
        n = sum(1 for r in data if parse_order_date(cell(r, j)) is not None)
        if n > best:
            dc, best = j, n
    if dc is None:                                   # fallback: header mein DATE dhoondho
        for rr in (rows[hdr], *(rows[max(0, hdr - 2):hdr][::-1])):
            dc = next((j for j, c in enumerate(rr) if "DATE" in _key(c)), None)
            if dc is not None:
                break

    out = []
    for r in data:
        dt = parse_order_date(cell(r, dc))
        if dt is None:                               # chuni hui column mein na ho to row mein kahin bhi date jaisa text
            for c in r:
                if _DATE_LIKE.match(c) and parse_order_date(c):
                    dt = parse_order_date(c)
                    break
        fin = cell(r, fc).strip().upper()
        fin = "APPROVED" if fin == "APPROVED" else "NOT APPROVED" if fin == "NOT APPROVED" else ""
        raw = cell(r, oc)
        if not raw.strip():
            raw = f"NOORDER-{gid}-{len(out) + 1}"
        out.append({"ORDER NO": re.sub(r"\s+", "", raw).upper(), "FINANCE": fin, "_date": dt,
                    "TAB_GID": str(gid), "PARTY": cell(r, pc), "RAW_ORDER": raw})
    return pd.DataFrame(out, columns=["ORDER NO", "FINANCE", "_date", "TAB_GID", "PARTY", "RAW_ORDER"])


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_orders_cached(url, gids):
    """Order workbook: SAARE tabs alag-alag padho, har ORDER NO ek row.
    `gids` sirf fallback hain; tabs pubhtml se apne aap dhoondhe jaate hain (koi tab chhootega nahi)."""
    tabs = {str(g): f"Tab {g}" for g in gids}
    try:
        for tab_name, gid in discover_tabs(url):
            tabs[str(gid)] = tab_name
    except Exception as exc:
        log.warning("tab discovery failed for order sheet: %s", exc)
    base = url.split("/pub")[0]
    frames, problems = [], []
    for gid, tab_name in tabs.items():
        try:
            data = _http_get(f"{base}/pub?output=csv&gid={gid}")
            if data.lstrip()[:1] == b"<":
                raise PermissionError("tab is not published as CSV")
            rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
            d = order_tab_to_df(rows, gid)
            d["TAB_NAME"] = tab_name
            frames.append(d)
        except Exception as exc:
            problems.append(f"{tab_name} (gid {gid}): {type(exc).__name__}: {exc}")
    if problems:
        log.warning("order tabs skipped: %s", " | ".join(problems))
    if not frames:
        raise DataError("No data found in any order tab. " + " | ".join(problems))
    return pd.concat(frames, ignore_index=True), datetime.datetime.now(IST)


def get_sheet(name):
    """-> (DataFrame or None, error text or None, fetched-at or None)."""
    if isinstance(name, (list, tuple)):
        frames = []
        for n in name:
            df, err, fetched = get_sheet(n)
            if df is not None:
                frames.append(df)
        if not frames:
            return None, "No data from any sheet", None
        return pd.concat(frames, ignore_index=True, sort=False), None, fetched
    cfg = SHEETS.get(name)
    if not cfg or not cfg.get("url"):
        return None, f"sheet '{name}' has no link in SHEETS", None
    errors = st.session_state.setdefault("_errors", {})
    good = st.session_state.setdefault("_last_good", {})
    try:
        if cfg.get("type") == "complaints":
            df, fetched = _fetch_complaints_cached(cfg["url"], str(cfg.get("worksheet", "0")))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if cfg.get("type") == "gviz":
            base = cfg["url"].split("/pub")[0]
            csv_url = f"{base}/pub?output=csv&gid={cfg.get('worksheet', '0')}"
            data = _http_get(csv_url)
            if data.lstrip()[:1] == b"<":
                raise PermissionError("Google Sheet is not returning data; check that Publish to web is on.")
            df = _frame_from_csv(data, header_hint="GRADE")
            df["_date"] = datetime.datetime.now(IST).date()
            good[name] = (df, datetime.datetime.now(IST))
            errors.pop(name, None)
            return df, None, datetime.datetime.now(IST)
        if cfg.get("type") == "pm_sched":
            u = cfg["url"]
            csv_url = u if u.lower().split("?")[0].endswith(".csv") else f"{u.split('/pub')[0]}/pub?output=csv&gid={cfg.get('worksheet', '0')}"
            data = _http_get(csv_url)
            if data.lstrip()[:1] == b"<":
                raise PermissionError("Preventive sheet is not returning data; check that Publish to web is on.")
            df = pd.read_csv(io.BytesIO(data), header=None, dtype=str)
            df["_date"] = datetime.datetime.now(IST).date()
            good[name] = (df, datetime.datetime.now(IST))
            errors.pop(name, None)
            return df, None, datetime.datetime.now(IST)
        if cfg.get("type") == "orders":
            df, fetched = _fetch_orders_cached(cfg["url"], tuple(cfg.get("worksheet", ())))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if isinstance(cfg.get("worksheet"), (list, tuple)):
            df, fetched = _fetch_multi_cached(cfg["url"], tuple(cfg["worksheet"]), cfg["date_col"],
                cfg.get("dayfirst", True), tuple(cfg.get("ignore_cols", ())))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if cfg.get("type") == "chem_daily":
            df, fetched = _fetch_chem_daily_cached(tuple(cfg["files"]))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if cfg.get("type") == "dyield":
            if name == "m_yield":
                df, fetched = _fetch_m_shed_custom(cfg["files"][0][1])
            else:
                df, fetched = _fetch_dyield_cached(tuple(cfg["files"]))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if cfg.get("type") == "bdls_de":
            df, fetched = _fetch_shed_cached(tuple(cfg["files"]))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if cfg.get("type") == "rolls_bc":
            df, fetched = _fetch_rolls_cached(tuple(cfg["files"]))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if cfg.get("type") == "yield":
            df, fetched = _fetch_yield_cached(cfg["url"], cfg.get("sheet_name", "DATA"))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if cfg.get("type") == "serviceability":
            df, fetched = _fetch_serviceability_cached(cfg["url"], str(cfg.get("worksheet", "0")))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if cfg.get("type") == "stock":
            df, fetched = _fetch_stock_cached(cfg["url"], cfg["sheet_name"])
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        if cfg["url"] == "manual":
            now_ist = datetime.datetime.now(IST)
            df = pd.DataFrame({"_date": [now_ist.date()]})
            good[name] = (df, now_ist)
            errors.pop(name, None)
            return df, None, now_ist
        if cfg.get("type") == "excel":
            df, fetched = _fetch_excel_cached(cfg["url"], cfg["sheet_name"],
                cfg.get("date_col", ""), cfg.get("dayfirst", True),
                cfg.get("static", False))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched
        # Baaki normal Google Sheets (Purchase PO, Maintenance, Freight, HR ...)
        df, fetched = _fetch_cached(
            cfg["url"], cfg.get("worksheet"), cfg["date_col"],
            cfg.get("dayfirst", True), _service_account() is not None,
            cfg.get("anchor"), tuple(cfg.get("ffill", ())),
            tuple(cfg.get("extra_date_cols", ())), tuple(cfg.get("ignore_cols", ())),
        )
        good[name] = (df, fetched)
        errors.pop(name, None)
        log.info("sheet '%s' loaded: %d rows", name, len(df))
        return df, None, fetched
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        log.error("sheet '%s' failed: %s", name, msg)
        errors[name] = msg
        if name in good:
            return good[name][0], msg, good[name][1]
        return None, msg, None


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def get_serviceability_data(url, sheet_name):
    """Serviceability sheet (Month-wise rows, Shed-wise columns) ko padhta hai."""
    # ... aage ka code ...
    src = io.BytesIO(_http_get(_direct_url(url))) if re.match(r"^https?://", url or "") else url
    
    # Header=None se padho taaki header row apne aap dhoondh sakein
    raw = pd.read_excel(src, sheet_name=sheet_name, header=None, engine="openpyxl")
    
    # Header row dhoondho jahan "MONTH" likha ho
    hdr_idx = None
    for i, row in raw.iterrows():
        if any(str(c).strip().upper() == "MONTH" for c in row.tolist()):
            hdr_idx = i
            break
            
    if hdr_idx is None:
        raise DataError("'MONTH' header row not found in Serviceability sheet.")

    raw.columns = [str(c).strip().upper() for c in raw.iloc[hdr_idx].tolist()]
    df = raw.iloc[hdr_idx + 1:].copy() # Header ke neeche ka data
    
    # Columns clean karo
    df = df.loc[:, ~df.columns.duplicated()] # Duplicate columns hatao
    
    # Jo sheds chahiye (screenshot ke hisaab se)
    shed_cols = {
        "B+C": "B+C", "D": "D", "E": "E", "H": "H", "F": "F", 
        "2ND/X": "2ND/X", "3RD": "3RD", "PILLOW": "PILLOW", 
        "OTHER": "OTHER", "BONDED": "BONDED", "LOADING": "LOADING", 
        "APPC": "APPC", "LOCAL": "LOCAL"
    }
    
    # Columns jo actually sheet mein hain unhe filter karo
    available_sheds = {k: v for k, v in shed_cols.items() if k in df.columns}
    
    rows = []
    for _, row in df.iterrows():
        month_str = str(row.get("MONTH", "")).strip()
        if not month_str or month_str.upper() == "NAN":
            continue
            
        total_plan = _num(pd.Series([row.get("TOTAL PLAN", 0)])).iloc[0]
        total_dispatch = _num(pd.Series([row.get("TOTAL DISPATCH", 0)])).iloc[0]
        
        # Shed-wise data extract karo
        shed_data = {}
        for k, col_name in available_sheds.items():
            val = _num(pd.Series([row.get(col_name, 0)])).iloc[0]
            shed_data[k] = val
            
        rows.append({
            "month": month_str,
            "total_plan": total_plan,
            "total_dispatch": total_dispatch,
            "sheds": shed_data,
        })
        
    return rows, datetime.datetime.now(IST)

@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def get_serviceability_data(url, sheet_name):
    """Serviceability sheet (Month-wise rows, Shed-wise columns) ko padhta hai."""
    src = io.BytesIO(_http_get(_direct_url(url))) if re.match(r"^https?://", url or "") else url
    raw = pd.read_excel(src, sheet_name=sheet_name, header=None, engine="openpyxl")
    
    hdr_idx = None
    for i, row in raw.iterrows():
        if any(str(c).strip().upper() == "MONTH" for c in row.tolist()):
            hdr_idx = i
            break
            
    if hdr_idx is None:
        raise DataError("'MONTH' header row not found in Serviceability sheet.")

    raw.columns = [str(c).strip().upper() for c in raw.iloc[hdr_idx].tolist()]
    df = raw.iloc[hdr_idx + 1:].copy()
    df = df.loc[:, ~df.columns.duplicated()]
    
    shed_cols = {
        "B+C": "B+C", "D": "D", "E": "E", "H": "H", "F": "F", 
        "2ND/X": "2ND/X", "3RD": "3RD", "PILLOW": "PILLOW", 
        "OTHER": "OTHER", "BONDED": "BONDED", "LOADING": "LOADING", 
        "APPC": "APPC", "LOCAL": "LOCAL"
    }
    
    available_sheds = {k: v for k, v in shed_cols.items() if k in df.columns}
    rows = []
    for _, row in df.iterrows():
        month_str = str(row.get("MONTH", "")).strip()
        if not month_str or month_str.upper() == "NAN":
            continue
            
        total_plan = _num(pd.Series([row.get("TOTAL PLAN", 0)])).iloc[0]
        total_dispatch = _num(pd.Series([row.get("TOTAL DISPATCH", 0)])).iloc[0]
        
        shed_data = {}
        for k, col_name in available_sheds.items():
            val = _num(pd.Series([row.get(col_name, 0)])).iloc[0]
            shed_data[k] = val
            
        rows.append({
            "month": month_str,
            "total_plan": total_plan,
            "total_dispatch": total_dispatch,
            "sheds": shed_data,
        })
    return rows, datetime.datetime.now(IST)

def serviceability_card(day):
    import datetime
    day = datetime.date(day.year, day.month, 1)  # <--- Bas ye line add karein
    df, err, _ = get_sheet("serviceability")
    # ... aage ka code waise hi rahega ...
    if df is None:
        return {"value": "0.0%", "desc": f"Error: {err}", "color": RED}

    # 2. Selected month ka naam nikalain (Jaise "NOVEMBER" ya "OCTOBER")
    target_month = day.strftime("%B").upper()

    # 3. Sheet mein "MONTH" wala column dhoondhein
    month_col = next((c for c in df.columns if str(c).strip().upper() == "MONTH"), None)
    if not month_col:
        return {"value": "0.0%", "desc": "MONTH column not found", "color": RED}

    # 4. Us month ki row filter karein
    row_df = df[df[month_col].astype(str).str.strip().str.upper() == target_month]
    
    if row_df.empty:
        return {"value": "0.0%", "desc": f"No data for {target_month}", "color": GREY}

    # 5. Numbers nikalne ka helper (taki % ya comma se error na aaye)
    def get_val(col_name):
        c = next((x for x in df.columns if str(x).strip().upper() == col_name.upper()), None)
        if c:
            val = _num(row_df[c]).iloc[0]
            return float(val) if pd.notna(val) else 0.0
        return 0.0

    # 6. Values extract karein
    total_plan = get_val("TOTAL PLAN")
    total_dispatch = get_val("TOTAL DISPATCH")
    
    # Aapki sheet mein direct "SERVICEABILITY %" column hai, wahan se uthayenge
    pct = get_val("SERVICEABILITY %")
    
    # Agar wo column khali ho, toh backup ke liye calculate kar lein
    if pct == 0 and total_plan > 0:
        pct = (total_dispatch / total_plan) * 100

    # 7. Shed-wise data nikalein
    shed_details = []
    # Aapki sheet mein 'B+C', 'D', 'E', 'H' wagera columns hain. Hum unhe automatically utha lenge.
    shed_cols = ["B+C", "D", "E", "H", "F", "2NDX", "3RD", "PILLOW", "OTHER", "BLOCK", "BONDE D", "LOADING", "PPC", "LOCAL"]
    
    for shed_name in shed_cols:
        val = get_val(shed_name)
        if val > 0:
            shed_pct = (val / total_plan * 100) if total_plan > 0 else 0.0
            shed_details.append((shed_name, f"{val:,.0f} ({shed_pct:.1f}%)"))

    # 8. Return dictionary (Jo aapka dashboard padhta hai)
    return {
        "value": f"{pct:.1f}%",
        "desc": f"Serviceability for {target_month} (Plan: {total_plan:,.0f} | Dispatch: {total_dispatch:,.0f})",
        "color": BLUE if pct > 80 else RED,
        "metrics": [
            (f"{pct:.1f}%", "Serviceability", "yield"),
            (f"{total_plan:,.0f}", "Total Plan"),
            (f"{total_dispatch:,.0f}", "Dispatch"),
        ],
        "sections": [
            (f"🗓 {target_month.title()} Data", [
                ("Total Plan", f"{total_plan:,.0f}"),
                ("Total Dispatch", f"{total_dispatch:,.0f}"),
                ("Serviceability", f"{pct:.1f}%")
            ])
        ],
        "details": [
            (f"⚖ Shed-wise Data ({target_month.title()})", shed_details)
        ]
    }
# ====================================================================
# SERVICEABILITY  (Google Sheet "SERVICEABILITY" -> Sheet1, daily trucks)
#   Columns: A Date | B Planned | C Dispatch | D Left | E % |
#            F..O  MATERIAL NOT AVAILABLE (B,C,D,E,H,2ND/X,F,3RD,K-J,Other) |
#            P..S  Truck Not Available, LOCAL, Unable to Load, Other
# ====================================================================
SERV_MATERIAL = ["B", "C", "D", "E", "H", "2ND/X", "F", "3RD", "K-J", "Other"]
SERV_OTHER = ["Truck Not Available", "Local", "Unable to Load", "Other"]
SERV_MAT_START = 5      # column F
SERV_OTHER_START = 15   # column P
SERV_LABELS = {"B": "B Shed", "C": "C Shed", "D": "D Shed", "E": "E Shed", "H": "H Shed",
               "F": "F Shed", "2ND/X": "2ND/X", "3RD": "3RD", "K-J": "K-J", "Other": "Other"}


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_serviceability_cached(url, gid):
    """Google Sheet (Publish to web) ko seedha CSV ki tarah padhta hai. Har din ki ek row."""
    base = url.split("/pub")[0]
    data = _http_get(f"{base}/pub?output=csv&gid={gid}")
    if data.lstrip()[:1] == b"<":
        raise PermissionError("Google returned no data. 'Publish to web' the sheet "
                              "(File > Share > Publish to web) aur gid check karein.")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))

    # layout check: shed header row mein F=B ... N=K-J hona chahiye
    ok = any(len(r) > 13 and r[5].strip().upper() == "B" and r[13].strip().upper() == "K-J" for r in rows[:15])
    if not ok:
        raise DataError("Serviceability sheet layout has changed: shed header row (B, C, D, E, H, 2ND/X, "
                        "F, 3RD, K-J) column F se N tak nahi mili.")

    def n(v):
        try:
            return float(str(v).replace(",", "").strip())
        except ValueError:
            return 0.0

    recs = []
    for r in rows:
        r = list(r) + [""] * (19 - len(r))
        try:
            d = datetime.datetime.strptime(r[0].strip(), "%d-%b-%y").date()
        except ValueError:
            continue                                  # header / TOTAL / blank rows
        planned, dispatch = n(r[1]), n(r[2])
        if planned <= 0 and dispatch <= 0:
            continue                                  # chhutti / data bhara nahi
        rec = {"_date": d, "planned": planned, "dispatch": dispatch}
        for i, k in enumerate(SERV_MATERIAL):
            rec["m_" + k] = n(r[SERV_MAT_START + i])
        for i, k in enumerate(SERV_OTHER):
            rec["o_" + k] = n(r[SERV_OTHER_START + i])
        recs.append(rec)
    if not recs:
        raise DataError("No row with a valid date found in Serviceability sheet.")
    df = pd.DataFrame(recs).drop_duplicates("_date", keep="last").sort_values("_date").reset_index(drop=True)
    return df, datetime.datetime.now(IST)


def _sq(v):
    v = float(v)
    return f"{v:,.0f}" if abs(v - round(v)) < 1e-9 else f"{v:,.1f}"


def _serv_agg(frame):
    p, dsp = float(frame["planned"].sum()), float(frame["dispatch"].sum())
    return {
        "planned": p, "dispatch": dsp, "left": p - dsp,
        "pct": (dsp / p * 100) if p else 0.0,
        "mat": {k: float(frame["m_" + k].sum()) for k in SERV_MATERIAL},
        "oth": {k: float(frame["o_" + k].sum()) for k in SERV_OTHER},
    }


def _serv_trucks_rows(a):
    return [("Total Trucks Planned", _sq(a["planned"])), ("Total Trucks Dispatch", _sq(a["dispatch"])),
            ("Total Trucks Left", _sq(a["left"])), ("Serviceability %", f"{a['pct']:.1f}%")]


def _serv_mat_rows(a):
    rows = [(SERV_LABELS[k], f"{_sq(v)} trucks") for k, v in a["mat"].items() if v > 0]
    tot = sum(a["mat"].values())
    return rows + [("TOTAL (no material)", f"{_sq(tot)} trucks")] if rows else \
        [("Material not available", "Not Any Entry In Shed")]


def _serv_oth_rows(a):
    rows = [(k, f"{_sq(v)} trucks") for k, v in a["oth"].items() if v > 0]
    tot = sum(a["oth"].values())
    return rows + [("TOTAL (other reasons)", f"{_sq(tot)} trucks")] if rows else \
        [("Other reasons", "✅ None")]


def serviceability_card_live(day):
    """Selected date ki serviceability + ruki hui gaadiyon ke karan (shed-wise / other), month aur all-months."""
    df, err, _ = get_sheet("serviceability_live")
    if df is None:
        return {"value": "0.0%", "desc": f"Error: {err}", "color": RED}

    d_df = df[df["_date"] == day]
    if d_df.empty:
        return None
    m_start, m_end = _month_range(day)
    mon_df = df[(df["_date"] >= m_start) & (df["_date"] <= m_end)]
    a_day, a_mon, a_all = _serv_agg(d_df), _serv_agg(mon_df), _serv_agg(df)
    pct = a_day["pct"]

    details = [
        (f"📅 {day:%d-%b-%Y} · Trucks", _serv_trucks_rows(a_day)),
        (f"❌ {day:%d-%b-%Y} · Material Not Available (shed-wise)", _serv_mat_rows(a_day)),
        (f"🚛 {day:%d-%b-%Y} · Other Reasons", _serv_oth_rows(a_day)),
    ]
    reasons = sum(a_day["mat"].values()) + sum(a_day["oth"].values())
    if abs(reasons - a_day["left"]) > 0.01:
        details.append(("⚠ Check: total of reasons does not match Trucks Left", [
            ("Trucks Left", _sq(a_day["left"])), ("Sum of all reasons", _sq(reasons))]))

    details += [
        (f"🗓 Month {day:%b-%y} · Trucks", _serv_trucks_rows(a_mon)),
        (f"❌ Month {day:%b-%y} · Material Not Available (shed-wise)", _serv_mat_rows(a_mon)),
        (f"🚛 Month {day:%b-%y} · Other Reasons", _serv_oth_rows(a_mon)),
    ]

    # all months (latest pehle)
    months = sorted({(d.year, d.month) for d in df["_date"]}, reverse=True)
    rows_m, rows_mat, rows_oth = [], [], []
    for y, m in months:
        s, e = _month_range(datetime.date(y, m, 1))
        a = _serv_agg(df[(df["_date"] >= s) & (df["_date"] <= e)])
        lbl = f"{s:%b-%y}"
        rows_m.append((lbl, f"{_sq(a['planned'])} planned | {_sq(a['dispatch'])} dispatch | "
                            f"{_sq(a['left'])} left | {a['pct']:.1f}%"))
        mt = " · ".join(f"{SERV_LABELS[k]} {_sq(v)}" for k, v in a["mat"].items() if v > 0)
        ot = " · ".join(f"{k} {_sq(v)}" for k, v in a["oth"].items() if v > 0)
        rows_mat.append((lbl, mt or "—"))
        rows_oth.append((lbl, ot or "—"))
    rows_m.append(("TOTAL (April to date)", f"{_sq(a_all['planned'])} planned | {_sq(a_all['dispatch'])} dispatch | "
                                              f"{_sq(a_all['left'])} left | {a_all['pct']:.1f}%"))
    details += [
        ("📊 All Months · Serviceability", rows_m),
        ("❌ All Months · Material Not Available", rows_mat),
        ("🚛 All Months · Other Reasons", rows_oth),
        (f"📆 Total ({df['_date'].min():%d-%m-%y} to {df['_date'].max():%d-%m-%y}) · Material Not Available",
         _serv_mat_rows(a_all)),
        ("📆 Total · Other Reasons", _serv_oth_rows(a_all)),
    ]

    return {
        "value": f"{pct:.1f}%",
        "desc": f"{_sq(a_day['dispatch'])} of {_sq(a_day['planned'])} trucks dispatched on {day:%d-%b-%Y}",
        "color": BLUE if pct >= 80 else (AMBER if pct >= 60 else RED),
        "metrics": [
            (f"{pct:.1f}%", "Serviceability", "yield"),
            (_sq(a_day["planned"]), "Trucks Planned"),
            (_sq(a_day["dispatch"]), "Dispatched"),
            (_sq(a_day["left"]), "Trucks Left"),
        ],
        "sections": [(f"❌ {day:%d-%m-%y} · Material Not Available", _serv_mat_rows(a_day))],
        "details": details,
    }
# ====================================================================
# FINANCE: DRS & CRS MONTH-WISE  (file: "DRS & CRS.xls" -> Party Name | Group | November | October ... June)
#   DRS = SUNDRY DEBITORS
#   CRS = SUNDRY CREDITORS + SUNDRY CREDITORS FOR EXP
# ====================================================================
DRS_GROUPS = ("SUNDRY DEBITORS", "SUNDRY DEBTORS")
CRS_GROUPS = ("SUNDRY CREDITORS", "SUNDRY CREDITORS FOR EXP", "SUNDRY CREDITORS FOR EXPENSES")


def _drs_crs_month_cols(df):
    """{month_number: column_name} - 'November', 'October ', 'July ' jaise columns se."""
    out = {}
    for c in df.columns:
        if str(c).startswith("_"):
            continue
        try:
            out[datetime.datetime.strptime(str(c).strip()[:3].title(), "%b").month] = c
        except ValueError:
            pass
    return out


def _drs_crs_month_dates(df):
    """Month dropdown ke liye: sheet ke har month ki ek date (current month ke liye aaj ki date)."""
    today = datetime.datetime.now(IST).date()
    fy = today.year if today.month >= 4 else today.year - 1
    out = []
    for m in _drs_crs_month_cols(df):
        y = fy if m >= 4 else fy + 1
        out.append(today if (y, m) == (today.year, today.month) else datetime.date(y, m, 1))
    return sorted(out, reverse=True)


def finance_drs_crs_month_card(day):
    """DRS & CRS - sirf month-wise (card = selected month, View Details = saare months)."""
    df, err, _ = get_sheet("finance_drs_crs_m")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    cols = [c for c in df.columns if not str(c).startswith("_")]
    norm = lambda s: str(s).strip().upper()
    c_grp = next((c for c in cols if norm(c) == "GROUP"), None)
    mcols = _drs_crs_month_cols(df)
    if not c_grp or not mcols:
        return {"value": "Config error", "color": RED,
                "desc": f"Group / month columns not found. Columns: {cols}"}

    grp = df[c_grp].astype(str).str.strip().str.upper()
    is_drs, is_crs = grp.isin(DRS_GROUPS), grp.isin(CRS_GROUPS)

    def month_vals(col):
        v = _num(df[col]).fillna(0.0)
        return (float(v[is_drs].sum()), float(v[is_crs].sum()),
                {g: float(v[grp == g].sum()) for g in (*DRS_GROUPS[:1], *CRS_GROUPS[:2])},
                {g: int((grp == g).sum()) for g in (*DRS_GROUPS[:1], *CRS_GROUPS[:2])})

    cr = lambda x: f"{x / 10000000:,.2f} Cr"
    if day.month not in mcols:
        return None
    drs, crs, by_g, cnt = month_vals(mcols[day.month])
    today = datetime.datetime.now(IST).date()
    till = f" (till {today:%d-%b})" if (day.year, day.month) == (today.year, today.month) else ""

    rows_all = []
    for m in sorted(mcols, key=lambda m: (m - 4) % 12, reverse=True):       # latest month upar (FY: Apr..Mar)
        d_, c_, _g, _c = month_vals(mcols[m])
        y = day.year if (m <= day.month or m < 4) else day.year - 1
        rows_all.append((f"{datetime.date(y, m, 1):%b-%y}", f"DRS {cr(d_)}  |  CRS {cr(c_)}"))

    return {
        "value": f"DRS {cr(drs)} | CRS {cr(crs)}",
        "desc": f"Closing balance · {day:%b-%y}{till}",
        "color": BLUE,
        "metrics": [(cr(drs), "DRS (Debtors)"), (cr(crs), "CRS (Creditors)")],
        "sections": [(f"📌 Exact amount · {day:%b-%y}", [("DRS", _inr(drs)), ("CRS", _inr(crs))])],
        "details": [
            ("📊 All Months · DRS & CRS", rows_all),
            (f"💰 {day:%b-%y} · Group-wise", [
                ("Sundry Debitors (DRS)", f"{_inr(by_g['SUNDRY DEBITORS'])}  ({cnt['SUNDRY DEBITORS']} parties)"),
                ("Sundry Creditors", f"{_inr(by_g['SUNDRY CREDITORS'])}  ({cnt['SUNDRY CREDITORS']} parties)"),
                ("Sundry Creditors For Exp", f"{_inr(by_g['SUNDRY CREDITORS FOR EXP'])}  ({cnt['SUNDRY CREDITORS FOR EXP']} parties)"),
                ("CRS total (Creditors + For Exp)", _inr(crs)),
            ]),
        ],
    }
# ====================================================================
# FINANCE: DRS & CRS MONTH-WISE  (naya format: ACCOUNT NAME | Month | GROUP | Dr/Cr | OPN.AMT | DEBIT AMT | CREDIT AMT | Dr/Cr | BAL.AMT)
#   DRS = GROUP "Sundry Debtors"                       -> BAL.AMT ka sum (Dr = +, Cr = -)
#   CRS = GROUP "Sundry Creditors" + "Sundry Creditors For Expenses" -> BAL.AMT ka sum (Cr = +, Dr = -)
# ====================================================================
def _bal_month_no(txt):
    try:
        return datetime.datetime.strptime(str(txt).strip()[:3].title(), "%b").month
    except ValueError:
        return None


def _bal_month_date(m, today):
    fy = today.year if today.month >= 4 else today.year - 1
    y = fy if m >= 4 else fy + 1
    return today if (y, m) == (today.year, today.month) else datetime.date(y, m, 1)


def _bal_prepare(df):
    cols = [c for c in df.columns if not str(c).startswith("_")]
    norm = lambda s: re.sub(r"[^A-Z]", "", str(s).upper())
    c_mon = next((c for c in cols if norm(c) == "MONTH"), None)
    c_grp = next((c for c in cols if norm(c) == "GROUP"), None)
    c_bal = next((c for c in cols if norm(c) == "BALAMT"), None)
    if not (c_mon and c_grp and c_bal):
        raise DataError(f"Month / GROUP / BAL.AMT column not found. Columns: {cols}")
    c_dc = cols[cols.index(c_bal) - 1] if cols.index(c_bal) > 0 else None     # BAL.AMT se pehle wala Dr/Cr column
    w = pd.DataFrame({
        "m": df[c_mon].map(_bal_month_no),
        "grp": df[c_grp].astype(str).str.strip().str.upper(),
        "bal": _num(df[c_bal]).fillna(0.0),
        "dc": df[c_dc].astype(str).str.strip().str.upper() if c_dc else "DR",
    })
    w = w[w["m"].notna()].copy()
    w["m"] = w["m"].astype(int)
    w["signed"] = w["bal"].where(w["dc"] != "CR", -w["bal"])                   # Dr = +, Cr = -
    return w


def _bal_drs_crs(w, m):
    s = w[w["m"] == m]
    d = s[s["grp"] == "SUNDRY DEBTORS"]
    c1 = s[s["grp"] == "SUNDRY CREDITORS"]
    c2 = s[s["grp"] == "SUNDRY CREDITORS FOR EXPENSES"]
    return {"drs": float(d["signed"].sum()), "crs": float(-(c1["signed"].sum() + c2["signed"].sum())),
            "c1": float(-c1["signed"].sum()), "c2": float(-c2["signed"].sum()),
            "c2_cr": float(c2.loc[c2["dc"] == "CR", "bal"].sum()), "c2_dr": float(c2.loc[c2["dc"] != "CR", "bal"].sum()),
            "n_d": len(d), "n_c1": len(c1), "n_c2": len(c2)}


def _drs_crs_bal_month_dates(df):
    """Month dropdown ke liye: sheet ke har month ki ek date."""
    today = datetime.datetime.now(IST).date()
    w = _bal_prepare(df)
    return sorted({_bal_month_date(m, today) for m in w["m"].unique()}, reverse=True)
def finance_drs_crs_sd_sc_card(day):
    """DRS = Group SD ka Closing Balance sum, CRS = Group SC ka Closing Balance sum (1 April se aaj tak)."""
    df, err, _ = get_sheet("finance_drs_crs_new")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    cols = [c for c in df.columns if not str(c).startswith("_")]
    norm = lambda s: re.sub(r"[^A-Z]", "", str(s).upper())
    c_grp = next((c for c in cols if norm(c) == "GROUP"), None)
    c_bal = next((c for c in cols if norm(c) == "CLOSINGBALANCE"), None)
    if not c_grp or not c_bal:
        return {"value": "Config error", "desc": f"Group / Closing Balance column not found. Columns: {cols}", "color": RED}

    w = pd.DataFrame({
        "grp": df[c_grp].astype(str).str.strip().str.upper(),
        "bal": _num(df[c_bal]).fillna(0.0),
    })
    sd, sc = w[w["grp"] == "SD"], w[w["grp"] == "SC"]
    drs, crs = float(sd["bal"].sum()), float(sc["bal"].sum())
    cr = lambda x: f"{x / 10000000:,.2f} Cr"

    return {
        "value": f"DRS {cr(drs)} | CRS {cr(crs)}",
        "desc": f"Closing Balance · 1 Apr 2026 to {day:%d-%b-%Y}",
        "color": BLUE,
        "metrics": [(cr(drs), "Total DRS (Debtors)"), (cr(crs), "Total CRS (Creditors)")],
        "sections": [("📌 Exact amount", [("Total DRS", _inr(drs)), ("Total CRS", _inr(crs))])],
        "details": [("💰 Group-wise", [
            ("SD (Debtors)", f"{_inr(drs)}  ({len(sd)} parties)"),
            ("SC (Creditors)", f"{_inr(crs)}  ({len(sc)} parties)"),
        ])],
    }
def finance_rec_paid_card(day):
    import html as _html
    esc = lambda x: _html.escape(str(x))
    cr = lambda x: f"{x / 10000000:,.2f} Cr"

    # 1. RECEIVED (.xls - values Lakhs mein hain, Apr se Nov till date)
    df_rec, err_r, _ = get_sheet("finance_received_xls")
    rec_rows = []
    tot_rec_rs = 0.0
    if df_rec is not None:
        r = df_rec.copy()
        r.columns = [str(c).strip() for c in r.columns]
        if "PARTY NAME" in r.columns and "RECEIVED" in r.columns:
            r["party"] = r["PARTY NAME"].astype(str).str.strip()
            r = r[(r["party"] != "") & (r["party"].str.lower() != "nan")]
            r = r[~r["party"].str.upper().str.contains("TOTAL|AS IN SHORTS", regex=True)]
            r["val_lakhs"] = pd.to_numeric(
                r["RECEIVED"].astype(str).str.replace(",", "", regex=False).str.strip(),
                errors="coerce"
            ).fillna(0.0)

            g_rec = r.groupby("party", as_index=False)["val_lakhs"].sum()
            g_rec = g_rec[g_rec["val_lakhs"] > 0].sort_values("val_lakhs", ascending=False)

            tot_rec_lakhs = float(g_rec["val_lakhs"].sum())
            tot_rec_rs = tot_rec_lakhs * 100000.0
            rec_rows = [(esc(row["party"]), f"₹{row['val_lakhs']:,.2f} L ({cr(row['val_lakhs'] * 100000.0)})") for _, row in g_rec.iterrows()]

    # 2. PAID (.xls - values Rupees mein hain, Apr se Nov till date)
    df_paid, err_p, _ = get_sheet("finance_paid_xls")
    paid_rows = []
    tot_paid_rs = 0.0
    if df_paid is not None:
        p = df_paid.copy()
        p.columns = [str(c).strip() for c in p.columns]
        if "Party Name" in p.columns and "Amount" in p.columns:
            p["party"] = p["Party Name"].astype(str).str.strip()
            p = p[(p["party"] != "") & (p["party"].str.lower() != "nan")]
            p = p[~p["party"].str.upper().str.contains("TOTAL", regex=True)]
            p["val_rs"] = pd.to_numeric(
                p["Amount"].astype(str).str.replace(",", "", regex=False).str.strip(),
                errors="coerce"
            ).fillna(0.0)

            g_paid = p.groupby("party", as_index=False)["val_rs"].sum()
            g_paid = g_paid[g_paid["val_rs"] > 0].sort_values("val_rs", ascending=False)

            tot_paid_rs = float(g_paid["val_rs"].sum())
            paid_rows = [(esc(row["party"]), _inr(row["val_rs"])) for _, row in g_paid.iterrows()]

    return {
        # Upar card par sirf dono ka Total Amount dikhega
        "value": f"Rec: {cr(tot_rec_rs)} | Paid: {cr(tot_paid_rs)}",
        "desc": f"Apr to Nov Till Date · {len(rec_rows)} Rec Parties · {len(paid_rows)} Paid Parties",
        "color": BLUE,
        "metrics": [
            (cr(tot_rec_rs), "Total Received"),
            (cr(tot_paid_rs), "Total Paid"),
        ],
        "sections": [
            ("📌 Summary (Apr to Nov Till Date)", [
                ("Total Amount Received", f"{_inr(tot_rec_rs)} ({cr(tot_rec_rs)})"),
                ("Total Amount Paid", f"{_inr(tot_paid_rs)} ({cr(tot_paid_rs)})"),
            ])
        ],
        "details": [
            (f"📥 Party-wise Received ({len(rec_rows)} parties)",
             rec_rows + [("TOTAL RECEIVED", f"{_inr(tot_rec_rs)} ({cr(tot_rec_rs)})")] if rec_rows else [("No data", "-")]),
            (f"📤 Party-wise Paid ({len(paid_rows)} parties)",
             paid_rows + [("TOTAL PAID", f"{_inr(tot_paid_rs)} ({cr(tot_paid_rs)})")] if paid_rows else [("No data", "-")]),
        ],
    }


def finance_drs_crs_bal_card(day):
    df, err, _ = get_sheet("finance_drs_crs_m")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    try:
        w = _bal_prepare(df)
    except DataError as e:
        return {"value": "Config error", "desc": str(e), "color": RED}
    if day.month not in set(w["m"]):
        return None
    cr = lambda x: f"{x / 10000000:,.2f} Cr"
    today = datetime.datetime.now(IST).date()
    r = _bal_drs_crs(w, day.month)
    till = f" (till {today:%d-%b})" if (day.year, day.month) == (today.year, today.month) else ""

    rows_all = []
    for m in sorted(set(w["m"]), key=lambda m: _bal_month_date(m, today), reverse=True):
        a = _bal_drs_crs(w, m)
        rows_all.append((f"{_bal_month_date(m, today):%b-%y}", f"DRS {cr(a['drs'])}  |  CRS {cr(a['crs'])}"))

    return {
        "value": f"DRS {cr(r['drs'])} | CRS {cr(r['crs'])}",
        "desc": f"Balance Amount · {day:%b-%y}{till}",
        "color": BLUE,
        "metrics": [(cr(r["drs"]), "Total DRS (Debtors)"), (cr(r["crs"]), "Total CRS (Creditors)")],
        "sections": [(f"📌 Exact amount · {day:%b-%y}", [("Total DRS", _inr(r["drs"])), ("Total CRS", _inr(r["crs"]))])],
        "details": [
            ("📊 All Months · Total DRS & Total CRS", rows_all),
            (f"💰 {day:%b-%y} · Group-wise", [
                ("Sundry Debtors (DRS)", f"{_inr(r['drs'])}  ({r['n_d']} entries)"),
                ("Sundry Creditors", f"{_inr(r['c1'])}  ({r['n_c1']} entries)"),
                ("Sundry Creditors For Expenses",
                 f"{_inr(r['c2'])}  (Cr {_inr(r['c2_cr'])} - Dr {_inr(r['c2_dr'])})"),
                ("CRS total", _inr(r["crs"])),
            ]),
        ],
    }
# ====================================================================
# FINANCE: RECEIVABLE DAYS  = (pichle month ka DRS) / (pichle month ki Sale) x 30
#   DRS  -> "DRS & CRS" sheet (finance_drs_crs_m), Sundry Debtors, pichle month ka BAL.AMT
#   Sale -> "DAILY BASIS SALES" sheet (daily_sales_report), pichle month ka TOTAL SALE AMOUNT ka sum
# ====================================================================
def _recv_prev(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def _recv_sale_by_month(sdf):
    """{(year, month): (sale_sum, din_count)} daily sales sheet se."""
    amt_col = next((c for c in sdf.columns if "TOTAL SALE" in str(c).upper()), None)
    if amt_col is None:
        raise DataError("TOTAL SALE AMOUNT column not found")
    t = pd.DataFrame({"d": sdf["_date"], "a": _num(sdf[amt_col]).fillna(0.0)})
    t = t[t["d"].notna()]
    t["ym"] = t["d"].map(lambda x: (x.year, x.month))
    g = t.groupby("ym").agg(sale=("a", "sum"), days=("d", "nunique"))
    return {k: (float(r["sale"]), int(r["days"])) for k, r in g.iterrows()}


def _recv_days_month_dates(df):
    """Month dropdown: sirf wo months jinke pichle month ka DRS + Sale dono sheet mein hain (aaj tak)."""
    today = datetime.datetime.now(IST).date()
    w = _bal_prepare(df)
    sdf, err, _ = get_sheet("daily_sales_report")
    if sdf is None:
        return [today]
    sales = _recv_sale_by_month(sdf)
    drs_months = set(w["m"])
    out = []
    for (y, m) in sales:                      # sale wale har month ka NEXT month selectable hai
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        if m in drs_months and (ny, nm) <= (today.year, today.month):
            out.append(today if (ny, nm) == (today.year, today.month) else datetime.date(ny, nm, 1))
    return sorted(set(out), reverse=True) or [today]


def finance_recv_days_card(day):
    df, err, _ = get_sheet("finance_drs_crs_m")
    sdf, err2, _ = get_sheet("daily_sales_report")
    if df is None:
        return {"value": "Error", "desc": f"DRS data error: {err}", "color": RED}
    if sdf is None:
        return {"value": "Error", "desc": f"Sales data error: {err2}", "color": RED}
    try:
        w = _bal_prepare(df)
        sales = _recv_sale_by_month(sdf)
    except DataError as e:
        return {"value": "Config error", "desc": str(e), "color": RED}

    py, pm = _recv_prev(day.year, day.month)
    prev = datetime.date(py, pm, 1)
    if pm not in set(w["m"]):
        return {"value": "No Data", "desc": f"{prev:%b-%y} is not in the DRS sheet", "color": GREY}
    if (py, pm) not in sales or sales[(py, pm)][0] <= 0:
        return {"value": "No Data", "desc": f"{prev:%b-%y} is not in the Sale sheet", "color": GREY}

    drs = _bal_drs_crs(w, pm)["drs"]
    sale, ndays = sales[(py, pm)]
    days = drs / sale * 30
    cr = lambda x: f"{x / 10000000:,.2f} Cr"
    full = calendar.monthrange(py, pm)[1]
    warn = [] if ndays >= full else [("⚠️ Note", f"Sale sirf {ndays}/{full} days - result incomplete")]

    return {
        "value": f"{days:,.2f}",
        "desc": "",
        "color": BLUE,
    }
# ====================================================================
# MAINTENANCE: CURRENT BREAKDOWN (month-wise, reason ke saath) + PREVENTIVE MAINTENANCE %
# ====================================================================
def _mcol(df, *keys):
    """Column naam dhoondho (extra space / newline se farak nahi padta)."""
    for c in df.columns:
        n = re.sub(r"\s+", " ", str(c)).strip().upper()
        if any(k in n for k in keys):
            return c
    return None


def maint_breakdown_card(df, day):
    c_m = _mcol(df, "MACHINE NAME")
    c_i = _mcol(df, "ISSUE DESCRIPTION")
    c_r = _mcol(df, "ISSUE RESOLVED")
    if not (c_m and c_i and c_r):
        return {"value": "Config error", "desc": f"Machine Name / Issue Description / Issue Resolved column not found. Columns: {list(df.columns)}", "color": RED}

    today = datetime.datetime.now(IST).date()
    w = df[df["_date"].notna()].copy()
    w["machine"] = w[c_m].astype(str).str.strip().replace({"nan": "", "None": ""})
    w = w[w["machine"] != ""]
    w["issue"] = w[c_i].astype(str).str.strip().replace({"nan": "", "None": ""})
    w["pending"] = w[c_r].astype(str).str.strip().str.upper() != "TRUE"
    w["ym"] = w["_date"].map(lambda x: (x.year, x.month))
    w["ago"] = w["_date"].map(lambda x: (today - x).days)
    w = w.sort_values("_date", ascending=False)

    def line(r):
        if r["pending"]:
            return (f"⚙ {r['machine']}", f"❌ {r['issue'] or 'No reason mentioned'} · {r['_date']:%d-%b} ({r['ago']}d ago)")
        return (f"⚙ {r['machine']}", f"✅ {r['issue'] or 'No reason mentioned'} · {r['_date']:%d-%b} (Solved)")

    sel = (day.year, day.month)
    allp = w[w["pending"]]
    sel_all = w[w["ym"] == sel]                  # Selected month ke SAARE breakdowns (e.g., 24)
    sel_p = sel_all[sel_all["pending"]]          # Selected month ke NOT SOLVED (e.g., 8)
    sel_solved = len(sel_all) - len(sel_p)       # Selected month ke SOLVED (e.g., 16)

    # ---- Details (View Full Details ke andar Month-wise summary + list) ----
    details = []
    mrows = []
    for ym, f in sorted(w.groupby("ym"), key=lambda x: x[0], reverse=True):
        mrows.append((f"{datetime.date(ym[0], ym[1], 1):%b-%y}", f"{len(f)} breakdowns | {int(f['pending'].sum())} not solved"))
    mrows.append(("TOTAL", f"{len(w)} breakdowns | {len(allp)} not solved"))
    details.append(("📊 Month-wise · Breakdowns | Not solved", mrows))

    if not sel_all.empty:
        mach = []
        for name, f in sel_all.groupby("machine"):
            mach.append((len(f), int(f["pending"].sum()), name))
        mach.sort(key=lambda x: (-x[0], -x[1], x[2]))
        details.append((f"🏭 {day:%b-%y} · Machine-wise ({len(sel_all)} breakdowns)",
                        [(n, f"{tot} total · {pen} pending") for tot, pen, n in mach]))

    for ym, f in sorted(w.groupby("ym"), key=lambda x: x[0], reverse=True):
        details.append((f"📅 {datetime.date(ym[0], ym[1], 1):%b-%y} · All breakdowns ({len(f)})", [line(r) for _, r in f.iterrows()]))

    return {
        "value": f"{len(allp)} Machines",
        "desc": f"Overall pending: {len(allp)} · {day:%b-%y} Not solved ({len(sel_p)} of {len(sel_all)} breakdowns)",
        "color": RED if len(allp) else BLUE,
        "sections": [(f"🔴 {day:%b-%y} · Machines under breakdown & reason ({len(sel_p)})", [line(r) for _, r in sel_p.iterrows()])] if len(sel_p) else [],
        "details": details,
    }


_PM_MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
              "OCTOBER", "NOVEMBER", "DECEMBER"]


def _pm_parse(df):
    """Preventive sheet (raw, header nahi) -> rows: month(1-12), section, machine, done(bool).
    Machine row = col A mein month ka naam + col B mein machine naam; day columns (1..30) mein TRUE = PM ho gaya."""
    out, section = [], ""
    for _, r in df.iterrows():
        a = str(r.iloc[0]).strip().upper() if pd.notna(r.iloc[0]) else ""
        b = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""
        if a in _PM_MONTHS:
            if b:
                days = [str(x).strip().upper() for x in r.iloc[2:32]]
                out.append({"m": _PM_MONTHS.index(a) + 1, "section": section, "machine": b, "done": "TRUE" in days})
        elif a and not b and (len(r) < 3 or pd.isna(r.iloc[2])):
            section = a.title()                     # "CURING SECTION" jaise section heading
    return pd.DataFrame(out, columns=["m", "section", "machine", "done"])


def _pm_month_dates(df):
    today = datetime.datetime.now(IST).date()
    p = _pm_parse(df)
    return sorted({_bal_month_date(int(m), today) for m in p["m"].unique()}, reverse=True)


def maint_pm_card(df, day):
    p = _pm_parse(df)
    cur = p[p["m"] == day.month]
    if cur.empty:
        return {"value": "No Data", "desc": f"{day:%b-%y} is not in the preventive schedule sheet", "color": GREY}
    total, done = len(cur), int(cur["done"].sum())
    pct = done / total * 100
    pend = cur[~cur["done"]]

    def mname(m):
        return datetime.date(2000, int(m), 1).strftime("%b")

    mrows = []
    for m in sorted(p["m"].unique(), key=lambda m: (m < 4, m), reverse=True):    # saal April se shuru
        f = p[p["m"] == m]
        mrows.append((mname(m), f"{f['done'].mean() * 100:.1f}%  ({int(f['done'].sum())}/{len(f)} machines)"))

    sec_done = [(s or "-", f"{int(f['done'].sum())}/{len(f)} machines done") for s, f in cur.groupby("section", sort=False)]
    return {
        "value": f"{pct:.1f} %",
        "desc": f"{done} / {total} machines PM done · {day:%b-%y}",
        "color": BLUE if pct >= 90 else (AMBER if pct >= 70 else RED),
        "sections": [(f"⏳ PM pending ({len(pend)} machines)", [(r["machine"].title(), r["section"]) for _, r in pend.iterrows()])] if len(pend) else [],
        "details": [
            ("📊 Month-wise PM %", mrows),
            (f"🏭 {day:%b-%y} · Section-wise (PM done)", sec_done),
            (f"✅ {day:%b-%y} · PM completed machines ({done})", [(r["machine"].title(), r["section"]) for _, r in cur[cur["done"]].iterrows()]),
        ],
    }
def _bd_start_end(df):
    """Har row ka breakdown start / end datetime aur downtime (hours)."""
    c_t = _mcol(df, "BREAKDOWN TIME")
    c_rd = _mcol(df, "RESOLUTION DATE")
    c_r = _mcol(df, "ISSUE RESOLVED")
    w = df[df["_date"].notna()].copy()

    # Breakdown time (hh:mm:ss ya 2:30 PM dono chalenge)
    txt = w[c_t].astype(str).str.strip() if c_t else pd.Series("", index=w.index)
    t = pd.to_timedelta(txt, errors="coerce")
    bad = t.isna()
    if bad.any():
        alt = pd.to_datetime(txt[bad], errors="coerce")
        t[bad] = pd.to_timedelta(alt.dt.hour.fillna(0) * 3600 + alt.dt.minute.fillna(0) * 60, unit="s")
    t = t.fillna(pd.Timedelta(0))
    w["start"] = pd.to_datetime(w["_date"]) + t

    # Resolution datetime
    if c_rd:
        try:
            w["end"] = pd.to_datetime(w[c_rd], dayfirst=True, errors="coerce", format="mixed")
        except Exception:
            w["end"] = pd.to_datetime(w[c_rd], dayfirst=True, errors="coerce")
    else:
        w["end"] = pd.NaT

    solved = w[c_r].astype(str).str.strip().str.upper().eq("TRUE") if c_r else False
    now = datetime.datetime.now(IST).replace(tzinfo=None)
    w["open"] = ~solved
    w.loc[w["open"], "end"] = now                      # pending issue: abhi tak ka downtime
    w["hrs"] = ((w["end"] - w["start"]).dt.total_seconds() / 3600).clip(lower=0)
    w["no_end"] = w["hrs"].isna()                      # solved hai par resolution time nahi bhara
    w["hrs"] = w["hrs"].fillna(0.0)
    return w


def maint_downtime_card(df, day):
    c_m = _mcol(df, "MACHINE NAME")
    c_i = _mcol(df, "ISSUE DESCRIPTION")
    if not c_m:
        return {"value": "Config error", "desc": f"Machine Name column not found: {list(df.columns)}", "color": RED}

    w = _bd_start_end(df)
    w["machine"] = w[c_m].astype(str).str.strip()
    w = w[~w["machine"].isin(["", "nan", "None"])]

    fy_start = datetime.date(day.year if day.month >= 4 else day.year - 1, 4, 1)   # saal April se
    m_start, m_end = _month_range(day)
    mon = w[(w["_date"] >= m_start) & (w["_date"] <= m_end)]
    ytd = w[(w["_date"] >= fy_start) & (w["_date"] <= day)]
    d_day = w[w["_date"] == day]

    h = lambda x: f"{x:,.1f} Hrs"
    missing = int(ytd["no_end"].sum())

    # machine-wise (selected month) - sabse zyada downtime upar
    mw = (mon.groupby("machine")["hrs"].agg(["sum", "count"]).sort_values("sum", ascending=False))
    mrows = [(m, f"{r['sum']:,.1f} Hrs · {int(r['count'])} breakdowns") for m, r in mw.iterrows()]

    # month-wise (saal ka)
    ymw = ytd.assign(ym=ytd["_date"].map(lambda x: (x.year, x.month))).groupby("ym")["hrs"].agg(["sum", "count"])
    yrows = [(f"{datetime.date(y, m, 1):%b-%y}", f"{r['sum']:,.1f} Hrs · {int(r['count'])} breakdowns")
             for (y, m), r in ymw.sort_index(ascending=False).iterrows()]
    yrows.append(("TOTAL (YTD)", f"{ytd['hrs'].sum():,.1f} Hrs"))

    details = [
        (f"🏭 {day:%b-%y} · Machine-wise downtime ({len(mrows)} machines)", mrows or [("No breakdown", "✅")]),
        (f"📊 Month-wise (Apr-{fy_start.year % 100} se {day:%b-%y})", yrows),
    ]
    if missing:
        details.append(("⚠ Check", [(f"{missing} solved breakdowns", "Resolution date/time missing; their downtime counted as 0")]))

    return {
        "value": h(mon["hrs"].sum()),
        "desc": f"Total downtime · {day:%b-%y} · {len(mon)} breakdowns",
        "color": RED if mon["hrs"].sum() > 0 else BLUE,
        "metrics": [
            (f"{d_day['hrs'].sum():,.1f}", f"Hrs {day:%d-%m}"),
            (f"{mon['hrs'].sum():,.1f}", f"Hrs {day:%b-%y}"),
            (f"{ytd['hrs'].sum():,.1f}", "Hrs YTD"),
        ],
        "details": details,
    }
# ====================================================================
# OTHERS: CUSTOMER COMPLAINTS
# ====================================================================
def _cmp_date(s):
    s = re.sub(r"\s+", "", str(s))
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", s)
    if not m:
        return None
    d, mo, y = int(m[1]), int(m[2]), int(m[3])
    if y < 100:
        y += 2000
    try:
        return datetime.date(y, mo, d)
    except ValueError:
        return None


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_complaints_cached(url, gid):
    base = url.split("/pub")[0]
    data = _http_get(f"{base}/pub?output=csv&gid={gid}")
    if data.lstrip()[:1] == b"<":
        raise PermissionError("Complaint sheet is not published. File > Share > Publish to web and check the gid.")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
    hdr = next((i for i, r in enumerate(rows)
                if any(c.strip().upper() == "DATE" for c in r) and any("COMPLAINT" in c.upper() for c in r)), None)
    if hdr is None:
        raise DataError("'DATE' and 'COMPLAINT' header row not found in Complaint sheet.")
    df = _frame_from_rows(rows[hdr:])
    df.columns = [re.sub(r"\s+", " ", str(c)).strip().upper() for c in df.columns]
    df["_date"] = df["DATE"].map(_cmp_date)
    df = df[df["_date"].notna()].copy()
    if df.empty:
        raise DataError("No valid date found in Complaint sheet.")
    return df, datetime.datetime.now(IST)


CMP_ISSUES = [
    ("Taper", ("TAPER",)),
    ("Tearing", ("TEAR",)),
    ("Stamping / Marking", ("STAMP", "MARKING")),
    ("Size / Thickness", ("SIZE", "THICK")),
    ("Packing", ("PACK",)),
    ("Side not clean", ("SIDE NOT",)),
    ("Colour / Hardness / Soft", ("COLOUR", "COLOR", "HARD", "SOFT")),
    ("Yellowness", ("YELLOW",)),
    ("Wave cutting", ("WAVE",)),
    ("Damage", ("DAMAGE",)),
    ("Weight", ("WEIGHT",)),
]


def _cmp_issue_labels(text):
    t = str(text).upper()
    out = [name for name, keys in CMP_ISSUES if any(k in t for k in keys)]
    return out or ["Other"]


def _cmp_grade(p):
    s = str(p).strip().upper()
    s = re.sub(r"(\d)(?=[A-Z])", r"\1 ", s)
    s = re.sub(r"\s*\+", "+", s)
    return re.sub(r"\s+", " ", s)


def complaints_card(df, day):
    import html as _html
    esc = lambda x: _html.escape(str(x))
    need = ["PRODUCT NAME", "CUSTOMER", "COMPLAINT", "PREVENTIVE ACTION"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        return {"value": "Config error", "desc": f"Columns not found: {miss}. Found: {list(df.columns)}", "color": RED}

    w = df[(df["_date"] <= day)].copy()
    w["comp"] = w["COMPLAINT"].astype(str).str.strip()
    w = w[w["comp"] != ""]
    if w.empty:
        return {"value": "0 Complaints", "desc": "No complaints up to this date", "color": BLUE}

    w["action"] = w["PREVENTIVE ACTION"].astype(str).str.strip()
    w["done"] = w["action"] != ""
    w["grade"] = w["PRODUCT NAME"].map(_cmp_grade)
    w["cust"] = w["CUSTOMER"].astype(str).str.strip().str.title()
    w = w.sort_values("_date", ascending=False)

    total, done = len(w), int(w["done"].sum())
    pending = total - done
    first, last = w["_date"].min(), w["_date"].max()

    # issue-wise count (ek complaint mein 2 issue ho to dono ginte hain)
    issue_cnt = {}
    for t in w["comp"]:
        for lab in _cmp_issue_labels(t):
            issue_cnt[lab] = issue_cnt.get(lab, 0) + 1
    issues = sorted(issue_cnt.items(), key=lambda x: -x[1])

    g = w[w["grade"] != ""]["grade"].value_counts()
    c = w[~w["cust"].str.lower().isin(["", "nan", "none"])]["cust"].value_counts()
    top = lambda s, n=3: " , ".join(f"{k} ({v})" for k, v in s.head(n).items()) or "-"
    top_issues = " , ".join(f"{k} ({v})" for k, v in issues[:3])

    # month-wise
    w["ym"] = w["_date"].map(lambda d: (d.year, d.month))
    mrows = [(f"{datetime.date(y, m, 1):%b-%y}", f"{len(f)} complaints | {int(f['done'].sum())} action taken | {len(f) - int(f['done'].sum())} pending")
             for (y, m), f in sorted(w.groupby("ym"), key=lambda x: x[0], reverse=True)]
    mrows.append(("TOTAL", f"{total} complaints | {done} action taken | {pending} pending"))

    full = [(f"{r['_date']:%d-%m-%y} · {esc(r['grade'])} · {esc(r['cust'] or '-')}",
             f"❌ {esc(r['comp'])}<br>{'✅ ' + esc(r['action']) if r['done'] else '⏳ Action pending'}")
            for _, r in w.iterrows()]

    return {
        "value": f"{total} Complaints",
        "desc": f"{first:%d-%b-%y} to {day:%d-%b-%y} (last complaint {last:%d-%b-%y})",
        "color": RED if pending else BLUE,
        "metrics": [
            (f"{total}", "Total Complaints"),
            (f"{done}", "Action Taken"),
            (f"{pending}", "Action Pending"),
        ],
        "sections": [("📌 Key Highlights", [
            ("Top Issue", top_issues),
            ("Top Grades", top(g)),
            ("Top Customers / Locations", top(c)),
        ])],
        "details": [
            ("📊 Month-wise", mrows),
            ("🧩 Issue-wise", [(k, f"{v} complaints") for k, v in issues]),
            ("🏷 Grade-wise", [(esc(k), f"{v} complaints") for k, v in g.items()]),
            ("📍 Customer-wise", [(esc(k), f"{v} complaints") for k, v in c.items()]),
            (f"📋 All Complaints ({total})", full),
        ],
    }
# ====================================================================
# FINANCE: TOTAL DUE (month-wise)
#   File columns: PARTY NAME | Month | DUE DYS | TOTAL O/S | UNDUE AMT | DUE AMT | OVERDUE AMT
#   Due % = Total Due Amt (us month ka) / Total O/S (us month ka) * 100
# ====================================================================
def _due_prepare(df):
    cols = [c for c in df.columns if not str(c).startswith("_")]
    norm = lambda s: re.sub(r"[^A-Z/]", "", str(s).upper())
    pick = lambda *k: next((c for c in cols if norm(c) in k), None)
    c_p, c_m = pick("PARTYNAME", "PARTY", "ACCOUNTNAME"), pick("MONTH")
    c_d, c_os = pick("DUEDYS", "DUEDAYS"), pick("TOTALO/S", "TOTALOS")
    c_due, c_ov = pick("DUEAMT"), pick("OVERDUEAMT")
    if not all([c_p, c_m, c_os, c_due, c_ov]):
        raise DataError(f"PARTY NAME / Month / TOTAL O/S / DUE AMT / OVERDUE AMT column not found. Columns: {cols}")
    w = pd.DataFrame({
        "party": df[c_p].astype(str).str.strip(),
        "m": df[c_m].map(_bal_month_no),
        "days": _num(df[c_d]).fillna(0.0) if c_d else 0.0,
        "os": _num(df[c_os]).fillna(0.0),
        "due": _num(df[c_due]).fillna(0.0),
        "ov": _num(df[c_ov]).fillna(0.0),
    })
    w = w[w["m"].notna() & (w["party"] != "")].copy()
    w["m"] = w["m"].astype(int)
    return w


def _due_month_dates(df):
    today = datetime.datetime.now(IST).date()
    return sorted({_bal_month_date(m, today) for m in _due_prepare(df)["m"].unique()}, reverse=True)


def finance_total_due_month_card(day):
    import html as _html
    df, err, _ = get_sheet("finance_due_m")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    try:
        w = _due_prepare(df)
    except DataError as e:
        return {"value": "Config error", "desc": str(e), "color": RED}
    if day.month not in set(w["m"]):
        return None
    today = datetime.datetime.now(IST).date()
    cr = lambda x: f"{x / 10000000:,.2f} Cr"
    pct = lambda a, b: (a / b * 100) if b else 0.0

    def tot(m):
        s = w[w["m"] == m]
        return float(s["os"].sum()), float(s["due"].sum()), float(s["ov"].sum()), len(s)

    t_os, t_due, t_ov, n = tot(day.month)
    due_pct = pct(t_due + t_ov, t_os)

    rows_all = []
    for m in sorted(set(w["m"]), key=lambda m: _bal_month_date(m, today), reverse=True):
        o, d, v, _n = tot(m)
        rows_all.append((f"{_bal_month_date(m, today):%b-%y}",
                         f"O/S {cr(o)} | Due {cr(d)} | Overdue {cr(v)} | Due + Overdue % {pct(d + v, o):.2f}%"))

    s = w[(w["m"] == day.month)].groupby("party", as_index=False).agg(
        days=("days", "max"), os=("os", "sum"), due=("due", "sum"), ov=("ov", "sum"))
    s = s[(s["due"] + s["ov"]) > 0.005].sort_values(["ov", "due"], ascending=False)
    esc = lambda x: _html.escape(str(x))
    prow = [(esc(r.party), f"Due Days: {int(r.days)} | O/S: {_inr(r.os)} | Due: {_inr(r.due)} | Overdue: {_inr(r.ov)}")
            for r in s.itertuples()]

    return {
        "value": f"{due_pct:.2f}%",
        "desc": f"Due + Overdue % · {day:%b-%y}" + (f" (till {today:%d-%b})" if (day.year, day.month) == (today.year, today.month) else ""),
        "color": BLUE,
        "metrics": [(f"{due_pct:.2f}%", "Due + Overdue %", "yield"), (cr(t_os), "Total O/S"),
                    (cr(t_due), "Total Due Amt"), (cr(t_ov), "Total Overdue Amt")],
        "sections": [(f"📌 Exact amount · {day:%b-%y}", [
            ("Total O/S", _inr(t_os)), ("Total Due Amount", _inr(t_due)), ("Total Overdue Amount", _inr(t_ov)),
            ("Due + Overdue % ((Due + Overdue) ÷ O/S × 100)", f"{due_pct:.2f}%")])],
        "details": [
            ("📊 All Months · Month-wise", rows_all),
            (f"👥 Party-wise · {day:%b-%y} ({len(prow)} parties)",
             prow + [("TOTAL (Due + Overdue parties)",
                      f"O/S: {_inr(float(s['os'].sum()))} | Due: {_inr(float(s['due'].sum()))} | Overdue: {_inr(float(s['ov'].sum()))}")]
             if prow else [("No party", "✅")]),
        ],
    }
# ====================================================================
# FINANCE: GREATER THAN 90 / 180 DAYS (month-wise)
#   File columns: Party Name | Month | Total Amount | 0-30 | 31-60 | 61-90 | 91-120 Days | 120-180 Days | >180 Days
#   Sirf 2 column ka sum: "91-120 Days" aur "120-180 Days" (month-wise, party-wise)
# ====================================================================
def _gtm_prepare(df):
    cols = [c for c in df.columns if not str(c).startswith("_")]
    norm = lambda s: re.sub(r"[^A-Z0-9->]", "", str(s).upper())
    pick = lambda *k: next((c for c in cols if norm(c) in k), None)
    
    c_p = pick("PARTYNAME", "PARTY", "ACCOUNTNAME")
    c_m = pick("MONTH")
    c_a = pick("61-120DAYS", "61-120", "91-120DAYS", "91-120")
    c_b = pick(">120DAYS", ">120", "120-180DAYS", "121-180DAYS", "120-180", "121-180")
    
    if not all([c_p, c_a, c_b]):
        raise DataError(f"Party Name / 61-120 Days / >120 Days column not found. Columns: {cols}")
        
    w = pd.DataFrame({
        "party": df[c_p].astype(str).str.strip(),
        "m": df[c_m].map(_bal_month_no) if c_m else datetime.datetime.now(IST).month,
        "a": _num(df[c_a]).fillna(0.0),
        "b": _num(df[c_b]).fillna(0.0),
    })
    w = w[w["m"].notna() & (w["party"] != "")].copy()
    w["m"] = w["m"].astype(int)
    return w


def _gtm_month_dates(df):
    # Naye sheet mein Month column nahi hai, sheet = current month ka data
    return [datetime.datetime.now(IST).date()]
def _drs_total_sd():
    """DRS = DRS CRS file mein Group SD ka Closing Balance sum."""
    d, e, _ = get_sheet("finance_drs_crs_new")
    if d is None:
        return 0.0
    norm = lambda s: re.sub(r"[^A-Z]", "", str(s).upper())
    g = next((c for c in d.columns if norm(c) == "GROUP"), None)
    b = next((c for c in d.columns if norm(c) == "CLOSINGBALANCE"), None)
    if not g or not b:
        return 0.0
    m = d[g].astype(str).str.strip().str.upper() == "SD"
    return float(_num(d[b])[m].sum())
RECEIVED_UNIT = 100000      # Received file ke amount LAKH mein hain. Agar file rupees mein ho to 1 kar do.


def finance_recv_paid_card(day):
    import html as _html
    esc = lambda x: _html.escape(str(x))
    rdf, e1, _ = get_sheet("received_new")
    pdf, e2, _ = get_sheet("paid_data")
    if rdf is None:
        return {"value": "Error", "desc": f"Received data error: {e1}", "color": RED}
    if pdf is None:
        return {"value": "Error", "desc": f"Paid data error: {e2}", "color": RED}

    norm = lambda s: re.sub(r"[^A-Z]", "", str(s).upper())
    pick = lambda d, key: next((c for c in d.columns if not str(c).startswith("_") and norm(c) == key), None)
    r_p, r_a = pick(rdf, "PARTYNAME"), pick(rdf, "RECEIVED")
    p_c, p_p, p_a = pick(pdf, "PAYMENTCATEGORY"), pick(pdf, "PARTYNAME"), pick(pdf, "AMOUNT")
    if not (r_p and r_a):
        return {"value": "Config error", "desc": f"PARTY NAME / RECEIVED not found in Received file. Columns: {list(rdf.columns)}", "color": RED}
    if not (p_c and p_p and p_a):
        return {"value": "Config error", "desc": f"Payment Category / Party Name / Amount not found in Paid file. Columns: {list(pdf.columns)}", "color": RED}

    # ---- RECEIVED: party-wise (8 blocks ek party ke jod diye jate hain) ----
    r = pd.DataFrame({"party": rdf[r_p].astype(str).str.strip(),
                      "amt": _num(rdf[r_a]).fillna(0.0) * RECEIVED_UNIT})
    r = r[(r["party"] != "") & (r["party"].str.lower() != "nan")]
    r_by = r.groupby("party")["amt"].sum().sort_values(ascending=False)
    r_by = r_by[r_by > 0]
    rec = float(r_by.sum())

    # ---- PAID: category-wise aur party-wise ----
    p = pd.DataFrame({"cat": pdf[p_c].astype(str).str.strip(),
                      "party": pdf[p_p].astype(str).str.strip(),
                      "amt": _num(pdf[p_a]).fillna(0.0)})
    p = p[(p["party"] != "") & (p["party"].str.lower() != "nan")]
    p["cat"] = p["cat"].replace({"": "Uncategorised", "nan": "Uncategorised"})
    paid = float(p["amt"].sum())
    p_cat = p.groupby("cat")["amt"].sum().sort_values(ascending=False)
    p_by = p.groupby("party")["amt"].sum().sort_values(ascending=False)

    cr = lambda x: f"{x / 10000000:,.2f} Cr"
    net = rec - paid

    return {
        "value": f"Recd {cr(rec)} | Paid {cr(paid)}",
        "desc": f"1 Apr 2026 to {day:%d-%b-%Y} (till date)",
        "color": BLUE,
        "metrics": [(cr(rec), "Total Received"), (cr(paid), "Total Paid")],
        "sections": [("📌 Exact amount", [
            ("Total Received", _inr(rec)),
            ("Total Paid", _inr(paid)),
            ("Net (Received - Paid)", _inr(net)),
        ])],
        "details": [
            (f"💰 Received · Party-wise ({len(r_by)} parties)",
             [(esc(k), _inr(v)) for k, v in r_by.items()] + [("TOTAL RECEIVED", _inr(rec))]),
            (f"📂 Paid · Category-wise ({len(p_cat)} categories)",
             [(esc(k), _inr(v)) for k, v in p_cat.items()] + [("TOTAL PAID", _inr(paid))]),
            (f"💸 Paid · Party-wise ({len(p_by)} parties)",
             [(esc(k), _inr(v)) for k, v in p_by.items()] + [("TOTAL PAID", _inr(paid))]),
        ],
    }
RP_FY_START = datetime.date(2026, 4, 1)
# ====================================================================
# FINANCE: TOTAL AMT RECEIVED / PAID  (MONTH-WISE)
# ====================================================================
_RP_MON = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def _rp_mno(x):
    s = str(x).strip().upper()
    if s.isdigit() and 1 <= int(s) <= 12:
        return int(s)
    return _RP_MON.get(s[:3])


def _rp_fy_order(m):
    return (m - 4) % 12          # Apr=0 ... Mar=11


def _rp_prep(rdf, pdf):
    """Received aur Paid dono ko month number ke saath saaf karke (r, p) dataframe deta hai."""
    norm = lambda s: re.sub(r"[^A-Z]", "", str(s).upper())
    pick = lambda d, keys: next((c for c in d.columns if not str(c).startswith("_") and norm(c) in keys), None)

    r_p, r_m, r_a = pick(rdf, ("PARTYNAME",)), pick(rdf, ("MONTH",)), pick(rdf, ("RECEIVED", "TOTAL"))
    if not (r_p and r_m and r_a):
        raise DataError(f"Received sheet mein PARTY NAME / Month / RECEIVED (or Total) column not found in Received sheet. Columns: {list(rdf.columns)}")
    p_p, p_m, p_a = pick(pdf, ("PARTYNAME",)), pick(pdf, ("MONTH",)), pick(pdf, ("AMOUNT",))
    p_c = pick(pdf, ("PAYMENTCATEGORY", "CATEGORY"))
    if not (p_p and p_m and p_a):
        raise DataError(f"Party Name / Month / Amount column not found in Paid sheet. Columns: {list(pdf.columns)}")

    r = pd.DataFrame({"m": rdf[r_m].map(_rp_mno),
                      "party": rdf[r_p].astype(str).str.strip(),
                      "amt": _num(rdf[r_a]).fillna(0.0) * RECEIVED_UNIT})
    r = r[r["m"].notna()].copy()
    r["m"] = r["m"].astype(int)
    # har month ke block mein 'TOTAL' / 'AS IN SHORTS' row ke baad ka kachra (purana ledger) hata do
    stop = r["party"].str.upper().str.replace(r"\s+", " ", regex=True).str.match(r"^(GRAND )?TOTAL$|^AS IN SHORTS$")
    r = r[~stop.groupby(r["m"]).cummax()]
    r = r[(r["party"] != "") & (r["party"].str.lower() != "nan")]

    p = pd.DataFrame({"m": pdf[p_m].map(_rp_mno),
                      "party": pdf[p_p].astype(str).str.strip(),
                      "cat": pdf[p_c].astype(str).str.strip() if p_c else pdf[p_p].astype(str).str.strip(),
                      "amt": _num(pdf[p_a]).fillna(0.0)})
    p = p[p["m"].notna()].copy()
    p["m"] = p["m"].astype(int)
    p = p[(p["party"] != "") & (p["party"].str.lower() != "nan")]
    p["cat"] = p["cat"].replace({"": "Uncategorised", "nan": "Uncategorised"})
    return r, p, bool(p_c)


def _rp_month_dates(df):
    """Month dropdown ke liye: received + paid sheet ke har month ki ek date (current month = aaj)."""
    today = datetime.datetime.now(IST).date()
    months = set()
    for d in (df, get_sheet("paid_data")[0]):
        if d is None:
            continue
        c = next((c for c in d.columns if re.sub(r"[^A-Z]", "", str(c).upper()) == "MONTH"), None)
        if c:
            months |= {m for m in d[c].map(_rp_mno).dropna().astype(int)}
    return sorted({_bal_month_date(m, today) for m in months}, reverse=True)


def finance_recv_paid_month_card(day):
    import html as _html
    esc = lambda x: _html.escape(str(x))
    rdf, e1, _ = get_sheet("received_data")
    pdf, e2, _ = get_sheet("paid_data")
    if rdf is None:
        return {"value": "Error", "desc": f"Received data error: {e1}", "color": RED}
    if pdf is None:
        return {"value": "Error", "desc": f"Paid data error: {e2}", "color": RED}
    try:
        r, p, has_cat = _rp_prep(rdf, pdf)
    except DataError as e:
        return {"value": "Config error", "desc": str(e), "color": RED}

    cr = lambda x: f"{x / 10000000:,.2f} Cr"
    sel = day.month
    today = datetime.datetime.now(IST).date()
    lab = f"{datetime.date(day.year, sel, 1):%b-%y}"
    live = (day.year, day.month) == (today.year, today.month)

    r_m, p_m = r[r["m"] == sel], p[p["m"] == sel]
    if r_m.empty and p_m.empty:
        return None
    rec_m, paid_m = float(r_m["amt"].sum()), float(p_m["amt"].sum())

    # 1 April se selected month tak (cumulative)
    upto = _rp_fy_order(sel)
    r_y = r[r["m"].map(_rp_fy_order) <= upto]
    p_y = p[p["m"].map(_rp_fy_order) <= upto]
    rec_y, paid_y = float(r_y["amt"].sum()), float(p_y["amt"].sum())

    # month-wise table
    all_m = sorted(set(r["m"]) | set(p["m"]), key=_rp_fy_order)
    all_m = [m for m in all_m if _rp_fy_order(m) <= upto]
    fy_year = day.year if sel >= 4 else day.year - 1
    mrows = []
    for m in reversed(all_m):
        a = float(r.loc[r["m"] == m, "amt"].sum())
        b = float(p.loc[p["m"] == m, "amt"].sum())
        yy = fy_year if m >= 4 else fy_year + 1
        mrows.append((f"{datetime.date(yy, m, 1):%b-%y}", f"Recd {cr(a)} | Paid {cr(b)} | Net {cr(a - b)}"))
    mrows.append(("TOTAL (YTD)", f"Recd {cr(rec_y)} | Paid {cr(paid_y)} | Net {cr(rec_y - paid_y)}"))

    r_by = r_m.groupby("party")["amt"].sum().sort_values(ascending=False)
    r_by = r_by[r_by > 0]
    p_cat = p_m.groupby("cat")["amt"].sum().sort_values(ascending=False)
    p_by = p_m.groupby("party")["amt"].sum().sort_values(ascending=False)

    details = [
        (f"📅 Month-wise (Apr to {lab})", mrows),
        (f"💰 {lab} · Received party-wise ({len(r_by)} parties)",
         [(esc(k), _inr(v)) for k, v in r_by.items()] + [("TOTAL RECEIVED", _inr(rec_m))]),
    ]
    if has_cat:
        details.append((f"📂 {lab} · Paid category-wise ({len(p_cat)})",
                        [(esc(k), _inr(v)) for k, v in p_cat.items()] + [("TOTAL PAID", _inr(paid_m))]))
        details.append((f"💸 {lab} · Paid party-wise ({len(p_by)})",
                        [(esc(k), _inr(v)) for k, v in p_by.items()] + [("TOTAL PAID", _inr(paid_m))]))
    else:
        details.append((f"💸 {lab} · Paid ({len(p_by)} heads)",
                        [(esc(k), _inr(v)) for k, v in p_by.items()] + [("TOTAL PAID", _inr(paid_m))]))

    return {
        "value": f"Recd {cr(rec_m)} | Paid {cr(paid_m)}",
        "desc": f"{lab}{' (till date)' if live else ''} · Month total",
        "color": BLUE,
        "metrics": [(cr(rec_m), f"Received {lab}"), (cr(paid_m), f"Paid {lab}")],
        "sections": [
            (f"📌 {lab} · Exact amount", [
                ("Received", _inr(rec_m)), ("Paid", _inr(paid_m)),
                ("Net (Received - Paid)", _inr(rec_m - paid_m))]),
            (f"📆 1 Apr to {lab} (till date)", [
                ("Received", _inr(rec_y)), ("Paid", _inr(paid_y)),
                ("Net (Received - Paid)", _inr(rec_y - paid_y))]),
        ],
        "details": details,
    }


def _rp_avg_month(df, amt_col, day):
    """1 April se `day` tak total, kitne din ka data hai, aur avg per month = total / days x 30."""
    w = df[df["_date"].notna() & (df["_date"] >= RP_FY_START) & (df["_date"] <= day)]
    if w.empty:
        return None
    total = float(_num(w[amt_col]).fillna(0.0).sum())
    start, end = w["_date"].min(), w["_date"].max()
    days = (end - start).days + 1
    return {"total": total, "start": start, "end": end, "days": days, "avg": total / days * 30}


def finance_recv_pay_days_card(day):
    d, e, _ = get_sheet("finance_drs_crs_new")
    sdf, e2, _ = get_sheet("daily_sales_report")
    pdf, e3, _ = get_sheet("purchase_excel")
    for nm, fr, er in (("DRS/CRS", d, e), ("Sales", sdf, e2), ("Purchase", pdf, e3)):
        if fr is None:
            return {"value": "Error", "desc": f"{nm} data error: {er}", "color": RED}

    norm = lambda s: re.sub(r"[^A-Z]", "", str(s).upper())
    g = next((c for c in d.columns if norm(c) == "GROUP"), None)
    b = next((c for c in d.columns if norm(c) == "CLOSINGBALANCE"), None)
    s_col = next((c for c in sdf.columns if "TOTAL SALE" in str(c).upper()), None)
    p_col = next((c for c in pdf.columns if norm(c) == "BILLAMOUNT"), None)
    if not (g and b):
        return {"value": "Config error", "desc": f"DRS/CRS file mein Group / Closing Balance not found. Columns: {list(d.columns)}", "color": RED}
    if not s_col:
        return {"value": "Config error", "desc": "TOTAL SALE AMOUNT column not found in Sales sheet", "color": RED}
    if not p_col:
        return {"value": "Config error", "desc": "Bill Amount column not found in Purchase sheet", "color": RED}

    grp = d[g].astype(str).str.strip().str.upper()
    bal = _num(d[b]).fillna(0.0)
    drs, crs = float(bal[grp == "SD"].sum()), float(bal[grp == "SC"].sum())

    sa = _rp_avg_month(sdf, s_col, day)
    pa = _rp_avg_month(pdf, p_col, day)
    if not sa or sa["avg"] <= 0:
        return {"value": "No Data", "desc": "Sale data not found", "color": GREY}
    if not pa or pa["avg"] <= 0:
        return {"value": "No Data", "desc": "Purchase data not found", "color": GREY}

    rd = drs * 30 / sa["avg"]
    pdays = crs * 30 / pa["avg"]
    cr = lambda x: f"{x / 10000000:,.2f} Cr"

    warn = ""
    if sa["start"] > RP_FY_START:
        warn = f" · ⚠ Sale data {sa['start']:%d-%b} only (not from April)"

    def block(title, net, a, label):
        return (title, [
            (f"Net {label} (closing balance)", _inr(net)),
            (f"{label[:4]} period", f"{a['start']:%d-%m-%Y} to {a['end']:%d-%m-%Y} ({a['days']} days)"),
            ("Total", _inr(a["total"])),
            ("Avg per month (Total ÷ days × 30)", _inr(a["avg"])),
        ])

    return {
        "value": f"Recv {rd:,.1f} d | Pay {pdays:,.1f} d",
        "desc": f"Till {max(sa['end'], pa['end']):%d-%b-%Y}{warn}",
        "color": BLUE if sa["start"] <= RP_FY_START else AMBER,
        "metrics": [(f"{rd:,.1f}", "Receivable Days", "yield"), (f"{pdays:,.1f}", "Payable Days")],
        "sections": [("📌 Net outstanding", [("Net DRS (Debtors)", cr(drs)), ("Net CRS (Creditors)", cr(crs))])],
        "details": [
            block("📥 Receivable Days = Net DRS × 30 ÷ Avg Sale per month", drs, sa, "DRS"),
            block("📤 Payable Days = Net CRS × 30 ÷ Avg Purchase per month", crs, pa, "CRS"),
        ],
    }


def finance_gt90_month_card(day):
    import html as _html
    df, err, _ = get_sheet("finance_gt90")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}

    w = df.copy()
    w.columns = [str(c).strip() for c in w.columns]

    party_col = next((c for c in w.columns if "party" in c.lower()), None)
    if not party_col:
        return {"value": "Config error", "desc": f"Party column not found: {list(w.columns)}", "color": RED}

    # Auto-detect dono sheet formats (New: 61-120 / >120 / >180  OR  Old: 91-120 / 120-180 / >180)
    if "61-120 Days" in w.columns and ">120 Days" in w.columns:
        c1_col, c2_col, c3_col = "61-120 Days", ">120 Days", ">180 Days"
        drs_col = "0-15 Days" if "0-15 Days" in w.columns else "Total Amount"
        lbl_gt = "Greater than 60 Days"
    elif "91-120 Days" in w.columns and "120-180 Days" in w.columns:
        c1_col, c2_col, c3_col = "91-120 Days", "120-180 Days", ">180 Days"
        drs_col = "Total Amount" if "Total Amount" in w.columns else "0-15 Days"
        lbl_gt = "Greater than 90 Days"
    else:
        return {"value": "Config error", "desc": f"Buckets not found in: {list(w.columns)}", "color": RED}

    for c in [c1_col, c2_col, c3_col, drs_col]:
        w[c] = pd.to_numeric(
            w[c].astype(str).str.replace(",", "", regex=False).str.strip(),
            errors="coerce",
        ).fillna(0.0) if c in w.columns else 0.0

    w["party"] = w[party_col].astype(str).str.strip()
    w = w[w["party"] != ""]
    w = w[~w["party"].str.lower().str.contains("total|grand", regex=True)]

    # Month filter (agar sheet mein Month/_date hai toh filter karega, warna current selected month maane)
    if "_date" in w.columns and w["_date"].notna().any():
        w["m"] = pd.to_datetime(w["_date"]).dt.month
    elif "Month" in w.columns:
        w["m"] = _parse_dates(w["Month"], dayfirst=True).dt.month.fillna(day.month).astype(int)
    else:
        w["m"] = day.month

    w = w.dropna(subset=["m"])
    w["m"] = w["m"].astype(int)
    if day.month not in set(w["m"]):
        return None

    today = datetime.datetime.now(IST).date()
    cr = lambda x: f"{x / 10000000:,.2f} Cr"
    esc = lambda x: _html.escape(str(x))
    pct = lambda part, whole: (part / whole * 100.0) if whole > 0 else 0.0

    def tot(m):
        s = w[w["m"] == m]
        return float(s[c1_col].sum()), float(s[c2_col].sum()), float(s[c3_col].sum()), float(s[drs_col].sum())

    c1, c2, c3, _unused = tot(day.month)
    total_drs = _drs_total_sd()
    tot_gt = c1 + c2 + c3
    p1, p2, p3, p_tot = pct(c1, total_drs), pct(c2, total_drs), pct(c3, total_drs), pct(tot_gt, total_drs)

    rows_all = []
    for m in sorted(set(w["m"]), key=lambda m: _bal_month_date(m, today), reverse=True):
        x1, x2, x3, xdrs = tot(m)
        xdrs = total_drs
        xtot = x1 + x2 + x3
        rows_all.append((
            f"{_bal_month_date(m, today):%b-%y}",
            f"{c1_col}: {cr(x1)} | {c2_col}: {cr(x2)} | {c3_col}: {cr(x3)} | Total: {cr(xtot)} ({pct(xtot, xdrs):.2f}% DRS)"
        ))

    g = w[w["m"] == day.month].groupby("party", as_index=False)[[c1_col, c2_col, c3_col]].sum()
    g["tot_gt"] = g[c1_col] + g[c2_col] + g[c3_col]

    g_all = g[g["tot_gt"] > 0.005].sort_values("tot_gt", ascending=False)
    g_c1  = g[g[c1_col] > 0.005].sort_values(c1_col, ascending=False)
    g_c2  = g[g[c2_col] > 0.005].sort_values(c2_col, ascending=False)
    g_c3  = g[g[c3_col] > 0.005].sort_values(c3_col, ascending=False)

    r_all = [(esc(r["party"]), f"{_inr(r['tot_gt'])} ({pct(r['tot_gt'], total_drs):.2f}% DRS)") for _, r in g_all.iterrows()]
    r_c1  = [(esc(r["party"]), f"{_inr(r[c1_col])} ({pct(r[c1_col], total_drs):.2f}%)") for _, r in g_c1.iterrows()]
    r_c2  = [(esc(r["party"]), f"{_inr(r[c2_col])} ({pct(r[c2_col], total_drs):.2f}%)") for _, r in g_c2.iterrows()]
    r_c3  = [(esc(r["party"]), f"{_inr(r[c3_col])} ({pct(r[c3_col], total_drs):.2f}%)") for _, r in g_c3.iterrows()]

    return {
        "value": f"{cr(tot_gt)} ({p_tot:.2f}%)",
        "desc": f"{lbl_gt} · {day:%b-%y} · {p_tot:.2f}% of Total DRS ({cr(total_drs)})",
        "color": RED if tot_gt > 0 else BLUE,
        "metrics": [
            (f"{p_tot:.2f}%", "% of DRS"),
            (cr(c1), c1_col),
            (cr(c2), c2_col),
            (cr(c3), c3_col),
        ],
        "sections": [(f"📌 Exact amount & DRS % · {day:%b-%y}", [
            (f"{c1_col} ({p1:.2f}%)", _inr(c1)),
            (f"{c2_col} ({p2:.2f}%)", _inr(c2)),
            (f"{c3_col} ({p3:.2f}%)", _inr(c3)),
            ("Total Overdue", f"{_inr(tot_gt)} ({p_tot:.2f}% of DRS)"),
        ])],
        "details": [
            ("📊 All Months · Month-wise", rows_all),
            (f"👥 Party-wise · Combined · {day:%b-%y} ({len(r_all)} parties)",
             r_all + [("TOTAL", f"{_inr(tot_gt)} ({p_tot:.2f}% DRS)")] if r_all else [("No party", "✅")]),
            (f"👥 Party-wise · {c1_col} · {day:%b-%y} ({len(r_c1)} parties)",
             r_c1 + [("TOTAL", f"{_inr(c1)} ({p1:.2f}%)")] if r_c1 else [("No party", "✅")]),
            (f"👥 Party-wise · {c2_col} · {day:%b-%y} ({len(r_c2)} parties)",
             r_c2 + [("TOTAL", f"{_inr(c2)} ({p2:.2f}%)")] if r_c2 else [("No party", "✅")]),
            (f"👥 Party-wise · {c3_col} · {day:%b-%y} ({len(r_c3)} parties)",
             r_c3 + [("TOTAL", f"{_inr(c3)} ({p3:.2f}%)")] if r_c3 else [("No party", "✅")]),
        ],
    }
def inv_dead_stock_card(day):
    import html as _html
    esc = lambda x: _html.escape(str(x))
    fmt_n = lambda x: f"{int(x):,}" if float(x).is_integer() else f"{x:,.2f}"

    df, err, _ = get_sheet("dead_stock_store")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}

    w = df.copy()
    # Column headers se newline (\n) aur extra space hatayein
    w.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in w.columns]

    mat_col = next((c for c in w.columns if c.upper() == "MATERIAL"), None)
    cat_col = next((c for c in w.columns if c.upper() == "CATEGORY"), None)
    uom_col = next((c for c in w.columns if c.upper() == "UOM"), None)

    if not mat_col or not uom_col:
        return {"value": "Config error", "desc": f"Columns not found: {list(w.columns)}", "color": RED}

    # Sabse aakhiri date column (jaise '18.10.26') automatically pick karein
    ignore = {mat_col, cat_col, uom_col}
    val_candidates = [c for c in w.columns if c not in ignore and "SR" not in c.upper()]
    qty_col = val_candidates[-1] if val_candidates else None
    if not qty_col:
        return {"value": "Config error", "desc": "Stock balance column not found", "color": RED}

    records = []
    sub_cat = None

    for _, row in w.iterrows():
        mat = str(row.get(mat_col, "")).strip()
        cat = str(row.get(cat_col, "")).strip() if cat_col else ""
        uom = str(row.get(uom_col, "")).strip().upper()
        val_raw = str(row.get(qty_col, "")).strip()

        if not mat or mat.lower() == "nan":
            continue

        # Niche wali sub-tables ('OLD MATTRESS COVER' / 'OLD INNNER COVER') ko handle karein
        if mat.upper() in ("OLD MATTRESS COVER", "OLD INNNER COVER", "OLD INNER COVER"):
            sub_cat = mat.title()
            continue

        if sub_cat:
            bdl_val = pd.to_numeric(uom, errors="coerce")
            pcs_val = pd.to_numeric(val_raw, errors="coerce")
            if pd.notna(bdl_val) and bdl_val > 0:
                records.append({"category": sub_cat, "material": mat, "uom": "BDL", "qty": float(bdl_val)})
            if pd.notna(pcs_val) and pcs_val > 0:
                records.append({"category": sub_cat, "material": mat, "uom": "PCS", "qty": float(pcs_val)})
        else:
            qty = pd.to_numeric(val_raw.replace(",", ""), errors="coerce")
            if pd.notna(qty) and qty > 0 and uom and uom != "NAN":
                cat_name = cat if (cat and cat.lower() != "nan") else "General / Other"
                records.append({"category": cat_name, "material": mat, "uom": uom, "qty": float(qty)})

    if not records:
        return {"value": "0 Items", "desc": "No dead stock", "color": BLUE}

    res = pd.DataFrame(records)

    # UOM ke full labels
    uom_labels = {
        "BDL": "Total Bundles",
        "PCS": "Total Pcs",
        "NO.": "Total No.",
        "ROLL": "Total Roll",
        "BOX": "Total Box",
    }
    uom_order = ["BDL", "PCS", "NO.", "ROLL", "BOX"]
    uom_sums = res.groupby("uom")["qty"].sum().to_dict()
    all_uoms = [u for u in uom_order if u in uom_sums] + [u for u in sorted(uom_sums) if u not in uom_order]

    # Upar card par dikhane ke liye summary text aur tiles
    summary_parts = [f"{uom_labels.get(u, u)}: {fmt_n(uom_sums[u])}" for u in all_uoms]
    tiles = [(fmt_n(uom_sums[u]), uom_labels.get(u, u)) for u in all_uoms]

    # Sections: UOM-wise Grand Total
    sec_rows = [(f"{uom_labels.get(u, u)} ({u})", fmt_n(uom_sums[u])) for u in all_uoms]

    # View Full Details:
    # 1) Category-wise Total (har category mein kitne BDL, PCS, NO., ROLL, BOX hain)
    cat_summary_rows = []
    for cat_name, grp in res.groupby("category", sort=True):
        c_uoms = grp.groupby("uom")["qty"].sum().to_dict()
        parts = [f"{u}: {fmt_n(c_uoms[u])}" for u in all_uoms if u in c_uoms]
        cat_summary_rows.append((esc(cat_name), " | ".join(parts)))

    details_list = [
        (f"📊 Category-wise Total Summary ({len(cat_summary_rows)} categories)", cat_summary_rows)
    ]

    # 2) Har Category ke niche uske saare Materials + unke UOM totals (jaise Corner ke niche saare Corner materials)
    for cat_name, grp in res.groupby("category", sort=True):
        c_uoms = grp.groupby("uom")["qty"].sum().to_dict()
        cat_tot_str = " | ".join([f"{u}: {fmt_n(c_uoms[u])}" for u in all_uoms if u in c_uoms])

        mat_rows = []
        for _, r in grp.iterrows():
            mat_rows.append((esc(r["material"]), f"{fmt_n(r['qty'])} {r['uom']}"))
        mat_rows.append((f"TOTAL ({esc(cat_name)})", cat_tot_str))

        details_list.append((f"📦 {cat_name} ({cat_tot_str})", mat_rows))

    return {
        "value": f"BDL: {fmt_n(uom_sums.get('BDL', 0))} | PCS: {fmt_n(uom_sums.get('PCS', 0))}",
        "desc": f"As on {qty_col} · " + " · ".join(summary_parts),
        "color": BLUE,
        "metrics": tiles,
        "sections": [(f"📌 Total Stock by UOM ({qty_col})", sec_rows)],
        "details": details_list,
    }
def prod_category_mix_card(day):
    import html as _html
    esc = lambda x: _html.escape(str(x))
    fmt_i = lambda x: f"{int(round(float(x))):,}"
    fmt_k = lambda x: f"{float(x):,.1f}"
    fmt_amt = lambda x: f"₹{float(x):,.2f}"

    # Apni CATEGORY MIX wali sheet key yahan rakhein (jaise "category_mix" ya jo aapke SHEETS mein hai)
    df, err, _ = get_sheet("cate_1")
    if df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}

    w = df.copy()
    w.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in w.columns]

    # Agar sheet mein date column hai toh selected month/date filter lagayein, warna poori sheet lein
    if "_date" in w.columns and w["_date"].notna().any():
        m_df = w[pd.to_datetime(w["_date"]).dt.to_period("M") == pd.Period(day, freq="M")]
        if not m_df.empty:
            w = m_df

    def _find_col(names):
        for n in names:
            for c in w.columns:
                if c.lower() == n.lower():
                    return c
        return None

    item_col = _find_col(["ITEM", "Item", "Category", "Product"])
    grade_col = _find_col(["Grade", "GRADE", "Quality", "Sub Category"])
    bdl_col = _find_col(["Bundle", "Bundles", "BDL", "Rolls", "Roll"])
    pcs_col = _find_col(["Pcs", "PCS", "Pieces", "Qty"])
    kgs_col = _find_col(["Kgs", "Kg", "KG", "Weight"])
    amt_col = _find_col(["Amt", "Amount", "Value", "Total Amt", "Net Amt"])

    if not item_col:
        return {"value": "Config error", "desc": f"ITEM column not found: {list(w.columns)}", "color": RED}

    for col in [bdl_col, pcs_col, kgs_col, amt_col]:
        if col:
            w[col] = pd.to_numeric(w[col].astype(str).str.replace(",", "").str.replace("₹", "").str.strip(), errors="coerce").fillna(0.0)
        else:
            w[col] = 0.0

    # Blank ITEM rows ko skip mat karo — unhe "UNSPECIFIED" category mein rakho taaki ek bhi row na chute
    w["_item"] = w[item_col].fillna("").astype(str).str.strip()
    w.loc[w["_item"].isin(["", "nan", "None", "NaN"]), "_item"] = "UNSPECIFIED"

    w["_grade"] = w[grade_col].fillna("").astype(str).str.strip() if grade_col else "-"
    w.loc[w["_grade"].isin(["", "nan", "None", "NaN"]), "_grade"] = "-"

    # Sirf completely zero rows hatayein (jahan Bdl, Pcs, Kgs, Amt chaaron 0 hon)
    w = w[(w[bdl_col] != 0) | (w[pcs_col] != 0) | (w[kgs_col] != 0) | (w[amt_col] != 0)].copy()

    if w.empty:
        return {"value": "0 Items", "desc": "No data found", "color": GREY}

    tot_bdl = w[bdl_col].sum()
    tot_pcs = w[pcs_col].sum()
    tot_kgs = w[kgs_col].sum()
    tot_amt = w[amt_col].sum()

    # Har ek ITEM category ka summary (ek bhi skip nahi hoga)
    cat_rows = []
    details_list = []

    # Sheet mein jis order mein items aaye hain usi order mein (ya alphabetical) dikhayein
    item_order = list(dict.fromkeys(w["_item"].tolist()))

    for item_name in item_order:
        grp = w[w["_item"] == item_name]
        c_bdl = grp[bdl_col].sum()
        c_pcs = grp[pcs_col].sum()
        c_kgs = grp[kgs_col].sum()
        c_amt = grp[amt_col].sum()

        summary_line = f"{fmt_i(c_bdl)} Bdls | {fmt_i(c_pcs)} Pcs | {fmt_k(c_kgs)} Kg | {fmt_amt(c_amt)}"
        cat_rows.append((esc(item_name), summary_line))

        # View Full Details: Har ITEM ke niche uske saare Grades + Totals
        grade_rows = []
        for _, r in grp.iterrows():
            g_str = f"{fmt_i(r[bdl_col])} Bdls | {fmt_i(r[pcs_col])} Pcs | {fmt_k(r[kgs_col])} Kg | {fmt_amt(r[amt_col])}"
            grade_rows.append((esc(r["_grade"]), g_str))

        grade_rows.append((f"TOTAL ({esc(item_name)})", summary_line))
        details_list.append((f"📦 {item_name} ({summary_line})", grade_rows))

    # Sabse niche Grand Total row
    grand_line = f"{fmt_i(tot_bdl)} Bdls | {fmt_i(tot_pcs)} Pcs | {fmt_k(tot_kgs)} Kg | {fmt_amt(tot_amt)}"
    cat_rows.append(("TOTAL (all items)", grand_line))

    return {
        "value": fmt_amt(tot_amt),
        "desc": f"Production category mix · {day:%b-%Y} ({len(item_order)} categories)",
        "color": BLUE,
        "metrics": [
            (fmt_i(tot_bdl), "BUNDLES"),
            (fmt_i(tot_pcs), "PCS"),
            (fmt_k(tot_kgs), "KG"),
            (fmt_amt(tot_amt), "TOTAL AMT"),
        ],
        "sections": [
            (f"📅 {day:%b-%y} · Category wise ({len(item_order)} Categories)", cat_rows)
        ],
        "details": details_list,
    }
def rec_payable_days_card(day):
    """Receivable & Payable Days: DRS & CRS + Daily Basis Sales + Purchase sheet se."""
    drs_df, err1, _ = get_sheet("drs_crs")
    if drs_df is None:
        return {"value": "Error", "desc": f"DRS & CRS error: {err1}", "color": RED}

    sales_df, err2, _ = get_sheet("daily_sales_sheet")
    if sales_df is None:
        return {"value": "Error", "desc": f"Sales sheet error: {err2}", "color": RED}

    purch_df, err3, _ = get_sheet("purchase_daily")
    if purch_df is None:
        return {"value": "Error", "desc": f"Purchase sheet error: {err3}", "color": RED}

    def _fmt_cr(v):
        v = float(v)
        if abs(v) >= 1e7:
            return f"₹{v / 1e7:,.2f} Cr"
        elif abs(v) >= 1e5:
            return f"₹{v / 1e5:,.2f} L"
        return f"₹{v:,.0f}"

    # 1. DRS & CRS se Net Receivable Out (SD) aur Net Creditors Out (SC)
    d = drs_df.copy()
    d.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in d.columns]
    grp_col = next((c for c in d.columns if c.lower() == "group"), None)
    bal_col = next((c for c in d.columns if "closing" in c.lower()), None)
    party_col = next((c for c in d.columns if "party" in c.lower()), d.columns[0])

    if not grp_col or not bal_col:
        return {"value": "Config error", "desc": f"Group/Closing column not found: {list(d.columns)}", "color": RED}

    d[bal_col] = pd.to_numeric(d[bal_col].astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(0.0)
    d["_grp"] = d[grp_col].astype(str).str.strip().str.upper()

    sd_df = d[d["_grp"] == "SD"].copy()
    sc_df = d[d["_grp"] == "SC"].copy()

    net_rec_out = float(sd_df[bal_col].sum())
    net_crs_out = float(sc_df[bal_col].sum())

    # 2. DAILY BASIS SALES se Avg Sale P.M Till Date
    s = sales_df.copy()
    s.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in s.columns]
    s_dt_col = next((c for c in s.columns if "date" in c.lower()), "_date" if "_date" in s.columns else None)
    s_amt_col = next((c for c in s.columns if "sale" in c.lower() or "amount" in c.lower() or "amt" in c.lower()), None)

    if not s_amt_col:
        return {"value": "Config error", "desc": f"Sale Amount column not found: {list(s.columns)}", "color": RED}

    s[s_amt_col] = pd.to_numeric(s[s_amt_col].astype(str).str.replace(",", "").str.replace("₹", "").str.strip(), errors="coerce").fillna(0.0)
    if s_dt_col:
        s["_dt"] = pd.to_datetime(s[s_dt_col], dayfirst=True, errors="coerce")
        s = s[s["_dt"].notna() & (s["_dt"].dt.date <= day)].copy()
        s_months = max(int(s["_dt"].dt.to_period("M").nunique()), 1)
    else:
        s_months = 1

    tot_sale = float(s[s_amt_col].sum())
    avg_sale_pm = tot_sale / s_months if s_months else 0.0
    rec_days = (net_rec_out * 30.0 / avg_sale_pm) if avg_sale_pm > 0 else 0.0

    # 3. PURCHASE sheet se Avg Purchase P.M Till Date (Bill Amount column)
    p = purch_df.copy()
    p.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in p.columns]
    p_dt_col = next((c for c in p.columns if "date" in c.lower()), "_date" if "_date" in p.columns else None)
    p_amt_col = next((c for c in p.columns if "bill amount" in c.lower()), None) or next(
        (c for c in p.columns if "amount" in c.lower() or "taxvalue" in c.lower()), None
    )

    if not p_amt_col:
        return {"value": "Config error", "desc": f"Purchase Amount column not found: {list(p.columns)}", "color": RED}

    p[p_amt_col] = pd.to_numeric(p[p_amt_col].astype(str).str.replace(",", "").str.replace("₹", "").str.strip(), errors="coerce").fillna(0.0)
    if p_dt_col:
        p["_dt"] = pd.to_datetime(p[p_dt_col], dayfirst=True, errors="coerce")
        p = p[p["_dt"].notna() & (p["_dt"].dt.date <= day)].copy()
        p_months = max(int(p["_dt"].dt.to_period("M").nunique()), 1)
    else:
        p_months = 1

    tot_purch = float(p[p_amt_col].sum())
    avg_purch_pm = tot_purch / p_months if p_months else 0.0
    pay_days = (net_crs_out * 30.0 / avg_purch_pm) if avg_purch_pm > 0 else 0.0

    # Top 15 Debtors & Creditors for View Full Details
    top_sd = sd_df.sort_values(bal_col, ascending=False).head(15)
    top_sc = sc_df.sort_values(bal_col, ascending=False).head(15)

    return {
        "value": f"{rec_days:.1f} / {pay_days:.1f} Days",
        "desc": f"Receivable: {rec_days:.1f} Days · Payable: {pay_days:.1f} Days",
        "color": BLUE,
        "metrics": [
            (f"{rec_days:.1f} Days", "RECEIVABLE DAYS"),
            (f"{pay_days:.1f} Days", "PAYABLE DAYS"),
        ],
        "sections": [
            ("📊 Calculation Breakdown", [
                ("Net Receivable Out (SD)", _fmt_cr(net_rec_out)),
                (f"Avg Sale P.M ({s_months}m till date)", _fmt_cr(avg_sale_pm)),
                ("Receivable Days", f"{rec_days:.1f} Days"),
                ("Net Creditors Out (SC)", _fmt_cr(net_crs_out)),
                (f"Avg Purchase P.M ({p_months}m till date)", _fmt_cr(avg_purch_pm)),
                ("Payable Days", f"{pay_days:.1f} Days"),
            ]),
        ],
        "details": [
            (f"📥 Top 15 Debtors (SD · Total {_fmt_cr(net_rec_out)})", [
                (str(r[party_col]).strip(), _fmt_cr(r[bal_col])) for _, r in top_sd.iterrows()
            ]),
            (f"📤 Top 15 Creditors (SC · Total {_fmt_cr(net_crs_out)})", [
                (str(r[party_col]).strip(), _fmt_cr(r[bal_col])) for _, r in top_sc.iterrows()
            ]),
        ],
    }


# ====================================================================
# 9. RENDER HELPERS
# ====================================================================
KPI_PER_ROW = 4


def _tiles_html(metrics):
    out = []
    for m in metrics:
        num, lbl = m[0], m[1]
        cls = "kpi-tile yield" if len(m) > 2 and m[2] == "yield" else "kpi-tile"
        out.append(f'<div class="{cls}"><div class="kpi-num">{num}</div><div class="kpi-lbl">{lbl}</div></div>')
    return '<div class="kpi-tiles">' + "".join(out) + "</div>"


def _sections_html(sections):
    out = []
    for heading, rows in sections:
        body = "".join(
            f'<div class="kpi-row" style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px dashed #E2E8F0;">'
            f'<span class="kpi-rl" style="font-size: 13px; font-weight: 700; color: #334155; white-space: normal; text-align: left; line-height: 1.3;">{l}</span>'
            f'<span class="kpi-rv" style="font-size: 13px; font-weight: 800; color: #0F172A; text-align: left; line-height: 1.2;">{v}</span>'
            f'</div>'
            for l, v in rows
        )
        out.append(f'<div class="kpi-sec"><div class="kpi-sec-h" style="margin-bottom: 6px;">{heading}</div>{body}</div>')
    return "".join(out)
PROD_AVG_MANPOWER = {}   # baad me data aaye to: {"Bdls & Yield": "18", "Mould": "12"}
PROD_TARGETS = {}        # baad me data aaye to: {"Bdls & Yield": "20 Tons"}

def _prod_add_tiles(res, title):
    """Production ke har card me 2 tiles jodta hai: Avg Manpower aur Target."""
    r = dict(res)
    m = list(r.get("metrics") or [])
    if not m:
        m = [(r.get("value", "—"), "Value")]
    m.append((PROD_AVG_MANPOWER.get(title, "—"), "Avg Manpower"))
    m.append((PROD_TARGETS.get(title, "—"), "Target"))
    r["metrics"] = m
    return r
# ============ PRODUCTION: AVG MANPOWER (day-wise) + TARGET (unit-wise) — ADD-ON ============
# ============ PRODUCTION: AVG MANPOWER (day-wise) + TARGET (unit-wise) — FIXED ============
import re as _re2
import pandas as _pd2
import datetime as _dt2

PROD_TARGET_PUB = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS-f8spNA_4dJLh7yGuzJdESA9D9eKfBEtYH3d-aI6vgc50qkwM__cbrk6wU0pRmg/pubhtml"
PROD_TARGET_GID = "760559634"

_PT_DATE_RE = _re2.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{2}$")

def _pt_csv_url():
    base = PROD_TARGET_PUB.split("/pub")[0]
    return f"{base}/pub?gid={PROD_TARGET_GID}&single=true&output=csv"

def _pt_to_num(val):
    try:
        s = str(val or "").replace(",", "").strip()
        return float(s) if s else None
    except Exception:
        return None

def _pt_unit(u):
    u = str(u or "").strip().upper().replace(" ", "").replace(".", "")
    if u.startswith("ROLL"):  return "Rolls"
    if u.startswith("MTR"):   return "Mtr"
    if u.startswith("KG"):    return "Kg"
    if u.startswith("BLOCK"): return "Blocks"
    if u.startswith("BDL") or u.startswith("BUNDLE"): return "Bdls"
    if u.startswith("PCS"):   return "Pcs"
    return ""

@st.cache_data(ttl=600, show_spinner=False)
def prod_target_df():
    try:
        raw = _pd2.read_csv(_pt_csv_url(), header=None, dtype=str, keep_default_na=False)
    except Exception:
        return _pd2.DataFrame(columns=["ym", "shed", "unit", "sub", "target"])
    
    rows = raw.values.tolist()
    out = []
    hdr_idx = [i for i, r in enumerate(rows) if len(r) > 0 and str(r[0]).strip().lower() == "shed name"]
    
    for k, h in enumerate(hdr_idx):
        drow = rows[h - 1] if h > 0 else []
        yms = []
        for c in drow:
            c = str(c).strip()
            if _PT_DATE_RE.match(c):
                try:
                    d = _dt2.datetime.strptime(c, "%d-%b-%y")
                    yms.append(d.strftime("%Y-%m"))
                except Exception:
                    pass
        if not yms:
            continue
        ym = max(set(yms), key=yms.count)
        end = hdr_idx[k + 1] - 1 if k + 1 < len(hdr_idx) else len(rows)
        shed = ""
        for r in rows[h + 1:end]:
            if len(r) < 4 or not any(str(x).strip() for x in r[:4]):
                continue
            if str(r[0]).strip():
                shed = str(r[0]).strip()
            t = _pt_to_num(r[3])
            if t is None or t == 0:
                continue
            out.append({
                "ym": ym,
                "shed": shed,
                "unit": _pt_unit(r[1]),
                "sub": str(r[2]).strip(),
                "target": float(t)
            })
    return _pd2.DataFrame(out)

# Keys ko UPPERCASE rakha hai taaki title case mismatch na ho
PROD_CARD_MAP = {
    "ROLLS & YIELD":    [("Peeling", "PEELING", ["PEELING"]), ("Looper", "LOOPER", ["LOOPER"])],
    "BDLS & YIELD":     [("D Shed", "SHED D", ["D SHED", "SHED D"]), ("E Shed", "SHED E", ["E SHED", "SHED E"])],
    "ROLLPACK & YIELD": [("Emma", "EMMA", ["EMMA"])],
    "MATTRESS & YIELD": [("Mattress", "MATTERESS", ["MATTRESS", "MATTERESS"])],
    "PILLOW & YIELD":   [("Pillow", "PILLOW", ["PILLOW"])],
    "MOULD":            [("Mould", "MOULD", ["MOULD"])],
    "BONDED":           [("Bonded", "BONDED", ["BOUND", "BONDED"])],
    "SCRAP":            [("Scrap", "SCRAP", ["BAILLING", "BAILING", "BALING"])],
}

def _pt_find(df, key):
    clean_key = key.upper().replace(" ", "")
    return df[df["shed"].str.upper().str.replace(" ", "").str.contains(clean_key, regex=False)]

def _pt_target_text(df, ym, key):
    d = _pt_find(df[df["ym"] == ym], key)
    if d.empty:
        return None
    parts = []
    for (u, sub), g in d.groupby(["unit", "sub"], sort=False):
        t = g["target"].iloc[0]
        lab = u or ""
        s = str(sub).upper()
        if "NIGHT" in s:
            lab = (lab + " Night").strip()
        elif "DAY" in s and len(d) > 1 and ("PCS" in s or "KG" in s):
            lab = (lab + " Day").strip()
        if "(KG)" in s and not u:
            lab = "Kg"
        if "(PCS)" in s and not u:
            lab = "Pcs"
        parts.append(f"{t:,.0f} {lab}".strip())
    return " · ".join(parts)

def _pt_manpower(day, kws):
    try:
        m = hr_manpower_df()
        if m is None or m.empty:
            return None, None
        m = m.copy()
        m["_n"] = m["dept"].astype(str).str.upper()
        sel = m[m["_n"].apply(lambda x: any(k in x for k in kws))]
        if sel.empty:
            return None, None
        day = _pd2.Timestamp(day).normalize()
        sel["_dt_norm"] = _pd2.to_datetime(sel["_date"]).dt.normalize()
        sel = sel[(sel["_dt_norm"] <= day) & (sel["man"].notna())]
        if sel.empty:
            return None, None
        last = sel["_dt_norm"].max()
        v = sel[sel["_dt_norm"] == last]["man"].sum()
        return float(v), last
    except Exception:
        return None, None

def _prod_add_tiles(res, title, day=None):
    try:
        # Agar day pass nahi hua, to res ke metrics/subtitle se date nikalne ki koshish karega
        if day is None and isinstance(res, dict):
            sub_txt = str(res.get("subtitle", "")) + " " + str(res.get("date", ""))
            m_dt = _re2.search(r"\d{2}-\d{2}-\d{4}|\d{2}-[A-Za-z]{3}-\d{4}", sub_txt)
            if m_dt:
                day = _pd2.to_datetime(m_dt.group(0), dayfirst=True, errors="coerce")
        
        day = _pd2.Timestamp(day) if (day is not None and not _pd2.isna(day)) else _pd2.Timestamp.today()
        ym = day.strftime("%Y-%m")
        
        tdf = prod_target_df()
        if tdf is not None and not tdf.empty and ym not in set(tdf["ym"]):
            ym = max(tdf["ym"])

        t_upper = str(title or "").strip().upper()
        blocks = PROD_CARD_MAP.get(t_upper)

        if t_upper == "TOTAL PRODUCTION & YIELD":
            blocks = [x for v in PROD_CARD_MAP.values() for x in v]
            tg = {}
            tot_mp = 0.0
            for lab, key, kws in blocks:
                v, _d = _pt_manpower(day, kws)
                tot_mp += v or 0
                d = _pt_find(tdf[tdf["ym"] == ym], key) if (tdf is not None and not tdf.empty) else None
                if d is not None:
                    for _, r in d.iterrows():
                        if r["unit"]:
                            tg[r["unit"]] = tg.get(r["unit"], 0) + r["target"]
            res["metrics"].append((f"{tot_mp:,.0f}" if tot_mp else "—", "Avg Manpower"))
            res["metrics"].append((" · ".join(f"{v:,.0f} {u}" for u, v in tg.items()) or "—", "Target / Shift"))
            return res

        if not blocks:
            res["metrics"].append(("—", "Avg Manpower"))
            res["metrics"].append(("—", "Target"))
            return res

        mp_parts, tg_tiles = [], []
        for lab, key, kws in blocks:
            v, _d = _pt_manpower(day, kws)
            if v is not None:
                mp_parts.append(f"{lab} {v:,.0f}" if len(blocks) > 1 else f"{v:,.0f}")
            txt = _pt_target_text(tdf, ym, key) if (tdf is not None and not tdf.empty) else None
            tg_tiles.append((txt or "—", f"{lab} Target / Shift" if len(blocks) > 1 else "Target / Shift"))

        res["metrics"].append((" | ".join(mp_parts) or "—", "Avg Manpower"))
        res["metrics"].extend(tg_tiles)
    except Exception:
        res["metrics"].append(("—", "Avg Manpower"))
        res["metrics"].append(("—", "Target"))
    return res
# ===== PRODUCTION FINAL ADD-ON: combined Avg Manpower + combined Target + Rollpack Pcs =====

def _pt_day(res, day):
    if day is None and isinstance(res, dict):
        sub_txt = str(res.get("subtitle", "")) + " " + str(res.get("date", ""))
        m_dt = _re2.search(r"\d{2}-\d{2}-\d{4}|\d{2}-[A-Za-z]{3}-\d{4}", sub_txt)
        if m_dt:
            day = _pd2.to_datetime(m_dt.group(0), dayfirst=True, errors="coerce")
    if day is not None and not _pd2.isna(day):
        return _pd2.Timestamp(day)
    try:
        g = st.session_state.get("global_date")
        if g:
            return _pd2.Timestamp(g)
    except Exception:
        pass
    return _pd2.Timestamp.today()

def _pt_vals(tdf, ym, key):
    """ek shed ke targets -> {unit: value}. Mould me Day/Night ko jod ke Pcs / Kg."""
    out = {}
    d = _pt_find(tdf[tdf["ym"] == ym], key)
    for (u, sub), g in d.groupby(["unit", "sub"], sort=False):
        s = str(sub).upper()
        lab = u or ""
        if not lab and "(KG)" in s:  lab = "Kg"
        if not lab and "(PCS)" in s: lab = "Pcs"
        out[lab] = out.get(lab, 0) + float(g["target"].iloc[0])
    return out

def _pt_fmt(vals):
    return " · ".join(f"{v:,.0f} {u}".strip() for u, v in vals.items() if v) or "—"

def _rollpack_pcs_day(day):
    try:
        pdf, _e, _t = get_sheet("production_logs")
        if pdf is None or pdf.empty:
            return None
        t = PROD_TYPES["rollpack"]
        s = _pcol(pdf, t["col"]).astype(str).str.upper()
        m = s.str.contains("|".join(map(re.escape, t["words"])), na=False)
        d = pdf[m & (_pd2.to_datetime(pdf["_date"]).dt.normalize() == _pd2.Timestamp(day).normalize())]
        return float(_num(_pcol(d, "SHEET")).sum())
    except Exception:
        return None

_prod_add_tiles_prev = _prod_add_tiles   # purana function safe rakha hai

def _prod_add_tiles(res, title, day=None):
    """FINAL: har card me ek hi Avg Manpower (total) + ek hi Target (total). Rollpack me Pcs tile bhi."""
    try:
        day = _pt_day(res, day)
        ym = day.strftime("%Y-%m")
        tdf = prod_target_df()
        if tdf is None or tdf.empty:
            raise ValueError("no target data")
        if ym not in set(tdf["ym"]):
            ym = max(tdf["ym"])
        t_up = str(title or "").strip().upper()
        if t_up == "TOTAL PRODUCTION & YIELD":
            return _prod_add_tiles_prev(res, title, day)      # jaisa tha waisa hi
        blocks = PROD_CARD_MAP.get(t_up)
        if not blocks:
            return _prod_add_tiles_prev(res, title, day)

        # ---- ROLLPACK: Pcs tile ----
        if t_up == "ROLLPACK & YIELD":
            p = _rollpack_pcs_day(day)
            res["metrics"].append((f"{p:,.0f}" if p is not None else "—", "Pcs"))

        # ---- Avg Manpower: sab blocks ka total ----
        tot, found = 0.0, False
        for lab, key, kws in blocks:
            v, _d = _pt_manpower(day, kws)
            if v is not None:
                tot += v; found = True
        res["metrics"].append((f"{tot:,.0f}" if found else "—", "Avg Manpower"))

        # ---- Target: sab blocks ka unit-wise total ----
        vals = {}
        for lab, key, kws in blocks:
            for u, v in _pt_vals(tdf, ym, key).items():
                vals[u] = vals.get(u, 0) + v
        if t_up == "ROLLPACK & YIELD":      # Blocks + Bdls ko jod ke Pcs
            comb = vals.pop("Blocks", 0) + vals.pop("Bdls", 0)
            if comb:
                vals = {"Pcs": comb, **vals}
        res["metrics"].append((_pt_fmt(vals), "Target / Shift"))
    except Exception:
        res["metrics"].append(("—", "Avg Manpower"))
        res["metrics"].append(("—", "Target"))
    return res


def _card(slot, title, value, desc, color, date_text=None, error=False, extra=None,
          metrics=None, sections=None):
    date_html = f'<div class="kpi-date">📅 {date_text}</div>' if date_text else ""
    safe = str(desc).replace('"', "'").replace("<", "&lt;")
    desc_html = (f'<div class="kpi-err" style="color:{color};" title="{safe}">{safe}</div>' if error else
                f'<div class="kpi-desc" style="color:{color};" title="{safe}">{safe}</div>')
    value_html = _tiles_html(metrics) if metrics else f'<div class="kpi-value">{value}</div>'
    extra_html = _sections_html(sections) if sections else (f'<div class="kpi-extra">Σ {extra}</div>' if extra else "")
    # NOTE: HTML mein koi khali line / 4-space indent nahi, warna markdown ise code samajh leta hai
    html = (f'<div class="kpi-wrap"><div class="kpi-title">{title}</div>{date_html}'
            f'{value_html}{desc_html}{extra_html}</div>')
    slot.markdown(html, unsafe_allow_html=True)


def _disabled_date(title, key):
    # alag key (_off): warna purani chuni hui date (jaise kal ki 31/10) is box mein atak jaati hai
    st.date_input(f"{title} date", datetime.datetime.now(IST).date(), key=f"{key}_off",
                label_visibility="collapsed", format="DD/MM/YYYY", disabled=True)
def _fix_sheets_to_pcs(obj):
    """Recursively replace 'Sheets' with 'Pcs' in any string or tuple."""
    if isinstance(obj, str):
        return obj.replace("Sheets", "Pcs").replace("SHEETS", "PCS").replace("sheets", "pcs")
    elif isinstance(obj, tuple):
        return tuple(_fix_sheets_to_pcs(i) for i in obj)
    elif isinstance(obj, list):
        return [_fix_sheets_to_pcs(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _fix_sheets_to_pcs(v) for k, v in obj.items()}
    return obj
KPI_SOURCES[("order", "PPC Wise")] = {
    "sheet": ["order_management_1", "order_management_2"],
    "calc": "order_ppc",
}

_compute_kpi_orig = compute_kpi
def compute_kpi(df, spec, day, *a, **k):
    if spec.get("calc") == "order_ppc":
        return _ppc_wise_card(df, day)
    return _compute_kpi_orig(df, spec, day, *a, **k)
@st.fragment
def render_kpi(dept_key, idx, title, desc):
    """One KPI block, fully independent: own source, own dates, own dropdown, own errors."""
    key = f"{dept_key}_date_{idx}"
    spec = KPI_SOURCES.get((dept_key, title))

    with st.container(border=True):
        slot = st.empty()
        if not spec:
            _disabled_date(title, key)
            _card(slot, title, "Not connected", MISSING_SOURCE.get((dept_key, title), DEFAULT_MISSING),
                GREY, error=True)
            return
        try:
            _card(slot, title, "Loading…", "Fetching data", GREY)
            df, err, fetched = get_sheet(spec["sheet"])
            if df is None:
                _disabled_date(title, key)
                _card(slot, title, "Data unavailable", err, RED, error=True)
                return

            # Main Dates nikalne ka code
            if spec.get("sheet") == "manual" or spec.get("calc") == "min_stock" or str(spec.get("calc", "")).startswith("hr_"):
                dates = [datetime.datetime.now(IST).date()]
            elif spec.get("calc") == "lb_stock":
                dates = [datetime.datetime.now(IST).date()]
            else:
                dates = available_dates(df)
            if spec.get("calc") == "complaints":
                dates = [datetime.datetime.now(IST).date()]
            # HR: dates sirf wo jin din attendance / OT bhara hai (aaj ki date nahi)
            if str(spec.get("calc", "")).startswith("hr_"):
                _hd = _hr_dates(df)
                if _hd:
                    dates = _hd
            if spec.get("calc") in ("hrg_manpower", "hrg_dept"):
                dates = _hr_dates_manpower() or dates
            if spec.get("calc") == "hrg_overtime":
                dates = _hr_dates_overtime() or dates
            if spec.get("calc") == "hrg_staff":
                dates = sorted(set(_hr_dates_manpower()) | {datetime.datetime.now(IST).date()}, reverse=True)

            # ROLLPACK ke liye F-Shed ki dates bhi jodo (taaki Oct month dropdown mein aaye)
            if spec.get("type") == "rollpack":
                _f, _e, _t = get_sheet("f_yield")
                if _f is not None and "_date" in _f.columns:
                    dates = sorted(set(dates) | set(_f["_date"].dropna().unique()), reverse=True)

            # Agar Mattress hai, toh M-Shed ki dates bhi jodo (October ke liye)
            if spec.get("type") == "mattress":
                _m, _e, _t = get_sheet("m_shed")
                if _m is not None:
                    dates = sorted(set(dates) | set(_m["_date"].dropna().unique()), reverse=True)

            # TOTAL PRODUCTION: dates seedhe Prod. Summary sheet se (isme 30-Oct tak ka data hai)
            if spec.get("type") == "total":
                _y, _e, _t = get_sheet("prod_summary")
                if _y is not None and "_date" in _y.columns:
                    dates = sorted(set(_y["_date"].dropna().unique()), reverse=True)
            # TONNAGE FOAMING: monthly dates + daily file ki dates
            if spec.get("calc") == "tonnage_daily":
                _td, _e, _t = get_sheet("foaming_daily")
                if _td is not None:
                    _tt = _td[(_td["chem"] == "GRAND TOTAL") & (_td["kg"] > 0)]
                    dates = sorted(set(dates) | set(_tt["_date"].dropna().unique()), reverse=True)

            # PILLOW: dates sirf wo jin din K shed pillow bana
            if spec.get("calc") == "pillow_sum":
                b = df["BUNDLES"].astype(str).str.strip().str.upper()
                _p = df[b.str.match(r"^\d{2}-K")]
                if not _p.empty:
                    dates = sorted(set(_p["_date"].dropna().unique()), reverse=True)

            # MOULD: dates sirf wo jin din J shed bana
            if spec.get("calc") == "mould_sum":
                b = df["BUNDLES"].astype(str).str.strip().str.upper()
                _p = df[b.str.match(r"^\d{2}-J")]
                if not _p.empty:
                    dates = sorted(set(_p["_date"].dropna().unique()), reverse=True)

            # BONDED: dates sirf wo jin din A shed bana
            if spec.get("calc") == "bonded_sum":
                b = df["BUNDLES"].astype(str).str.strip().str.upper()
                _p = df[b.str.match(r"^\d{2}-A")]
                if not _p.empty:
                    dates = sorted(set(_p["_date"].dropna().unique()), reverse=True)

            # SCRAP: dates sirf wo jin din O shed ka data hai
            if spec.get("calc") == "scrap_sum":
                b = df["BUNDLES"].astype(str).str.strip().str.upper()
                _p = df[b.str.match(r"^\d{2}-O")]
                if not _p.empty:
                    dates = sorted(set(_p["_date"].dropna().unique()), reverse=True)
            # DRS & CRS month-wise: sheet ke har month ki ek date, taaki dropdown mein saare months aayein
            if spec.get("calc") == "finance_dispute":
                dates = _dsp_month_dates(df)
            if spec.get("calc") == "finance_drs_crs_month":
                dates = [datetime.datetime.now(IST).date()]     # <- pehle _drs_crs_bal_month_dates(df) tha
            if spec.get("calc") == "maint_pm":
                dates = _pm_month_dates(df)
            if spec.get("calc") == "finance_recv_days":
                dates = _recv_days_month_dates(df)
            if spec.get("calc") == "finance_total_due_month":
                dates = _due_month_dates(df)
            if spec.get("calc") == "finance_gt90_month":
                dates = _gtm_month_dates(df)
            if spec.get("calc") == "total_received_paid":
                dates = _rp_month_dates(df)


            # FIXED / MANUAL values (Poly Stock, TDI, Pop Polymer): month ya date chunne ki zarurat nahi.
            # Hamesha aaj ki date par value dikhao, taaki purani session ki month/date se "No Data" na aaye.
            if spec.get("sheet") == "manual":
                chosen = dates[0]
                res = compute_kpi(df, spec, chosen)
                _card(slot, title, res["value"], res["desc"] or desc, res["color"] or BLUE,
                      chosen.strftime(DATE_FMT))
                return

            # MATTRESS: dates = H shed production dates + M-Shed yield dates
            if spec.get("calc") == "mattress_sum":
                _h = shed_rows(df, "H")
                _dset = set(_h["_date"].dropna().unique())
                _m, _e, _t = get_sheet("m_yield")
                if _m is not None:
                    _dset |= set(_m["_date"].dropna().unique())
                if _dset:
                    dates = sorted(_dset, reverse=True)

            # --- MONTH dropdown ---
            # --- MONTH dropdown (Local to this card) ---
            all_months = set()
            for d in dates:
                all_months.add((d.year, d.month))
            current_year = datetime.datetime.now(IST).year
            for m in range(1, 13):
                all_months.add((current_year, m))
                all_months.add((current_year - 1, m))

            months_with_data = sorted({(d.year, d.month) for d in dates}, reverse=True)
            other_months = sorted([m for m in all_months if m not in months_with_data], reverse=True)
            months = months_with_data + other_months

            # Local dropdown
            mcol, dcol = st.columns([1, 1], gap="small")
            
            # Set default local month to Global Month if it exists in this card's data
            default_m_idx = 0
            if st.session_state.get("global_month") in months:
                default_m_idx = months.index(st.session_state.global_month)

            chosen_m = mcol.selectbox(
                f"{title} month", months, index=default_m_idx, key=f"{key}_m", label_visibility="collapsed",
                format_func=lambda m: datetime.date(m[0], m[1], 1).strftime("%b-%y"),
            )

            month_dates = [d for d in dates if (d.year, d.month) == chosen_m]
            if not month_dates and spec.get("calc") == "complaints":
                _ms, _me = _month_range(datetime.date(chosen_m[0], chosen_m[1], 1))
                month_dates = [min(_me, datetime.datetime.now(IST).date())]
            
            if not month_dates and (spec.get("calc") in ("lb_stock", "dead_stock", "inv_dead_stock") or spec.get("sheet") == "dead_stock_store"):
                month_dates = [datetime.datetime.now(IST).date()]
                
            if not month_dates:
                _disabled_date(title, key)
                _card(slot, title, "No Data Available for This Month", desc, GREY, datetime.date(chosen_m[0], chosen_m[1], 1).strftime("%b-%Y"))
                return

            # --- PILLOW / FINANCE / FOAMING / SALES / MIN_STOCK: sirf month, date hidden ---
            is_pillow = (spec.get("calc") == "prod_log" and spec.get("type") == "pillow")
            is_finance = str(spec.get("calc", "")).startswith("finance_")
            is_foaming = str(spec.get("calc", "")).startswith("sum_consumption")
            is_min_stock = (spec.get("calc") == "min_stock")
            is_note = spec.get("calc") in ("credit_note", "debit_note")

            # Yahan is_min_stock add karna zaroori tha
            hide_date = is_pillow or is_finance or is_foaming or is_min_stock or is_note or (spec.get("calc", "").startswith("sales_") and not spec.get("show_date"))
            if spec.get("calc") == "complaints":
                hide_date = True

            if hide_date:
                chosen = month_dates[0]
                date_label = f"Full Month ({chosen.strftime('%b-%Y')})" if is_pillow or is_note or spec.get("calc", "").startswith("sales_") else "As on date"
            else:
                # Set default local date to Global Date if it exists in this card's dates
                default_d_idx = 0
                if st.session_state.get("global_date") in month_dates:
                    default_d_idx = month_dates.index(st.session_state.global_date)

                chosen = dcol.selectbox(
                    f"{title} date", month_dates, index=default_d_idx, key=f"{key}_{chosen_m[0]}_{chosen_m[1]}_v2",
                    label_visibility="collapsed",
                    format_func=lambda d: d.strftime("%d-%m-%y"),
                )
                date_label = chosen.strftime(DATE_FMT)

            st.session_state[key] = chosen
            prefix = spec.get("date_label", "as of" if spec.get("mode") == "as_of" else "")
            label = f"{prefix} {date_label}".strip()

            try:
                res = compute_kpi(df, spec, chosen)
            except Exception as exc:
                log.exception("KPI %s/%s failed", dept_key, title)
                _card(slot, title, "Config error", f"{type(exc).__name__}: {exc}", RED, label, error=True)
                return
            if res is not None and dept_key == "production":
                res = _prod_add_tiles(res, title, chosen)

            if res is not None and res.get("details"):
                with st.expander("📋 View Full Details"):
                    st.markdown(_sections_html(res["details"]), unsafe_allow_html=True)
            if res is not None and res.get("drill"):
                for _lbl, _rows in res["drill"]:
                    with st.expander(_lbl):
                        st.markdown(_sections_html([(res.get("drill_heading", "Material-wise balance"), _rows)]), unsafe_allow_html=True)

            if res is None:
                _card(slot, title, "No Data Available for This Date", desc, GREY, chosen.strftime(DATE_FMT))
            elif err:
                _card(slot, title, _fix_sheets_to_pcs(res["value"]), f"⚠ Stale: last updated {fetched:%d-%m %H:%M}", AMBER, label,
                      extra=_fix_sheets_to_pcs(res.get("extra")), metrics=_fix_sheets_to_pcs(res.get("metrics")), sections=_fix_sheets_to_pcs(res.get("sections")))
            else:
                _card(slot, title, _fix_sheets_to_pcs(res["value"]), _fix_sheets_to_pcs(res["desc"] or desc), res["color"] or BLUE, label,
                      extra=_fix_sheets_to_pcs(res.get("extra")), metrics=_fix_sheets_to_pcs(res.get("metrics")), sections=_fix_sheets_to_pcs(res.get("sections")))
        except Exception as exc:                  # never let one block break the others
            log.exception("KPI %s/%s crashed", dept_key, title)
            _card(slot, title, "Error", f"{type(exc).__name__}: {exc}", RED, error=True)


def render_department_button(dept):
    st.markdown(f'<span class="dept-{dept["key"]}"></span>', unsafe_allow_html=True)
    label = f"{dept['icon']} {dept['name']}"
    with st.popover(label, use_container_width=True):
        st.caption("Open detailed dashboard / sheet")
        for i, (link_label, url) in enumerate(dept["links"]):
            if url:
                st.link_button(link_label, url, use_container_width=True)
            else:
                st.button(
                    f"⚠ Link missing – {link_label}",
                    key=f"missing_{dept['key']}_{i}",
                    disabled=True,
                    use_container_width=True,
                )
# ====================================================================
# ONLINE BUSINESS (sirf monthly, manual data)
# Har mahine ka naya data neeche ek nayi (saal, mahina) entry bana kar daalo
# ====================================================================
ONLINE_EXPENSES = {
    (2026, 10): {
        "main": [
            ("Amazon Seller", "Platform", 603273),
            ("Blinkit Commerce", "Platform", 48704),
            ("Blue Dart", "Logistics", 34685),
            ("Easebuzz", "Platform Cost", 10063),
            ("Evitamin", "Agency Charges", 160417),
            ("Facebook", "Ad Cost", 79732),
            ("Flipkart", "Platform Cost", 6644981),   # kagaz ka number check karein
        ],
        "other": [
            ("Gokwik", "Platform", 7997),
            ("Delivery / PR Exit", "Logistics", 332000),      # 3.32 lakh
            ("Designer + Mukul", "Agency Charges", 65000),    # 0.65 lakh
        ],
    },
    # Agle mahine ke liye aise hi add karo:
    # (2026, 11): {"main": [("Amazon Seller", "Platform", 0)], "other": []},
}


def render_online_business(dept):
    """Online Business: sirf month dropdown, total + category-wise + platform-wise."""
    with st.container(border=True):
        render_department_button(dept)
        months = sorted(ONLINE_EXPENSES.keys(), reverse=True)
        chosen = st.selectbox(
            "Online Business month", months, key="online_month",
            label_visibility="collapsed",
            format_func=lambda m: datetime.date(m[0], m[1], 1).strftime("%b-%y"),
        )
        data = ONLINE_EXPENSES[chosen]
        main, other = data.get("main", []), data.get("other", [])
        main_total = sum(a for _, _, a in main)
        other_total = sum(a for _, _, a in other)
        grand = main_total + other_total

        by_cat = {}
        for _, cat, amt in main + other:
            by_cat[cat] = by_cat.get(cat, 0) + amt
        by_cat = dict(sorted(by_cat.items(), key=lambda x: x[1], reverse=True))

        metrics = [
            (_inr(grand), "Total Expense"),
            (_inr(main_total), "Main Platforms"),
            (_inr(other_total), "Others"),
        ]
        label = datetime.date(chosen[0], chosen[1], 1).strftime("%b-%Y")
        st.markdown(
            f'<div class="kpi-wrap"><div class="kpi-title">Online Business Expenses</div>'
            f'<div class="kpi-date">📅 {label}</div>{_tiles_html(metrics)}'
            f'<div class="kpi-desc" style="color:{BLUE};">Monthly expense: platform, logistics, ads & agency</div></div>',
            unsafe_allow_html=True,
        )
        with st.expander("📋 View Full Details"):
            sections = [
                ("📂 Category wise", [(k, _inr(v)) for k, v in by_cat.items()]),
                ("🏪 Platform wise", [(f"{n} ({c})", _inr(a)) for n, c, a in main]
                                     + [("TOTAL (main)", _inr(main_total))]),
                ("➕ Other expenses", [(f"{n} ({c})", _inr(a)) for n, c, a in other]
                                      + [("TOTAL (others)", _inr(other_total))]),
                ("🧮 Grand Total", [("Combined", _inr(grand))]),
            ]
            st.markdown(_sections_html(sections), unsafe_allow_html=True)


def render_department(dept):
    if dept["key"] == "online":
        render_online_business(dept)
        return
    with st.container(border=True):
        render_department_button(dept)
        kpis = dept["kpis"]
        
        # PRODUCTION ke liye 4 cards ek line mein, baaki sabke liye 3
        per_row = 4 if dept["key"] == "production" else KPI_PER_ROW
        
        for start in range(0, len(kpis), per_row):
            # Yahan gap="small" kiya hai taaki 4 cards mein space bache
            cols = st.columns(per_row, gap="small", vertical_alignment="top")
            for offset, (title, desc) in enumerate(kpis[start:start + per_row]):
                with cols[offset]:
                    with st.container():
                        render_kpi(dept["key"], start + offset, title, desc)


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def discover_tabs(pub_url):
    """List the tabs (name, gid) of a 'Publish to web' spreadsheet."""
    html = _http_get(pub_url.split("/pub")[0] + "/pubhtml").decode("utf-8", errors="replace")
    tabs, seen = [], set()
    for m in re.finditer(r'name:\s*"([^"]+)"[^}]*?gid:\s*"(\d+)"', html):
        if m.group(2) not in seen:
            seen.add(m.group(2))
            tabs.append((m.group(1).encode().decode("unicode_escape", errors="ignore"), m.group(2)))
    if not tabs:
        for g in dict.fromkeys(re.findall(r"gid=(\d+)", html)):
            tabs.append((f"tab gid {g}", g))
    return tabs or [("first tab", "0")]


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def peek_tab(pub_url, gid, n=8):
    data = _http_get(pub_url.split("/pub")[0] + f"/pub?output=csv&gid={gid}")
    if data.lstrip()[:1] == b"<":
        raise PermissionError("tab is not published as data")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
    return rows[:n], len(rows)


def render_explorer():
    """Shows every tab, its gid and first rows - to pick the right columns."""
    with st.expander("🔎 Sheet explorer: all tabs, gids and column headers"):
        for name, cfg in SHEETS.items():
            if not str(cfg["url"]).startswith("http"):
                continue
            st.markdown(f"**Workbook `{name}`**")
            try:
                tabs = discover_tabs(cfg["url"])
            except Exception as exc:
                st.error(f"Could not list tabs: {type(exc).__name__}: {exc}")
                continue
            for tab_name, gid in tabs:
                try:
                    rows, total = peek_tab(cfg["url"], gid)
                except Exception as exc:
                    st.warning(f"Tab '{tab_name}' (gid {gid}): {type(exc).__name__}: {exc}")
                    continue
                st.write(f"Tab **{tab_name}** · gid **{gid}** · {total} rows")
                width = max((len(r) for r in rows), default=0)
                st.dataframe(pd.DataFrame([r + [""] * (width - len(r)) for r in rows]),
                            use_container_width=True, hide_index=True)


def render_diagnostics():
    with st.expander("🛠 Diagnostics (sources, columns, KPI validation)"):
        for name in sorted({n for s in KPI_SOURCES.values() if s.get("sheet")
                            for n in (s["sheet"] if isinstance(s["sheet"], (list, tuple)) else [s["sheet"]])}):
            df, err, fetched = get_sheet(name)
            st.markdown(f"**Sheet `{name}`**")
            if df is None:
                st.error(err)
                continue
            if "_date" not in df.columns:
                st.write(f"{len(df)} rows (matrix sheet, no date column to check)")
                continue
            st.write(
                f"{len(df)} rows · dates {df['_date'].min():{DATE_FMT}} to {df['_date'].max():{DATE_FMT}} "
                f"· fetched {fetched:%d-%m-%Y %H:%M:%S} IST · "
                f"{df.attrs.get('bad_dates', 0)} rows skipped for unreadable date"
            )
            st.write("**Exact column headers found:**", [c for c in df.columns if not str(c).startswith("_")])
            if err:
                st.warning(f"Last refresh failed, showing older data: {err}")

        st.markdown("**Power BI**")
        st.info(POWERBI_NOTE)

        for dept in DEPARTMENTS:
            for idx, (title, _d) in enumerate(dept["kpis"]):
                spec = KPI_SOURCES.get((dept["key"], title))
                if not spec or not spec.get("calc"):
                    continue
                df = get_sheet(spec["sheet"])[0]
                day = st.session_state.get(f"{dept['key']}_date_{idx}")
                if df is None or day is None:
                    continue
                st.markdown(f"**{title} - validation for {day:{DATE_FMT}}** (date chosen in that block)")
                try:
                    if spec["calc"] == "po_pending":
                        r = po_pending(df, day, spec.get("columns"))
                        if r is None:
                            st.write("No POs on or before this date.")
                            continue
                        st.caption(r["formula"])
                        st.write("Columns used:", r["columns"])
                        st.write(f"**{r['open_pos']} open POs / {r['open_lines']} open lines.** "
                                f"Outstanding qty: {r['qty_by_uom']}")
                        rec = r["recon"]
                        ok = rec["checked"] - len(rec["mismatch"])
                        st.write(f"Cross-check against the sheet's own Balance Qty: {ok} of {rec['checked']} lines agree.")
                        if len(rec["mismatch"]):
                            st.warning("Lines where PO Qty - sum(Inv Qty) differs from the sheet's Balance Qty by more than 1:")
                            st.dataframe(rec["mismatch"], use_container_width=True)
                        for i in r["issues"]:
                            st.warning(i)
                        st.dataframe(r["table"], use_container_width=True)
                    elif spec["calc"] == "purchase_mtd":
                        r = purchase_mtd(df, day, spec.get("columns"), spec.get("basis", "received"))
                        if r is None:
                            st.write("No purchase rows in this month up to the selected date.")
                            continue
                        st.caption(r["formula"])
                        st.write(f"Total: **{_inr(r['value'])}** from {len(r['table'])} rows")
                        if r["warn_items"]:
                            st.warning("These items have rates that differ more than "
                                    f"{MIXED_RATE_RATIO}x elsewhere in the sheet (mixed currencies?): {r['warn_items']}")
                        for i in r["issues"]:
                            st.warning(i)
                        st.dataframe(r["table"], use_container_width=True)
                except Exception as exc:
                    st.error(f"{type(exc).__name__}: {exc}")


# ====================================================================
# 10. MAIN LAYOUT (original: two departments per row, auto-refresh fragment)
# ====================================================================
# 1. Yahan @st.fragment lagayein
def dashboard_body():
    st.session_state["_errors"] = {}

    status_col, button_col = st.columns([6, 1])
    status_slot = status_col.empty()
    if button_col.button("🔄 Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    for i in range(0, len(DEPARTMENTS), 2):
        left, right = st.columns(2)
        with left:
            render_department(DEPARTMENTS[i])
        with right:
            if i + 1 < len(DEPARTMENTS):
                render_department(DEPARTMENTS[i + 1])

    now = datetime.datetime.now(IST)
    total = sum(len(d["kpis"]) for d in DEPARTMENTS)
    connected = sum(1 for d in DEPARTMENTS for k in d["kpis"] if (d["key"], k[0]) in KPI_SOURCES)
    errors = st.session_state.get("_errors", {})
    fetched_times = [t for _, t in st.session_state.get("_last_good", {}).values()]
    last_data = max(fetched_times).strftime("%d-%m-%Y %H:%M:%S") if fetched_times else "never"
    with status_slot.container():
        st.caption(
            f"Data last fetched: **{last_data}** (IST) · page checked {now:%H:%M:%S} · "
            f"auto-refresh every {REFRESH_SECONDS // 60} min · "
            f"{connected} of {total} KPIs mapped to a data source"
        )
        for name, msg in errors.items():
            st.error(f"Could not refresh '{name}': {msg}. Showing last good data if any.")

    render_diagnostics()
    render_explorer()

    missing = [f"{d['name']}: {label}" for d in DEPARTMENTS for label, url in d["links"] if not url]
    if missing:
        with st.expander(f"⚠ {len(missing)} department links still to be added"):
            for m in missing:
                st.write(f"- {m}")

# 2. Yahan se @st.fragment hata dein
dashboard_body()

st.markdown(
    '<div class="corp-footer">© Jindal Petrofoam Private Limited • Enterprise Master Dashboard • Data auto-refreshes every 5 minutes</div>',
    unsafe_allow_html=True,
)
