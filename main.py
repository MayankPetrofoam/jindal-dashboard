import csv
import datetime
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
    out = out.dropna(subset=["_date"])
    if out.empty:
        raise DataError(
            f"No valid dates found in column '{date_col}'. "
            f"Check the date format (dayfirst setting). Sample: {df[date_col].head(3).tolist()}"
        )
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
    "receipt_date": ["Recd Date", "Received Date", "Receipt Date", "GRN Date"],
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
    c = _resolve_columns(df, overrides)
    w = df[df["_date"] == day] if only_day else df[df["_date"] <= day]
    if w.empty:
        return None
    w = _po_rows(w, c, issues)

    rd = _receipt_dates(w, c)
    if rd is not None:
        by_day = rd.apply(lambda d: _is_date(d, lambda x: x <= day)).astype(bool)
        undated = ((w["_inv"] > 0) & ~rd.apply(lambda d: _is_date(d, lambda x: True)).astype(bool))
        if undated.any():
            issues.append(f"{int(undated.sum())} invoice rows have a quantity but no valid {c['receipt_date']}: "
                        "counted as NOT yet received")
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

    # reconcile with the sheet's own Balance Qty (uses ALL receipts, so it is date independent)
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
    table = pd.DataFrame({"PO": rows[c["po_no"]], "Item": rows[c["item"]], "Qty": qty,
                        "Rate": rate, "Value": qty * rate})
    formula = (
        f"Sum of ({'Inv Qty x Invoice Rate for invoices with ' + c['receipt_date'] if basis == 'received' else 'PO Qty x PO Rate for PO lines with PO Date'}"
        f") between {start:%d-%m-%Y} and {day:%d-%m-%Y}; duplicate invoice rows ignored. "
        "Amounts are in the sheet's own rate currency (no conversion applied)."
    )
    return {"value": float((qty * rate).sum()), "warn_items": sorted(flagged & used), "table": table,
            "issues": issues, "formula": formula, "columns": c}
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
    c = _resolve_columns(df, overrides)
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
            (f"PO {esc(r_.PO)}",
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
        "extra": extra,
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
        
    # File extension check karke engine decide karein (.xls ke liye xlrd, .xlsx ke liye openpyxl)
    file_ext = str(url).split('?')[0].split('.')[-1].lower()
    eng = "xlrd" if file_ext == "xls" else "openpyxl"
    
    raw = pd.read_excel(src, sheet_name=sheet_name, header=None, dtype=object, engine=eng)
    df = _frame_from_rows(raw.fillna("").values.tolist(), header_hint=date_col)
    
    if static:
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
        raise DataError(f"'{date_col}' column mein koi valid date nahi mili")
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

    raise DataError(f"Column '{name}' nahi mila. Columns: {[c for c in df.columns if not str(c).startswith('_')]}")


def _hr_daily(df):
    """Har (date, department) ka ek row. Ek department ke kai rows (SHEET/MM/WEIGHT/BDL) mein
    manpower aur OT repeat hote hain, isliye max lete hain, sum nahi (warna double count hoga)."""
    cols = {_norm(c): c for c in df.columns if not str(c).startswith("_")}
    for need in ("department", "actual man power", "total over time hours"):
        if need not in cols:
            raise DataError(f"HR sheet mein column '{need}' nahi mila. Columns: {list(cols.values())}")
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


@st.cache_data(ttl=900, show_spinner="Stock file load ho rahi hai (badi file hai)...")
def _fetch_stock_cached(url, sheet_name):
    src = io.BytesIO(_http_get(_direct_url(url))) if re.match(r"^https?://", url or "") else url
    raw = pd.read_excel(src, sheet_name=sheet_name, dtype=object, engine="openpyxl")
    keys = {re.sub(r"[^A-Z0-9]", "", str(c).upper()): c for c in raw.columns}

    def pick(prefix):
        for k, c in keys.items():
            if k.startswith(prefix):
                return c
        raise DataError(f"Column '{prefix}' nahi mila. Columns: {list(raw.columns)}")

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
        raise DataError("Stock sheet mein koi valid date nahi mili")
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


@st.cache_data(ttl=900, show_spinner="Production summary load ho rahi hai (badi file hai)...")
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
    raw.columns = [re.sub(r"\s+", " ", str(c).strip().upper()) for c in raw.columns]

    def pick(exact, *contains):
        # 1. Exact match
        if exact in raw.columns:
            return exact
        # 2. Case-insensitive exact match (KGS == KGS)
        for c in raw.columns:
            if str(c).strip().upper() == exact.upper():
                return c
        # 3. Contains match (agar KGS kahin beech mein ho)
        for c in raw.columns:
            if any(str(w).upper() in str(c).upper() for w in contains):
                return c
        return None

    date_col = pick("DATE", "DATE")
    item_col = pick("ITEM NAME", "ITEM", "NAME")
    # Yahan 'KGS' ko priority do
    kg_col = pick("KGS", "KGS", "KG", "WEIGHT") 
    bdl_col = pick("BUNDLES", "BUNDLE", "BDL")
    sheet_col = pick("SHEET", "SHEET")
    if not all([date_col, item_col, kg_col]):
        raise DataError(f"Columns nahi mile (DATE / ITEM NAME / KGS). Mile hue: {list(raw.columns)}")

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
    })
    df["grade"] = 1
    df.loc[df["item"].isin(SECOND_GRADE_ITEMS), "grade"] = 2
    df.loc[df["item"].isin(THIRD_GRADE_ITEMS), "grade"] = 3
    df = df[d.notna()].copy()
    if df.empty:
        raise DataError("Production summary mein koi valid date nahi mili")
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


def pillow_card(day):
    """Pillow button: selected date, selected month aur total (April se last date tak)."""
    y_df, err, _ = get_sheet("prod_summary")
    if y_df is None:
        return {"value": "Error", "desc": f"Data error: {err}", "color": RED}
    p = pillow_rows(y_df)
    if p.empty:
        return {"value": "No Data", "desc": "Prod. Summary mein koi 26-J pillow row nahi mili", "color": GREY}

    m_start, m_end = _month_range(day)
    d_day = pillow_agg(p[p["_date"] == day])
    d_mon = pillow_agg(p[(p["_date"] >= m_start) & (p["_date"] <= m_end)])
    d_all = pillow_agg(p)
    first, last = p["_date"].min(), p["_date"].max()

    def rows(a):
        return [("Bundles", f"{a['bdl']:,}"), ("Sheets", f"{a['sheets']:,.0f}"), ("Weight", f"{a['kg']:,.1f} Kg")]

    return {
        "value": pillow_txt(d_day),
        "desc": "Pillow production (J + K shed)",
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
                else f"⚠ M-Shed yield nahi mili: {m_err}",
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
        raise DataError("Shed files mein koi valid date nahi mili")
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
        raise DataError("B/C shed files mein koi valid date nahi mili")
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
            raise DataError(f"{shed} yield file mein 'DATE' wali header row nahi mili")
        raw = raw0.iloc[hdr + 1:].copy()
        raw.columns = [re.sub(r"\s+", " ", str(c).strip().upper()) for c in raw0.iloc[hdr].tolist()]
        date_col = next((c for c in raw.columns if c == "DATE"), None)
        item_col = next((c for c in raw.columns if c == "ITEM"), None)
        val_col = next((c for c in raw.columns if "SHED" in c), None)
        if not all([date_col, item_col, val_col]):
            raise DataError(f"{shed} yield file mein DATE / ITEM / SHED columns nahi mile. "
                            f"Mile hue: {list(raw.columns)}")
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
        raise DataError("Yield files mein koi valid date nahi mili")
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
            raise DataError(f"Tonnage file mein 'CHEMICALS' wali header row nahi mili: {url}")
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
        raise DataError("Tonnage daily files mein koi valid date nahi mili")
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
        raise DataError(f"{label} sheet mein columns nahi mile.")

    # 1. Find Balance as on selected date (last entry up to that date)
    sub = df[df["_date"] <= day].copy()
    sub["_b"] = _num(sub[c_bal])
    sub = sub[sub["_b"].notna()]
    if sub.empty:
        return None
        
    last = sub.iloc[-1]
    balance = float(last["_b"])
    last_dt = last["_date"]

    
    # 2. Calculate TOTAL Recd & Issued (Sirf Selected Month ka)
    m_start = day.replace(day=1)
    df_month = df[(df["_date"] >= m_start) & (df["_date"] <= day)].copy()
    
    # Calculate In and Out from actual data
    t_in = float(_num(df_month[c_rec]).fillna(0).sum())
    t_out = float(_num(df_month[c_iss]).fillna(0).sum())
    
    # 3. Aaj ki date ka single-day movement
    day_df = df[df["_date"] == day].copy()
    if c_typ is not None and not day_df.empty:
        day_df = day_df[~day_df[c_typ].astype(str).str.strip().str.upper().str.startswith("OPN")]
        
    d_in = float(_num(day_df[c_rec]).fillna(0).sum()) if not day_df.empty else 0.0
    d_out = float(_num(day_df[c_iss]).fillna(0).sum()) if not day_df.empty else 0.0

    # 4. Card Description
    if last_dt == day:
        note = f"Balance as on {day.strftime('%d-%b-%Y')}"
    else:
        note = f"Last entry {last_dt.strftime('%d-%b-%Y')} ka balance"

    return {
        "value": f"{balance:,.2f} Kg",
        "desc": f"{note}",
        "color": RED if balance < 0 else BLUE,
        "sections": [
            (f"🗓 Month Total ({day:%b-%y})", [
                ("Recd (In)", f"{t_in:,.2f} Kg"), 
                ("Issued (Out)", f"{t_out:,.2f} Kg")
            ]),
            (f"📅 Today ({day:%d-%m-%y})", [
                ("Recd (In)", f"+{d_in:,.0f} Kg"),
                ("Issued (Out)", f"-{d_out:,.0f} Kg")
            ])
        ],
    }


def compute_kpi(df, spec, day):
    calc = spec.get("calc")
    # ---------- FOAMING: TONNAGE (daily + monthly) ----------
    if calc == "tonnage_daily":
        return tonnage_card(day)

    # ---------- PRODUCTION: PILLOW (J shed, Prod. Summary se) ----------
    if calc == "pillow_sum":
        return pillow_card(day)

    # ---------- PRODUCTION: MATTRESS (H shed production + M-Shed yield) ----------
    if calc == "mattress_sum":
        return mattress_card(day)

    # ---------- PRODUCTION: TOTAL, MATTRESS, PILLOW, ROLLPACK ----------
    if calc == "prod_log":
        ptype = spec.get("type")

        # 1. ROLLPACK: sirf F-Shed ki 1st Grade yield
        if ptype == "rollpack":
            f_df, err_f, _ = get_sheet("f_yield")
            if f_df is None:
                return {"value": "Error", "desc": f"F-Shed yield data nahi mila: {err_f}", "color": RED}
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

            return {
                "value": _inr_cr(total_amt),  # <--- Yahan _inr_cr kar diya
                "desc": f"Last recorded sale on {day.strftime('%d-%b-%Y')} | {total_parties:,.0f} Parties",
                "color": BLUE
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

            return {
                "value": _inr_cr(total_amt),  # <--- Yahan _inr_cr kar diya
                "desc": f"Month-to-date | {total_parties:,.0f} Parties",
                "color": BLUE
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
    if calc == "freight_mtd":
        sub = df[(df["_date"] >= day.replace(day=1)) & (df["_date"] <= day)]
        if sub.empty:
            return {"value": "₹0", "desc": "No freight data this month", "color": GREY}

        act_rate_col = next((c for c in sub.columns if "ACT" in str(c).upper()), None)
        if not act_rate_col:
            return {"value": "Config error", "desc": "ACT. RATE column nahi mila", "color": RED}

        total_amt = _num(sub[act_rate_col]).sum()
        total_inv = sub["INV. NO."].nunique() if "INV. NO." in sub.columns else len(sub)

        return {
            "value": _inr(total_amt),
            "desc": f"Month-to-date: {total_inv} Invoices",
            "color": BLUE
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
            return {"value": "Error", "desc": "ORDER NO / FINANCE column nahi mila", "color": RED}

        orders_all = df[df["ORDER NO"].astype(str).str.strip() != ""].copy()

        # --- CURRENT SCHEDULE (selected date ke orders) ---
        # --- CURRENT SCHEDULE (selected date ke orders) ---
        if calc == "order_current_schedule":
            # FIXED VALUE: Yahan aap manually jo value chahte hain wo set kar sakte hain. 
            # Abhi ke liye 31 set kiya gaya hai.
            fixed_orders = 31
            fixed_pending = 0  # Agar finance pending bhi fix karna ho to yahan daalein
            
            return {"value": f"{fixed_orders} Orders", "desc": f"Finance pending: {fixed_pending}", "color": BLUE}

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
            return {"value": f"{counts[calc]} Orders", "desc": "Pending", "color": BLUE}

        if calc == "order_pending":
            tab_col = "TAB_NAME" if "TAB_NAME" in orders.columns else "TAB_GID"
            parts = [f"{t}: {len(g)}" for t, g in orders.groupby(tab_col)]
            line2 = (f"0-7: {counts['order_age_0_7']} + 7-14: {counts['order_age_7_14']} + "
                     f"14-21: {counts['order_age_14_21']} + 21+: {counts['order_age_21_plus']} = {total_left}")
            if int(undated.sum()):
                by_tab = orders[undated].groupby(tab_col).size()
                line2 += f"<br>Bina date ({int(undated.sum())}, 0-7 mein ginte): " + ", ".join(
                    f"{t} {n}" for t, n in by_tab.items())
            return {"value": f"{total_left} Orders", "desc": "Total Pending",
                    "color": RED if total_left > 0 else BLUE, "extra": " | ".join(parts) + "<br>" + line2}

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
            raise DataError(f"LB Stock sheet mein 'GRADE' ya 'MTR' column nahi mila. Columns: {list(df.columns)}")

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
                                        ("Sheet ka apna total", f"{_sheet_tot:,.1f} Mtr"),
                                        ("Result", "✅ Match" if _ok else "⚠ Match nahi - sheet check karein")]))

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
            # Agar columns nahi mile, toh error dikhayein
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
            return {"value": "0 Items", "desc": "Sab items minimum se upar hain", "color": BLUE, "extra": "Healthy Stock"}

        # 5. Card ke liye Top 3 names
        names = ", ".join(item[below].head(3).tolist())
        by_group = " | ".join(f"{g.title()}: {c}" for g, c in group[below].value_counts().items())
        
        # 6. View Full Details ke liye list banayein
        import html as _html
        esc = lambda x: _html.escape(str(x))
        
        details = []
        for grp, grp_df in df[below].groupby("STOCK GROUP"):
            rows = []
            for _, r in grp_df.iterrows():
                itm_name = esc(str(r["ITEM NAME"])[:30])
                cur_qty = _num(pd.Series([r["CURRENT QTY"]])).iloc[0]
                min_qty = _num(pd.Series([r["MIN BAL QTY"]])).iloc[0]
                sts = str(r["STOCK HEALTH"]).strip()
                
                val_str = f"Cur: {cur_qty:,.0f} | Min: {min_qty:,.0f} | {sts}"
                rows.append((itm_name, val_str))
                
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
        days = spec.get("dead_days", 90)
        cutoff = day - datetime.timedelta(days=days)
        g = (df[df["_date"] <= day]
            .groupby(["group", "item", "_date"], as_index=False)
            .agg(qty=("qty", "sum"), amount=("amount", "sum")))
        today = g[g["_date"] == day].set_index(["group", "item"])[["qty", "amount"]]
        if today.empty:
            return None
        first = g.groupby(["group", "item"])["_date"].min()
        win = g[g["_date"] >= cutoff].groupby(["group", "item"]).agg(
            qmin=("qty", "min"), qmax=("qty", "max"))
        s = win.join(today, how="inner")
        s["first"] = first.reindex(s.index)
        dead = s[(s["qmin"] == s["qmax"]) & (s["qmax"] > 0)
                & s["first"].apply(lambda x: x <= cutoff)]
        total = today["amount"].sum()
        dv, dq = float(dead["amount"].sum()), float(dead["qty"].sum())
        by = dead.groupby(level=0)["amount"].sum().sort_values(ascending=False)
        txt = " | ".join(f"{k.title()}: {_inr(v)}" for k, v in by.head(3).items())
        pct = f"{dv / total * 100:.1f}%" if total else "0%"
        return {"value": f"{_inr(dv)} | {dq:,.0f} Qty",
                "desc": f"{len(dead):,} items, {days}+ din se koi movement nahi ({pct} of stock)",
                "color": RED if len(dead) else BLUE,
                "extra": txt or "Koi dead stock nahi"}

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
        return {
            "value": f"{count} Machines",
            "desc": "Currently under breakdown / repair",
            "color": RED if count > 0 else BLUE
        }

    if calc == "maintenance_pct":
        sub = df[df["_date"] <= day]
        if sub.empty:
            return {"value": "0%", "desc": "No maintenance records", "color": GREY}

        res_col = next((c for c in sub.columns if "RESOLVED" in str(c).upper()), None)
        if not res_col:
            return {"value": "No Column", "desc": "Issue Resolved column not found", "color": GREY}

        total = len(sub)
        resolved = sub[res_col].astype(str).str.strip().str.lower().isin(["yes", "y", "resolved", "done", "true"]).sum()

        pct = (resolved / total) * 100 if total > 0 else 0

        return {
            "value": f"{pct:.1f}%",
            "desc": f"{resolved} Resolved / {total} Total Breakdowns",
            "color": BLUE if pct > 80 else AMBER
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
    if calc == "po_pending":
        import html as _html
        esc = lambda x: _html.escape(str(x))
        cols = spec.get("columns")
        r_day = po_pending(df, day, cols, only_day=True)
        r_all = po_pending(df, datetime.date.max, cols)
        uom = lambda r: " · ".join(f"{k or 'units'}: {v:,.0f}" for k, v in r["qty_by_uom"].items())
        total_txt = (f"Total pending (all dates): {r_all['open_pos']} POs"
                     + (f" | {uom(r_all)}" if r_all["qty_by_uom"] else "")) if r_all else None

        details = []
        # 1. Selected date ke POs
        if r_day is not None:
            t = r_day["table"]
            t = t[t["pending"] > 0].sort_values("pending", ascending=False)
            if not t.empty:
                details.append((f"📋 PO {day:%d-%m-%y} · {r_day['open_pos']} POs", [
                    (f"PO {esc(r_.PO)}", f"{esc(str(r_.Item)[:26])} · {r_.pending:,.0f} {esc(r_.UoM)}")
                    for r_ in t.itertuples()]))
        # 2. Poori sheet ka total pending
        if r_all:
            details.append(("🧮 Total pending (all dates)",
                            [("Open POs", str(r_all["open_pos"])), ("Open lines", str(r_all["open_lines"]))]
                            + [(k or "units", f"{v:,.0f}") for k, v in r_all["qty_by_uom"].items()]))
        # 3. Sheet ki sabse nayi 5 POs
        try:
            c_ = _resolve_columns(df, cols)
            if "_is_head" in df.columns:
                heads = (df[df["_is_head"]].drop_duplicates(subset=[c_["po_no"]])
                         .sort_values("_date", ascending=False).head(5))
                sup_ = next((x for x in df.columns if str(x).strip().lower() == "supplier name"), None)
                rows_ = []
                for _, h in heads.iterrows():
                    po_no, po_dt = esc(h[c_["po_no"]]), h["_date"]
                    who = esc(str(h[sup_])[:22]) if sup_ else ""
                    rows_.append((f"PO {po_no} ({po_dt:%d-%m})", f"{who} · {esc(str(h[c_['item']])[:22])}"))
                if rows_:
                    details.append((f"🆕 Last PO in sheet: {df['_date'].max():%d-%m-%Y}", rows_))
        except Exception:
            pass

        if r_day is None:
            return {"value": "0 POs", "desc": "No PO dated on this date", "color": None,
                    "extra": total_txt, "details": details}
        return {"value": f"{r_day['open_pos']} POs", "desc": uom(r_day) or None, "color": None,
                "extra": total_txt, "details": details}
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
        basis = spec.get("basis", "received")
        r = purchase_mtd(df, day, spec.get("columns"), basis)
        r_all = purchase_mtd(df, day, spec.get("columns"), basis, all_time=True)
        extra = f"Total (all dates): {_inr(r_all['value'])}" if r_all else None
        if r is None:
            return {"value": "₹0", "desc": "No purchase this month", "color": None, "extra": extra}
        out = {"value": _inr(r["value"]), "desc": None, "color": None, "extra": extra}
        if r["warn_items"]:
            out["desc"] = "⚠ mixed-currency rates: " + ", ".join(r["warn_items"][:3])
            out["color"] = AMBER
        return out

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
    "min_stock": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Stock%20Minimum%20Balance%20(2).xlsx?v=8", 
        "sheet_name": "Sheet1",
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

    "maintenance_logs": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTrPocQhFp-3kIL0QhVYFzIrkD5Wd5QmoShNK3i08MZSx4Wu59y25d0uo687C71guf3vc5FdNcM56_H/pubhtml",
        "worksheet": "0",
        "date_col": "Breakdown Date",
        "dayfirst": True
    },

    "foaming_chemicals": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Chemical%20Consumption.xlsx",
        "sheet_name": "Data",
        "date_col": "MONTH",
        "dayfirst": True
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
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/tdi_v2.xls",
        "sheet_name": "tdi",
        "date_col": "Date",
        "dayfirst": True,
    },
    "pop_data": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/pop.xls",
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
    "finance_ageing": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Ageing%20(2).xlsx",
        "sheet_name": "Ageing analysis",
        "date_col": "PARTY NAME",
    },
    "finance_svp": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/SVP%20(1).xlsx",
        "sheet_name": "svp",
        "date_col": "PARTY NAME",
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
        "sheet": "purchase_po",
        "mode": "month",
        "date_label": "month to",
        "calc": "purchase_mtd",
        "basis": "received",
    },

    ("inventory", "Total Inventory Value"): {"sheet": "stock_data", "calc": "stock_value"},
    ("inventory", "Dead Stock (Value & Qty)"): {"sheet": "stock_data", "calc": "stock_dead", "dead_days": 90},

    # Production Department ke saare blocks ki live binding:
    ("production", "Total Production & Yield"): {"sheet": "production_logs", "calc": "prod_log", "type": "total"},
    ("production", "Bdls & Yield"):      {"sheet": "bdls_de", "calc": "bdls_de"},
    ("production", "Rolls & Yield"):     {"sheet": "rolls_bc", "calc": "rolls_bc"},
    ("production", "Mattress & Yield"):  {"sheet": "prod_summary", "calc": "mattress_sum"},
    ("production", "Pillow & Yield"):    {"sheet": "prod_summary", "calc": "pillow_sum"},
    ("production", "Rollpack & Yield"):  {"sheet": "production_logs", "calc": "prod_log", "type": "rollpack"},

    # <<< FREIGHT DATA SOURCE >>>
    ("other", "Freight Report"): {
        "sheet": "freight_data",
        "calc": "freight_mtd",
    },

    # <<< Maintenance  >>>
    # <<< Maintenance  >>>
    # <<< Maintenance  >>>
    ("maint", "Current Breakdown Machines"): {
        "sheet": "maintenance_logs",
        "mode": "on_date",  # <-- Yahan "as_of" ki jagah "on_date" kar dein
        "calc": "generic_count",
        "col": "Issue Resolved",
        "where": {"Issue Resolved": "FALSE"},
    },
    ("maint", "Preventive Maintenance %"): {
        "sheet": "maintenance_logs",
        "mode": "as_of",
        "calc": "maintenance_pct",
    },
    # <<< ORDER MANAGEMENT DATA SOURCE >>>
    ("order", "Orders 0-7 Days Old"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_age_0_7"},
    ("order", "Orders 7-14 Days Old"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_age_7_14"},
    ("order", "Orders 14-21 Days Old"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_age_14_21"},
    ("order", "Orders 21+ Days Old"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_age_21_plus"},
    ("order", "Orders Left (No. / Qty)"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_pending"},
    ("order", "Current Schedule"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_current_schedule"},
    ("order", "Serviceability %"): {"sheet": ["order_management_1", "order_management_2"], "calc": "order_serviceability"},

    # <<< FINANCE DATA SOURCE >>>
    ("finance", "Total Drs & Crs"): {
        "sheet": "finance_svp",
        "calc": "finance_total_drs_crs",
    },
    ("finance", "Greater Than 90 / 180 Days"): {
        "sheet": "finance_ageing",
        "calc": "finance_ageing_90_180",
    },
    ("finance", "Total Due (Drs & Crs)"): {
        "sheet": "finance_ageing",
        "calc": "finance_total_due",
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
    ("sales", "Category Mix"): {
        "sheet": "sales_report",
        "calc": "sales_category_mix",
    },
    ("hr", "Manpower Present & Monthly Avg"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hr_manpower"},
    ("hr", "Overtime & Monthly Avg"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hr_overtime"},
    ("hr", "Dept-wise Report"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hr_dept"},

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
        "key": "production",
        "icon": "⚙️",
        "name": "PRODUCTION",
        "kpis": [
            ("Total Production & Yield", "All products aggregated"),
            ("Bdls & Yield", "Bundle production"),
            ("Rolls & Yield", "Roll production"),
            ("Mattress & Yield", "Mattress production"),
            ("Pillow & Yield", "Pillow production"),
            ("Rollpack & Yield", "Rollpack production"),
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
            ("Orders 0-7 Days Old", "Naye pending orders"),
            ("Orders 7-14 Days Old", "Pending 7 to 14 days"),
            ("Orders 14-21 Days Old", "Pending 14 to 21 days"),
            ("Orders 21+ Days Old", "Critical: Pending > 21 days"),
            ("Orders Left (No. / Qty)", "Total pending combined"),
            ("Current Schedule", "Aaj ke orders"),
            ("Serviceability %", "Approved vs Total"),
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
            ("Category Mix", "Online, Rebound & Others"),
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
            ("Total Inventory Value", "RM + WIP + FG"),
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
        ],
        "links": [
            ("📊 Freight Report (Power BI)", "https://app.powerbi.com/groups/me/reports/43dfa27d-52db-4423-b40d-2732870ef9f2/d02bed28a39f2f8e3034?experience=power-bi"),
            ("📋 Safety & Quality Log (Google Sheets)", None),
            ("📊 Customer Target vs Sale (Power BI)", None),
        ],
    },
]

# Dashboard mein departments ka order (upar se neeche)
DISPLAY_ORDER = ["foaming", "production", "order", "sales", "purchase",
                "inventory", "finance", "maint", "hr", "other"]
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
        raise DataError("Kisi bhi tab se data nahi mila. " + " | ".join(problems))

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
        raise DataError("Kisi bhi order tab se data nahi mila. " + " | ".join(problems))
    return pd.concat(frames, ignore_index=True), datetime.datetime.now(IST)


def get_sheet(name):
    """-> (DataFrame or None, error text or None, fetched-at or None)."""
    # Agar name ek list hai (jaise ["order_management_1", "order_management_2"])
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
        # LB Stock (gviz) ke liye
        if cfg.get("type") == "gviz":
            base = cfg["url"].split("/pub")[0]
            csv_url = f"{base}/pub?output=csv&gid={cfg.get('worksheet', '0')}"
            data = _http_get(csv_url)
            if data.lstrip()[:1] == b"<":
                raise PermissionError("Google Sheet data nahi de rahi, check karein ki Publish to web on hai.")
            df = _frame_from_csv(data, header_hint="GRADE") 
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
            # Check if this is the M-Shed file and use the custom column-based reader
            if name == "m_yield":
                url = cfg["files"][0][1] # Extract the URL
                df, fetched = _fetch_m_shed_custom(url)
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
                                            cfg["date_col"], cfg.get("dayfirst", True),
                                            cfg.get("static", False))
            good[name] = (df, fetched)
            errors.pop(name, None)
            return df, None, fetched

        # Baaki normal sheets ke liye (Purchase, Maintenance)
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


# ====================================================================
# 9. RENDER HELPERS
# ====================================================================
KPI_PER_ROW = 3


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
        body = "".join(f'<div class="kpi-row"><span class="kpi-rl">{l}</span><span class="kpi-rv">{v}</span></div>'
                       for l, v in rows)
        out.append(f'<div class="kpi-sec"><div class="kpi-sec-h">{heading}</div>{body}</div>')
    return "".join(out)


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
            # Main Dates nikalne ka code
            if spec.get("sheet") == "manual" or spec.get("calc") == "min_stock" or str(spec.get("calc", "")).startswith("hr_"):
                dates = [datetime.datetime.now(IST).date()]
            elif spec.get("calc") == "lb_stock":
                dates = [datetime.datetime.now(IST).date()]
            else:
                dates = available_dates(df)
            # HR: dates sirf wo jin din attendance / OT bhara hai (aaj ki date nahi)
            if str(spec.get("calc", "")).startswith("hr_"):
                _hd = _hr_dates(df)
                if _hd:
                    dates = _hd

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

            # PILLOW: dates sirf wo jin din J shed pillow bana (Prod. Summary se)
            if spec.get("calc") == "pillow_sum":
                _p = pillow_rows(df)
                if not _p.empty:
                    dates = sorted(set(_p["_date"].dropna().unique()), reverse=True)

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
            
            if not month_dates and spec.get("calc") == "lb_stock":
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

            # Yahan is_min_stock add karna zaroori tha
            hide_date = is_pillow or is_finance or is_foaming or is_min_stock or (spec.get("calc", "").startswith("sales_") and not spec.get("show_date"))

            if hide_date:
                chosen = month_dates[0]
                date_label = f"Full Month ({chosen.strftime('%b-%Y')})" if is_pillow or spec.get("calc", "").startswith("sales_") else "As on date"
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

            if res is not None and res.get("details"):
                with st.expander("📋 View Full Details"):
                    st.markdown(_sections_html(res["details"]), unsafe_allow_html=True)

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


def render_department(dept):
    with st.container(border=True):
        render_department_button(dept)
        kpis = dept["kpis"]
        for start in range(0, len(kpis), KPI_PER_ROW):
            cols = st.columns(KPI_PER_ROW)
            for offset, (title, desc) in enumerate(kpis[start:start + KPI_PER_ROW]):
                with cols[offset]:
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
        for name in sorted({n for s in KPI_SOURCES.values()
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
