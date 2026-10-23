import csv
import datetime
import io
import re
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

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
# 2. CUSTOM CSS  (compact, desktop-first, wraps on small screens)
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

    /* Department button (popover or link button) = blue strip */
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
        font-weight: 700 !important; font-size: 13px !important; color: #ffffff !important;
    }
    div[data-testid="stPopover"] > button:hover,
    a[data-testid="stBaseLinkButton-secondary"]:hover {
        background-color: #2B4FB5 !important;
    }

    /* KPI card text */
    .kpi-title { font-size: 10.5px; font-weight: 700; color: #334155;
                 text-transform: uppercase; line-height: 1.15; }
    .kpi-value { font-size: 16px; font-weight: 800; color: #0F172A; line-height: 1.2; }
    .kpi-desc  { font-size: 10px; font-weight: 500; line-height: 1.3;
                 white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    /* extra bottom space: Streamlit pulls markdown up by a negative margin,
       which was hiding the description line behind the date box */
    .kpi-wrap { padding-bottom: 1.1rem; }

    /* compact per-KPI date dropdown */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        min-height: 24px !important; font-size: 11px !important;
    }
    div[data-testid="stSelectbox"] { width: 132px !important; margin-bottom: -6px; }
    div[data-testid="stDateInput"] { width: 132px !important; margin-bottom: -6px; }
    div[data-testid="stDateInput"] div[data-baseweb="input"] {
        min-height: 22px !important; height: 24px !important; font-size: 10.5px !important;
    }
    div[data-testid="stDateInput"] input { padding: 0 2px 0 8px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 0.35rem 0.5rem; }
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

# ====================================================================
# DATA ENGINE (reads Google Sheets and calculates KPI values)
# ====================================================================
# --------------------------------------------------------------------
# Google Sheets access
# --------------------------------------------------------------------
def sheet_id(url):
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url or "")
    if not m:
        raise ValueError("This is not a Google Sheets link (expected .../spreadsheets/d/<ID>/...)")
    return m.group(1)


def _frame_from_rows(rows, header_hint=None):
    """Rows (list of lists) -> DataFrame of text.

    The header row is the first row that contains `header_hint` (e.g. "PO Date"),
    so empty lines or titles above the real header are skipped.
    """
    rows = [list(r) for r in rows]
    if not rows:
        return pd.DataFrame()
    start = 0
    if header_hint:
        want = str(header_hint).strip().lower()
        for i, row in enumerate(rows):
            if any(str(c).strip().lower() == want for c in row):
                start = i
                break
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


def _fetch_published(url, gid=None, header_hint=None):
    """Read a 'Publish to web' link (.../spreadsheets/d/e/2PACX-.../pubhtml).

    gid = the tab's number (the digits after #gid= in the sheet's address bar).
    None = the first tab.
    """
    base = url.split("/pub")[0]
    csv_url = f"{base}/pub?output=csv" + (f"&gid={gid}" if gid not in (None, "") else "")
    req = urllib.request.Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    if data.lstrip()[:1] == b"<":
        raise PermissionError("Google did not return data. Check that the tab is published to the web.")
    return _frame_from_csv(data, header_hint)


def fetch_sheet(url, worksheet=None, service_account=None, header_hint=None):
    """Return the worksheet as a DataFrame of text cells.

    "Publish to web" link  -> read directly (worksheet = tab gid number).
    service_account given  -> private sheet via Google API (gspread).
    otherwise              -> sheet must be shared "Anyone with the link: Viewer".
    """
    if "/spreadsheets/d/e/" in (url or ""):
        return _fetch_published(url, worksheet, header_hint)
    sid = sheet_id(url)

    if service_account:
        import gspread  # only needed for private sheets

        gc = gspread.service_account_from_dict(dict(service_account))
        sh = gc.open_by_key(sid)
        ws = sh.worksheet(worksheet) if worksheet else sh.sheet1
        return _frame_from_rows(ws.get_all_values(), header_hint)

    query = {"tqx": "out:csv"}
    if worksheet:
        query["sheet"] = worksheet
    csv_url = f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    if data.lstrip()[:1] == b"<":
        raise PermissionError(
            "Google returned a login page: the sheet is private. Share it as "
            "'Anyone with the link - Viewer', or add a service account in secrets."
        )
    return _frame_from_csv(data, header_hint)


# --------------------------------------------------------------------
# Preparing and computing KPI values
# --------------------------------------------------------------------
def prepare(df, date_col, dayfirst=True):
    """Add a clean `_date` column (rows with unreadable dates are dropped)."""
    if date_col not in df.columns:
        raise KeyError(f"date column '{date_col}' not found. Sheet columns: {list(df.columns)}")
    out = df.copy()
    out["_date"] = pd.to_datetime(out[date_col], dayfirst=dayfirst, errors="coerce").dt.date
    return out.dropna(subset=["_date"]).sort_values("_date", kind="stable")


def available_dates(df):
    """Dates present in the data, newest first."""
    return sorted(df["_date"].unique(), reverse=True)


def _num(series):
    cleaned = series.astype(str).str.replace(r"[₹,%\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def _need(df, col):
    if col not in df.columns:
        raise KeyError(f"column '{col}' not found. Sheet columns: {[c for c in df.columns if c != '_date']}")


def compute(df, spec, day):
    """KPI text for `day`, or None when the sheet has no data for that day.

    spec = {
      "mode": "on_date" (rows dated exactly `day`, default)
              | "as_of" (all rows dated on or before `day`),
      "parts": [{"agg": count|sum|mean|min|max|nunique|last,
                 "col": "<column>",              # not needed for count
                 "where": {"Status": "Pending"}}],  # optional, equality filters
      "fmt": "{0:,.0f} POs",   # {0}, {1}... = the parts in order
    }
    """
    if spec.get("mode", "on_date") == "as_of":
        sub = df[df["_date"] <= day]
    else:
        sub = df[df["_date"] == day]
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
            result = getattr(_num(col), agg)()
            values.append(result)
        else:
            raise ValueError(f"unknown agg '{agg}'")

    if any(v is None or (isinstance(v, float) and v != v) for v in values):
        return None
    return spec.get("fmt", "{0}").format(*values)


# ====================================================================
# 4. SETTINGS
# ====================================================================
BLUE = "#2563eb"
GREY = "#475569"
RED = "#dc2626"
AMBER = "#b45309"

REFRESH_SECONDS = 300          # auto-refresh every 5 minutes
IST = ZoneInfo("Asia/Kolkata")

# ====================================================================
# 5. DATA SOURCES  <<< FILL THESE IN (this is the only part to edit)
#
# 5a. SHEETS: one entry per Google Sheet tab that holds KPI data.
#     "url"       = the sheet's browser link (.../spreadsheets/d/<ID>/edit)
#     "worksheet" = tab name (leave None for the first tab)
#     "date_col"  = column that holds the date of each row
#     Example (remove the leading # to use):
#       "purchase_po": {
#           "url": "https://docs.google.com/spreadsheets/d/<ID>/edit",
#           "worksheet": "Pending PO",
#           "date_col": "PO Date",
#       },
# ====================================================================
SHEETS = {
    # Purchase -> "PO STATUS_v2", tab "Consolidated" (the PO rows).
    #   worksheet = the tab's gid (the digits after #gid= in the address bar;
    #               your screenshot showed gid=0 for Consolidated).
    #   date_col  = header of the PO date column.
    #   dayfirst  = False because your dates are month/day/year (3/21/2026).
    #   The header is on row 2; the code finds it automatically via date_col.
    "purchase_po": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRMyHArWBjTjiS4_B9LMLIkR2mYOVhviB5Yb-uQZ3sUWZV1W6dhkxQ6njifhKMIGq8eCCoK9U9dqz12/pubhtml",
        "worksheet": "0",
        "date_col": "PO Date",
        "dayfirst": False,
    },
}

# ====================================================================
# 5b. KPI_SOURCES: says which sheet + which columns give each KPI.
#     Key = (department key, KPI title exactly as shown on screen).
#     Example for Purchase -> Pending PO (remove the leading # to use):
#       ("purchase", "Pending PO"): {
#           "sheet": "purchase_po",
#           "mode": "as_of",     # rows dated on/before the chosen date
#           "parts": [{"agg": "count", "where": {"Status": "Pending"}}],
#           "fmt": "{0:,.0f} POs",
#       },
#     agg options: count, sum, mean, min, max, nunique, last
#     A KPI with two numbers (e.g. "Qty / Weight") uses two parts and
#     "fmt": "{0:,.0f} Units / {1:,.1f} MT".
#     KPIs not listed here show "Not connected" (never a made-up value).
# ====================================================================
KPI_SOURCES = {
    # Pending PO = number of different PO numbers whose Status is "Pending",
    # counting POs dated on or before the chosen date.
    # ASSUMPTION: the Consolidated tab has a column headed exactly "Status"
    # (it is off-screen in the screenshot) and "PO #" holds the PO number.
    # If a name is wrong, the block shows "Config error" and lists the
    # real column names so they can be corrected here.
    ("purchase", "Pending PO"): {
        "sheet": "purchase_po",
        "mode": "as_of",
        "parts": [{"agg": "nunique", "col": "PO #", "where": {"Status": "Pending"}}],
        "fmt": "{0:,.0f} POs",
    },
}

# ====================================================================
# 6. LINKS
#    Only real links are filled in.  None = link still to be added
#    (shown on screen as "link missing").
# ====================================================================
PURCHASE_SHEET = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRMyHArWBjTjiS4_B9LMLIkR2mYOVhviB5Yb-uQZ3sUWZV1W6dhkxQ6njifhKMIGq8eCCoK9U9dqz12/pubhtml"
)
PURCHASE_POWERBI = (
    "https://app.powerbi.com/groups/me/reports/"
    "3ac01124-e935-4964-a7b1-2436d90f0787/0ae022176631890e2147?experience=power-bi"
)

# ====================================================================
# 7. DEPARTMENT CONFIGURATION
#    kpis  = (KPI title, short description of what it measures)
#    Values are NOT stored here - they come from KPI_SOURCES above.
#    links = (label, url or None)
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
            ("POL Stock", "Chemical stock"),
            ("TDI Balance", "Chemical balance"),
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
            ("📊 Operational Yield View (Power BI)", None),
            ("📋 Plant Logs Register (Google Sheets)", None),
        ],
    },
    {
        "key": "order",
        "icon": "📦",
        "name": "ORDER MANAGEMENT",
        "kpis": [
            ("Orders Left (No. / Qty)", "PPC-wise pending"),
            ("Current Schedule", "Schedule status"),
            ("Serviceability %", "Serviceability"),
        ],
        "links": [
            ("📊 Order Dispatch Console (Power BI)", None),
            ("📋 Booking Tracker (Google Sheets)", None),
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
            ("📊 Target vs Actual Board (Power BI)", None),
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
            ("📋 Breakdown Log (Google Sheets)", None),
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
            ("📊 Inventory Dashboard (Power BI)", None),
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
            ("📊 HR Dashboard (Power BI)", None),
            ("📋 Attendance Sheet (Google Sheets)", None),
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
            ("📊 Freight Report (Power BI)", None),
            ("📋 Safety & Quality Log (Google Sheets)", None),
            ("📊 Customer Target vs Sale (Power BI)", None),
        ],
    },
]


# ====================================================================
# 8. LIVE DATA LOADING  (cached, auto-refresh, last-good fallback)
# ====================================================================
def _service_account():
    """Service-account credentials from .streamlit/secrets.toml, if present."""
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass
    return None


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_cached(url, worksheet, date_col, dayfirst, has_account):
    df = fetch_sheet(url, worksheet, _service_account() if has_account else None,
                     header_hint=date_col)
    df = prepare(df, date_col, dayfirst)
    return df, datetime.datetime.now(IST)


def get_sheet(name):
    """-> (prepared DataFrame or None, error text or None, fetched-at or None).

    If a refresh fails, the last good copy is returned together with the
    error, so the screen can say the data is stale instead of hiding it.
    """
    cfg = SHEETS.get(name)
    if not cfg or not cfg.get("url"):
        return None, f"sheet '{name}' has no link in SHEETS", None
    errors = st.session_state.setdefault("_errors", {})
    good = st.session_state.setdefault("_last_good", {})
    try:
        df, fetched = _fetch_cached(
            cfg["url"], cfg.get("worksheet"), cfg["date_col"],
            cfg.get("dayfirst", True), _service_account() is not None,
        )
        good[name] = (df, fetched)
        errors.pop(name, None)
        return df, None, fetched
    except Exception as exc:  # network, permission, wrong column ...
        msg = f"{type(exc).__name__}: {exc}"
        errors[name] = msg
        if name in good:
            return good[name][0], msg, good[name][1]
        return None, msg, None


# ====================================================================
# 9. RENDER HELPERS
# ====================================================================
KPI_PER_ROW = 3  # inside each department panel


def _card(slot, title, value, desc, color):
    slot.markdown(
        f"""
        <div class="kpi-wrap">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-desc" style="color:{color};" title="{desc}">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi(dept_key, idx, title, desc):
    key = f"{dept_key}_date_{idx}"
    spec = KPI_SOURCES.get((dept_key, title))

    with st.container(border=True):
        slot = st.empty()  # filled after the date is chosen

        if not spec:
            st.date_input(f"{title} date", datetime.datetime.now(IST).date(), key=key,
                          label_visibility="collapsed", format="DD/MM/YYYY", disabled=True)
            _card(slot, title, "Not connected", "Source not configured", GREY)
            return

        df, err, fetched = get_sheet(spec["sheet"])
        if df is None:
            st.date_input(f"{title} date", datetime.datetime.now(IST).date(), key=key,
                          label_visibility="collapsed", format="DD/MM/YYYY", disabled=True)
            _card(slot, title, "Data unavailable", err, RED)
            return

        dates = available_dates(df)
        if not dates:
            _card(slot, title, "No Data Available", "Sheet has no dated rows", GREY)
            return
        chosen = st.selectbox(
            f"{title} date", dates, key=key, label_visibility="collapsed",
            format_func=lambda d: d.strftime("%d/%m/%Y"),
        )
        try:
            value = compute(df, spec, chosen)
        except Exception as exc:
            _card(slot, title, "Config error", f"{type(exc).__name__}: {exc}", RED)
            return

        if value is None:
            _card(slot, title, "No Data Available", desc, GREY)
        elif err:
            _card(slot, title, value, f"⚠ Stale: last updated {fetched:%d/%m %H:%M}", AMBER)
        else:
            _card(slot, title, value, desc, BLUE)


def render_department_button(dept):
    """Blue strip: opens the department's Power BI / Google Sheet."""
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


# ====================================================================
# 10. MAIN LAYOUT: all departments visible, two per row.
#     Wrapped in a fragment so it re-runs by itself every REFRESH_SECONDS.
# ====================================================================
@st.fragment(run_every=REFRESH_SECONDS)
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
            render_department(DEPARTMENTS[i + 1])

    # ---- status line (filled after rendering, so it knows about errors) ----
    now = datetime.datetime.now(IST)
    total = sum(len(d["kpis"]) for d in DEPARTMENTS)
    connected = sum(1 for d in DEPARTMENTS for k in d["kpis"] if (d["key"], k[0]) in KPI_SOURCES)
    errors = st.session_state.get("_errors", {})
    fetched_times = [t for _, t in st.session_state.get("_last_good", {}).values()]
    last_data = max(fetched_times).strftime("%d/%m/%Y %H:%M:%S") if fetched_times else "never"
    with status_slot.container():
        st.caption(
            f"Data last fetched: **{last_data}** (IST) · page checked {now:%H:%M:%S} · "
            f"auto-refresh every {REFRESH_SECONDS // 60} min · "
            f"{connected} of {total} KPIs connected to a data source"
        )
        for name, msg in errors.items():
            st.error(f"Could not refresh '{name}': {msg}. Showing last good data if any.")

    missing = [
        f"{d['name']}: {label}"
        for d in DEPARTMENTS
        for label, url in d["links"]
        if not url
    ]
    if missing:
        with st.expander(f"⚠ {len(missing)} department links still to be added"):
            for m in missing:
                st.write(f"- {m}")


dashboard_body()
