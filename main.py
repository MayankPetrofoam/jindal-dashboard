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
        font-weight: 700 !important; font-size: 13px !important; color: #ffffff !important;
    }
    div[data-testid="stPopover"] > button:hover,
    a[data-testid="stBaseLinkButton-secondary"]:hover {
        background-color: #2B4FB5 !important;
    }

    .kpi-title { font-size: 10.5px; font-weight: 700; color: #334155;
                text-transform: uppercase; line-height: 1.15; }
    .kpi-value { font-size: 16px; font-weight: 800; color: #0F172A; line-height: 1.2; }
    .kpi-desc  { font-size: 10px; font-weight: 500; line-height: 1.3;
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .kpi-date  { font-size: 10px; font-weight: 700; color: #1E3A8A; line-height: 1.3; }
    .kpi-err   { font-size: 10px; font-weight: 500; line-height: 1.3; color: #dc2626;
                max-height: 3.9em; overflow: hidden; }
    .kpi-wrap { padding-bottom: 1.1rem; }

    /* compact per-KPI date dropdown (original design) */
    /* Dropdowns ko naya size aur spacing dein */
        /* Dropdowns ko chhota size aur spacing */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        min-height: 24px !important; 
        font-size: 10px !important;
        padding-left: 4px !important; 
        padding-right: 1px !important;
    }
    div[data-testid="stSelectbox"] { 
        width: 100% !important; 
        margin-bottom: 0 !important; 
    }
    /* Label ko chhota karo taaki jagah bache */
    div[data-testid="stSelectbox"] label {
        font-size: 9px !important;
        margin-bottom: 2px !important;
        line-height: 1 !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span { overflow: visible !important; }
    div[data-testid="stDateInput"] { width: 132px !important; margin-bottom: -6px; }
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
# Sheet layout (verified on your screenshots): a PO line is one row with a
# PO #, followed by rows with a blank PO # that carry one invoice each
# (Invoice #, Inv Qty, Recd Date ...). "Balance Qty" on the first row of a
# line equals PO Qty - sum(Inv Qty) (checked on POs 45, 49, 284, 339, 342,
# 350, 361), so Inv Qty with a Recd Date is what the sheet treats as received.
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


@st.cache_data(ttl=REFRESH_SECONDS - 5, show_spinner=False)
def _fetch_excel_cached(url, sheet_name, date_col, dayfirst, static=False):
    if re.match(r"^https?://", url or ""):
        data = _http_get(_direct_url(url))
        if data[:2] != b"PK":
            raise PermissionError("Link se Excel file nahi mili.")
        src = io.BytesIO(data)
    else:
        src = url
    raw = pd.read_excel(src, sheet_name=sheet_name, header=None, dtype=object, engine="openpyxl")
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

def compute_kpi(df, spec, day):
    calc = spec.get("calc")

    # ---------- PRODUCTION: TOTAL, MATTRESS, PILLOW, ROLLPACK ----------
    if calc == "prod_log":
        ptype = spec.get("type")

        # 1. ROLLPACK ke liye alag logic (F-Shed sheet se)
        # 1. ROLLPACK ke liye alag logic (F-Shed sheet se)
        if ptype == "rollpack":
            f_df, err_f, _ = get_sheet("f_shed")
            if f_df is None:
                return {"value": "Error", "desc": f"F-Shed data not available: {err_f}", "color": RED}

            month_start = day.replace(day=1)
            next_month = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            month_end = next_month - datetime.timedelta(days=1)

            # --- YIELD: F-Shed sheet se selected month ki latest date nikalna ---
            f_month_data = f_df[(f_df["_date"] >= month_start) & (f_df["_date"] <= month_end)]
            
            if not f_month_data.empty:
                actual_date = f_month_data["_date"].max() # Us mahine ki sabse latest date
                f_day = f_month_data[f_month_data["_date"] == actual_date]
            else:
                f_day = pd.DataFrame() # Agar us mahine ka data nahi hai

            day_yield = float(_num(_pcol(f_day, "F-SHED")).sum()) if not f_day.empty else 0.0
            month_yield = float(_num(_pcol(f_month_data, "F-SHED")).sum()) if not f_month_data.empty else 0.0

            # --- BDLS / SHEET / WEIGHT ---
            t = PROD_TYPES["rollpack"]
            s = _pcol(df, t["col"]).astype(str).str.upper()
            work = df[s.str.contains("|".join(map(re.escape, t["words"])), na=False)]
            w_mon = work[(work["_date"] >= month_start) & (work["_date"] <= month_end)]

            if w_mon.empty:
                bdls, sheets, weight = 0, 0.0, 0.0
            else:
                sheets = pd.to_numeric(w_mon["SHEET"], errors="coerce").fillna(0).sum() if "SHEET" in w_mon.columns else 0
                weight = pd.to_numeric(w_mon["WEIGHT"], errors="coerce").fillna(0).sum() if "WEIGHT" in w_mon.columns else 0
                bdls = pd.to_numeric(w_mon["BDLS"], errors="coerce").fillna(0).sum() if "BDLS" in w_mon.columns else 0
                if bdls == 0:
                    bdls = sheets

            # Categories
            if not f_month_data.empty:
                top = (f_month_data.assign(_v=_num(_pcol(f_month_data, "F-SHED")))
                       .groupby(_pcol(f_month_data, "ITEM").astype(str).str.strip())["_v"].sum()
                       .sort_values(ascending=False).head(4))
                cats = " | ".join(f"{k}: {v:,.1f}" for k, v in top.items())
            else:
                cats = "No yield data this month"

            return {
                "value": f"{day_yield:,.1f} Yield",
                "desc": f"Month ({month_start:%b-%y}): {bdls:,} Bdls | {sheets:,.0f} Sheets | {weight:,.1f} Wt",
                "color": BLUE,
                "extra": f"Month Yield: {month_yield:,.1f} | {cats}",
            }

        # 2. TOTAL ke liye logic
        elif ptype == "total":
            t = PROD_TYPES["total"]
            df_prod = df.copy()

            month_start = day.replace(day=1)
            next_month = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            month_end = next_month - datetime.timedelta(days=1)

            mtd_data = df_prod[(df_prod["_date"] >= month_start) & (df_prod["_date"] <= day)]

            mtd_sheets = 0
            mtd_weight = 0
            mtd_bdls = 0

            if not mtd_data.empty:
                if "SHEET" in mtd_data.columns:
                    mtd_sheets = pd.to_numeric(mtd_data["SHEET"], errors='coerce').fillna(0).sum()
                elif "SHEET ✓" in mtd_data.columns:
                    mtd_sheets = pd.to_numeric(mtd_data["SHEET ✓"], errors='coerce').fillna(0).sum()

                if "WEIGHT" in mtd_data.columns:
                    mtd_weight = pd.to_numeric(mtd_data["WEIGHT"], errors='coerce').fillna(0).sum()
                elif "WEIGHT ✓" in mtd_data.columns:
                    mtd_weight = pd.to_numeric(mtd_data["WEIGHT ✓"], errors='coerce').fillna(0).sum()

                if "BDLS" in mtd_data.columns:
                    mtd_bdls = pd.to_numeric(mtd_data["BDLS"], errors='coerce').fillna(0).sum()
                elif "BDLS ✓" in mtd_data.columns:
                    mtd_bdls = pd.to_numeric(mtd_data["BDLS ✓"], errors='coerce').fillna(0).sum()
                elif "BDLS." in mtd_data.columns:
                    mtd_bdls = pd.to_numeric(mtd_data["BDLS."], errors='coerce').fillna(0).sum()

                if mtd_bdls == 0:
                    mtd_bdls = mtd_sheets

            mtd_qty = mtd_sheets

            # Saari shed files se Daily Yield nikaalo
            total_yield = 0.0
            mtd_yield = 0.0

            for shed in ["m_shed", "f_shed"]:
                s_df, _, _ = get_sheet(shed)
                if s_df is not None:
                    yield_col = next((c for c in s_df.columns if "M-SHED" in str(c).upper() or "F-SHED" in str(c).upper()), None)
                    if yield_col:
                        s_day = s_df[s_df["_date"] == day]
                        if s_day.empty:
                            s_day = s_df[s_df["_date"] <= day].sort_values("_date").tail(1)
                        total_yield += float(_num(s_day[yield_col]).sum()) if not s_day.empty else 0.0

                        s_mtd = s_df[(s_df["_date"] >= month_start) & (s_df["_date"] <= day)]
                        mtd_yield += float(_num(s_mtd[yield_col]).sum()) if not s_mtd.empty else 0.0

            for shed_key in ["bdls_de", "rolls_bc"]:
                s_df, _, _ = get_sheet(shed_key)
                if s_df is not None and "val" in s_df.columns:
                    s_day = s_df[(s_df["_date"] == day) & (s_df["type"] == "PRODUCTION")]
                    total_yield += float(_num(s_day["val"]).sum()) if not s_day.empty else 0.0

                    s_mtd = s_df[(s_df["_date"] >= month_start) & (s_df["_date"] <= day) & (s_df["type"] == "PRODUCTION")]
                    mtd_yield += float(_num(s_mtd["val"]).sum()) if not s_mtd.empty else 0.0

            return {
                "value": f"{total_yield:,.1f} Yield | {mtd_bdls:,.0f} Bdls | {mtd_qty:,.0f} Sheets | {mtd_weight:,.1f} Wt",
                "desc": f"Month-to-date: {mtd_yield:,.1f} Yield | {mtd_bdls:,.0f} Bdls | {mtd_qty:,.0f} Sheets | {mtd_weight:,.1f} Wt",
                "color": BLUE,
                "extra": None
            }

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

        # 3. PILLOW ke liye logic
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
            # Yahan humne month aur YEAR dono match kiye hain
            mask = df["_date"].apply(lambda x: x.month == day.month and x.year == day.year if pd.notna(x) else False)
            return df[mask]

        if calc == "sales_last_month":
            month_sub = get_selected_month_data()
            if month_sub.empty:
                return {"value": "No Data", "desc": f"Records not available for {day.strftime('%b-%Y')}", "color": GREY}
            
            # Us month ki sabse last date nikalna
            actual_last_date = month_sub["_date"].max()
            sub = month_sub[month_sub["_date"] == actual_last_date]
            
            total_amt = sub["_amt"].sum()
            total_bdls = sub["_bdls"].sum()
            
            val_str = f"{_inr(total_amt)} | {total_bdls:,.0f} Bdls" if total_amt > 0 else f"{total_bdls:,.0f} Bdls"
                
            return {
                "value": val_str,
                "desc": f"Last recorded sale on {actual_last_date.strftime('%d-%b-%Y')}",
                "color": BLUE
            }

        elif calc == "sales_mtd":
            sub = get_selected_month_data()
            if sub.empty:
                return {"value": "₹0", "desc": f"No sales in {day.strftime('%b-%Y')}", "color": GREY}
            
            total_amt = sub["_amt"].sum()
            total_bdls = sub["_bdls"].sum()
            return {
                "value": _inr(total_amt),
                "desc": f"Month-to-date: {total_bdls:,.0f} Bdls",
                "color": BLUE
            }

        elif calc == "sales_category_mix":
            sub = get_selected_month_data()
            if sub.empty:
                return {"value": "No Data", "desc": f"No category data for {day.strftime('%b-%Y')}", "color": GREY}
            
            # ST. CODE ke hisaab se group karna
            mix = sub.groupby("_cat")["_amt"].sum().sort_values(ascending=False)
            mix = mix[(mix.index != "") & (mix.index != "nan") & (mix.index != "0")] # Blank hatao
            
            if mix.empty:
                return {"value": "No Data", "desc": "No category data", "color": GREY}

            top = mix.head(2)
            txt = " | ".join(f"{k}: {_inr(v)}" for k, v in top.items())
            return {
                "value": f"{len(mix)} Categories",
                "desc": txt,
                "color": BLUE
            }

        # Agar koi aur sales calc ho toh yahan se pehle wala purana code hata dein

        # ---------- OTHERS: FREIGHT ----------
    if calc == "freight_mtd":
        sub = df[(df["_date"] >= day.replace(day=1)) & (df["_date"] <= day)]
        if sub.empty:
            return {"value": "₹0", "desc": "No freight data this month", "color": GREY}
        
        # Freight ka total (ACT. RATE column uthayenge)
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
    # ---------- ORDER MANAGEMENT (Google Sheet, saare tabs) ----------
    # ---------- ORDER MANAGEMENT (Google Sheet, saare tabs) ----------
    if calc and str(calc).startswith("order_"):
        df_ord = df.copy()
        
        # 1. Qty Column dhoondho (Teeno tabs ke liye)
        qty_col = None
        for c in df_ord.columns:
            n = _norm(c)
            # TOTAL BCLS / BUNDLES / QTY (ORDER) dhoondho
            if ("total" in n and "bcl" in n) or ("qty" in n and "order" in n):
                qty_col = c
                break
        
        if not qty_col:
            # Fallback
            for c in df_ord.columns:
                n = str(c).upper()
                if "TOTAL" in n or "QTY" in n:
                    qty_col = c
                    break

        # 2. Pending filter (Finance APPROVED nahi hai ya NOT APPROVED/PENDING hai toh pending hai)
         # 2. Pending filter (Sirf APPROVED hi resolved hai, baaki sab pending hai)
        fin_col = next((c for c in df_ord.columns if "FINANCE" in str(c).upper()), None)
        if fin_col:
            fin_val = df_ord[fin_col].astype(str).str.strip().str.upper()
            
            # Agar cell mein "APPROVED" hai AUR "NOT" nahi hai -> Resolved
            # Baaki sab (NOT APPROVED, PAYMENT PENDING, blank) -> Pending
            is_approved = fin_val.str.contains("APPROVED", na=False) & ~fin_val.str.contains("NOT", na=False)
            df_ord["_is_pending"] = ~is_approved
        else:
            df_ord["_is_pending"] = True

        # 3. Age calculation (Ek hi baar karna hai)
        df_ord["_age_days"] = df_ord["_date"].apply(lambda x: (day - x).days if pd.notna(x) else 999)
        pending_df = df_ord[df_ord["_is_pending"]]

    # --- AGEING BLOCKS (0-7, 7-14, 14-21, 21+) ---
    if calc in ("order_age_0_7", "order_age_7_14", "order_age_14_21", "order_age_21_plus"):
        if calc == "order_age_0_7":
            sub = pending_df[(pending_df["_age_days"] >= 0) & (pending_df["_age_days"] <= 7)]
            label = "0-7 Days"
            color = BLUE
        elif calc == "order_age_7_14":
            sub = pending_df[(pending_df["_age_days"] > 7) & (pending_df["_age_days"] <= 14)]
            label = "7-14 Days"
            color = BLUE
        elif calc == "order_age_14_21":
            sub = pending_df[(pending_df["_age_days"] > 14) & (pending_df["_age_days"] <= 21)]
            label = "14-21 Days"
            color = AMBER
        elif calc == "order_age_21_plus":
            sub = pending_df[pending_df["_age_days"] > 21]
            label = "21+ Days (Critical)"
            color = RED

        total_orders = len(sub)
        total_qty = _num(sub[qty_col]).sum() if qty_col else 0
        
        return {
            "value": f"{total_orders} Orders",
            "desc": f"{label} pending | Qty: {total_qty:,.0f}",
            "color": color
        }

    # --- ORDERS LEFT (No. / Qty) ---
    if calc == "order_pending":
        total_orders = len(pending_df)
        total_qty = _num(pending_df[qty_col]).sum() if qty_col else 0
        
        if "TAB_GID" in pending_df.columns:
            per_tab = " | ".join(f"Tab {t}: {len(g)}" for t, g in pending_df.groupby("TAB_GID"))
        else:
            per_tab = ""
            
        return {
            "value": f"{total_orders} Orders",
            "desc": f"Total Qty: {total_qty:,.0f}",
            "color": RED if total_orders > 0 else BLUE,
            "extra": per_tab
        }

    # --- CURRENT SCHEDULE ---
    if calc == "order_current_schedule":
        today_df = df_ord[df_ord["_date"] == day]
        if today_df.empty:
            return {"value": "0 Orders", "desc": "No orders scheduled", "color": GREY}
        
        total_orders = len(today_df)
        total_qty = _num(today_df[qty_col]).sum() if qty_col else 0
        pending_today = today_df[today_df["_is_pending"]]
        
        return {
            "value": f"{total_orders} Orders",
            "desc": f"Today's Qty: {total_qty:,.0f} | Pending: {len(pending_today)}",
            "color": BLUE
        }

    # --- SERVICEABILITY % ---
    if calc == "order_serviceability":
        total = len(df_ord)
        if total == 0:
            return None
        approved = len(df_ord[~df_ord["_is_pending"]])
        pct = (approved / total) * 100
        
        return {
            "value": f"{pct:.1f}%",
            "desc": f"{approved} Approved / {total} Total",
            "color": BLUE if pct > 80 else AMBER
        }
        

    # ---------- PRODUCTION: PILLOW (Sirf Month-wise & Pcs) ----------
    if calc == "prod_log" and spec.get("type") == "pillow":
        t = PROD_TYPES[spec["type"]]
        s = _pcol(df, t["col"]).astype(str).str.upper()
        m = s.str.contains("|".join(map(re.escape, t["words"])), na=False)
        work = df[m]

        def agg_pillow(d):
            if d.empty:
                return 0, 0.0
            # BDLS column ka sum
            bdl = int(_num(_pcol(d, "BDLS")).sum())
            
            # Pcs ke liye 'SHEET' column ki values ko sum karo (kyunki sheet mein yahi Pcs hai)
            qty = float(_num(_pcol(d, "SHEET")).sum()) 
            return bdl, qty

        # Sirf selected month ka data (1st se last date tak)
        month_start = day.replace(day=1)
        next_month = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        month_end = next_month - datetime.timedelta(days=1)
        month_data = work[(work["_date"] >= month_start) & (work["_date"] <= month_end)]
        
        month_b, month_q = agg_pillow(month_data)

        # UI par display format
        return {"value": f"{month_b:,} Bdls | {month_q:,.0f} Pcs",
                "desc": f"Full Month Total ({day.strftime('%b-%Y')})",
                "color": BLUE,
                "extra": None} 
        
    # ---------- FOAMING: TONNAGE (CONSUMPTION) ----------
    if calc == "sum_consumption":
        col = spec.get("col", "CONS")
        if col not in df.columns:
            raise DataError(f"Column '{col}' not found.")
        
        # Data ko selected date ke month se filter karo
        sub = df[df["_date"].apply(lambda d: d.month == day.month and d.year == day.year if pd.notna(d) else False)]
        
        # Agar upar wala filter fail ho, toh fallback (as_of logic)
        if sub.empty:
            sub = df[df["_date"] <= day]
        if sub.empty:
            return None
        
        # Agar 'where' condition di hai (jaise TDI DRUMS), toh filter karo
        for col_name, wanted in spec.get("where", {}).items():
            if col_name in sub.columns:
                sub = sub[sub[col_name].astype(str).str.strip().str.lower() == str(wanted).strip().lower()]
        
        if sub.empty:
            return None
            
        total_cons = _num(sub[col]).sum()
        return {"value": f"{total_cons:,.2f}", "desc": f"Consumption for {day.strftime('%b-%Y')}", "color": BLUE}

    # ---------- FOAMING: TDI BALANCE ----------
    if calc == "last_balance":
        col = spec.get("col", "TDI_Balance")
        if col not in df.columns:
            raise DataError(f"Column '{col}' not found. Columns: {list(df.columns)}")
        
        # Selected date ka last record
        sub = df[df["_date"] <= day]
        if sub.empty:
            return None
        
        last_val = _num(sub[col]).dropna().iloc[-1] if not _num(sub[col]).dropna().empty else 0
        return {"value": f"{last_val:,.2f} Qty", "desc": f"Balance as on {day.strftime('%d-%b-%Y')}", "color": BLUE}
        # ---------- PURCHASE: GOODS BELOW MIN STOCK ----------
    if calc == "min_stock":
        item = _pcol(df, "ITEM NAME").astype(str).str.strip()
        status = _pcol(df, "STATUS").astype(str).str.strip().str.lower()
        group = _pcol(df, "STOCK GROUP").astype(str).str.strip()
        valid = item != ""
        below = valid & status.str.startswith("below")
        n_below, n_all = int(below.sum()), int(valid.sum())
        names = ", ".join(item[below].head(3).tolist())
        by_group = " | ".join(f"{g.title()}: {c}" for g, c in group[below].value_counts().items())
        return {"value": f"{n_below} Items",
                "desc": (names + ("..." if n_below > 3 else "")) if n_below else "Sab items minimum se upar",
                "color": RED if n_below else BLUE,
                "extra": f"{by_group} | Total tracked: {n_all}" if n_below else f"Total tracked: {n_all}"}
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
    if calc == "generic_count":
        col = spec.get("col")
        where = spec.get("where", {})
        sub = df[df["_date"] <= day]
        if sub.empty:
            return {"value": "0", "desc": "No records found till this date", "color": BLUE}
        
        # Filter lagana (Jaise Issue Resolved blank hona chahiye)
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
        
        # "Issue Resolved" column dhoondho (agar column ka naam thoda alag ho toh)
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
        def tot(d, typ):
            return float(d.loc[d["type"] == typ, "val"].sum())

        d_day = df[df["_date"] == day]
        # Month-to-date (1st se selected date tak)
        d_mtd = df[(df["_date"] >= day.replace(day=1)) & (df["_date"] <= day)]
        # POORA MONTH (1st se last date tak) - naya add kiya
        month_start = day.replace(day=1)
        next_month = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        month_end = next_month - datetime.timedelta(days=1)
        d_full_month = df[(df["_date"] >= month_start) & (df["_date"] <= month_end)]

        b, p = tot(d_day, "BUNDLES"), tot(d_day, "PRODUCTION")
        
        # Shed-wise breakdown for selected date
        parts = []
        for shed in sorted(df["shed"].unique()):
            s = d_day[d_day["shed"] == shed]
            parts.append(f"{shed}: {tot(s, 'BUNDLES'):,.0f} Bdls")

        # Naya: Complete month ki total production (Bundles + Production)
        full_month_b = tot(d_full_month, "BUNDLES")
        full_month_p = tot(d_full_month, "PRODUCTION")

        return {
            "value": f"{b:,.0f} Bdls | {p:,.1f} Prod",
            "desc": f"Month-to-date: {tot(d_mtd, 'BUNDLES'):,.0f} Bdls | {tot(d_mtd, 'PRODUCTION'):,.1f} Prod",
            "color": BLUE,
            "extra": f"{' | '.join(parts)} | Month Total: {full_month_b:,.0f} Bdls | {full_month_p:,.1f} Prod"
        }

    # ---------- PRODUCTION: ROLLS (B + C Shed) ----------
    if calc == "rolls_bc":
        def tot(d, typ):
            return float(d.loc[d["type"] == typ, "val"].sum())

        d_day = df[df["_date"] == day]
        d_mtd = df[(df["_date"] >= day.replace(day=1)) & (df["_date"] <= day)]
        # POORA MONTH - naya add kiya
        month_start = day.replace(day=1)
        next_month = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        month_end = next_month - datetime.timedelta(days=1)
        d_full_month = df[(df["_date"] >= month_start) & (df["_date"] <= month_end)]

        r, m, p = tot(d_day, "ROLLS"), tot(d_day, "METERS"), tot(d_day, "PRODUCTION")
        
        parts = []
        for shed in sorted(df["shed"].unique()):
            s = d_day[d_day["shed"] == shed]
            parts.append(f"{shed}: {tot(s, 'ROLLS'):,.0f} Rolls / {tot(s, 'METERS'):,.0f} Mtr")

        # Naya: Complete month ki total production
        full_month_r = tot(d_full_month, "ROLLS")
        full_month_m = tot(d_full_month, "METERS")
        full_month_p = tot(d_full_month, "PRODUCTION")

        return {
            "value": f"{r:,.0f} Rolls | {m:,.0f} Mtr",
            "desc": f"Production: {p:,.1f} | Month-to-date: {tot(d_mtd, 'ROLLS'):,.0f} Rolls",
            "color": BLUE,
            "extra": f"{' | '.join(parts)} | Month Total: {full_month_r:,.0f} Rolls | {full_month_m:,.0f} Mtr | Prod: {full_month_p:,.1f}"
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
    first_row = df.iloc[0].astype(str).str.strip().tolist()
    second_row = df.iloc[1].astype(str).str.strip().tolist()
    
    date_columns = {}
    current_date = None
    
    for idx, cell in enumerate(first_row):
        # PATCH: Text ko date mein convert karo
        if cell:
            try:
                # "1-Oct-26" ko date object banata hai
                parsed_dt = pd.to_datetime(cell, format="%d-%b-%y", errors="coerce")
                if pd.notna(parsed_dt):
                    current_date = parsed_dt.date()
            except:
                pass
            
        if current_date:
            sub = second_row[idx].lower()
            if 'actual production' in sub:
                if current_date not in date_columns:
                    date_columns[current_date] = {}
                date_columns[current_date]["prod_col"] = idx
            elif 'efficiency' in sub or 'eff' in sub:
                if current_date not in date_columns:
                    date_columns[current_date] = {}
                date_columns[current_date]["eff_col"] = idx
                
    available_dates = list(date_columns.keys())
    records = []
    
    for idx, row in df.iterrows():
        if idx < 2:
            continue
        shed = str(row.iloc[0]).strip()
        unit_type = str(row.iloc[1]).strip()
        
        if not shed or shed in ["None", "Shed Name", ""]:
            continue
            
        for dt, cols in date_columns.items():
            try:
                prod_val = str(row.iloc[cols["prod_col"]]).replace(',', '').strip()
                eff_val = str(row.iloc[cols["eff_col"]]).replace('%', '').replace(',', '').strip() if "eff_col" in cols else "0"
                
                records.append({
                    "Date": dt,
                    "Shed": shed,
                    "UnitType": unit_type,
                    "ActualProduction": pd.to_numeric(prod_val, errors='coerce'),
                    "Efficiency": pd.to_numeric(eff_val, errors='coerce')
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
    # "PO STATUS_v2" -> tab "Consolidated". One PO line = one row with a PO #,
    # followed by rows with a blank PO # that each carry one invoice.
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
    # <<< YAHAN SE NAYA SALES BLOCK ADD KAREIN >>>
        "sales_report": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/All_Years_Sale_Data.xlsx", # <-- Yahan apni file ka exact naam/path daalein
        "sheet_name": "Sales Data",  # Aapke screenshot ke hisaab se tab ka naam
        "date_col": "MONTH",         # Aapki sheet me date ka column
        "dayfirst": True,
    },
    # Add more tabs/sheets here, each with ITS OWN date_col.
        "production_logs": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/All%20shed%20production%202026-27%20(5).xlsx",
        "sheet_name": "FY2026-27 Prod. Sheet",
        "date_col": "DATE",
        "dayfirst": True,
    },
        # F-Shed (Yield ke liye)
    "f_shed": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/F-Shed%20(1).xlsx",
        "sheet_name": "F-Shed",
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
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Stock%20Minimum%20Balance.xlsx",
        "sheet_name": "Sheet1",
        "date_col": "STATUS",
    },
            "bdls_de": {
        "type": "bdls_de",
        "url": "bdls_de",
        "files": (
            ("D Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Shed-D%20Bdls%2BProd%20(1).xlsx", "Shed-D Bdls+Prod"),
            ("E Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Shed-E%20Bdls%2BProd.xlsx", "Shed-E Bdls+Prod"),
        ),
    },
        "rolls_bc": {
        "type": "rolls_bc",
        "url": "rolls_bc",
        "files": (
            ("B Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/B-Shed%20Mtrs%2BRolls%2BProd.xlsx", "B-Shed Mtrs+Rolls+Prod"),
            ("C Shed", "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/C-Shed%20Mtrs%2BRolls%2BProd%20(1).xlsx", "C-Shed Mtrs+Rolls+Prod"),
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
        "sheet_name": "Data", # <--- YEH ADD KARNA ZAROORI HAI (Aapki excel file me jo tab ka naam hai, woh daalein)
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
        "worksheet": "1511781172",  # Aapki screenshot ke hisaab se GID
        "date_col": "DATE",         # Freight sheet mein date wala column
        "dayfirst": False,          # 22-Oct-26 format ke liye
        "ignore_cols": ["MONTH"],   # MONTH column ko filter karne ke liye
    },

    "hr_manpower": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vR4PjMPwxSrMxWE010j_3E4TXjUmmHo9nERPYUcTKfrHE9C_NeR-HbC50QrpKc8Yw/pubhtml",
        "worksheet": "1154348919",     # Over Time Data tab ka gid
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
        "order_management": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQZiVAgR2AeNLr-IZ-mW2g7Zp-Kye0IRyKtn7KjI_ygm_fGNPE4SB2BljpBmAHf4unirihIGmHrksr/pubhtml",
        "worksheet": ["0", "1151895349", "416003397"],
        "date_col": "DATE",
        "dayfirst": False,  # <--- YEH TRUE SE FALSE KAR DEIN
        "ignore_cols": ["REASON", "FINANCE"],
    },
    "m_shed": {
        "type": "excel",
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/M-Shed%20(4).xlsx",  # <-- M-Shed (4).xlsx KA SAHI LINK
        "sheet_name": "M-Shed",  # <-- Sheet tab ka naam "M-Shed" hi hai
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
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/Ageing%20(2).xlsx", # <-- Yahan apni actual Finance file ka link daalein
        "sheet_name": "Ageing analysis",
        "date_col": "PARTY NAME",
    },
    "finance_svp": {
        "type": "excel",
        "static": True,
        "url": "https://raw.githubusercontent.com/MayankPetrofoam/jindal-dashboard/main/SVP%20(1).xlsx", # <-- Yahan apni actual Finance file ka link daalein
        "sheet_name": "svp",
        "date_col": "PARTY NAME",
    },
}
# ====================================================================
# 5b. KPI_SOURCES  (key = (department key, KPI title exactly as on screen))
# ====================================================================
KPI_SOURCES = {
    # Open POs (count) as of the selected date; description line shows the
    # outstanding quantity per unit (PCS / KGS / MTR).
    ("purchase", "Pending PO"): {
    "sheet": "purchase_po",
    "mode": "on_date",
    "date_label": "PO date",
    "calc": "po_pending",
},
    # Value of goods received from the 1st of the month up to the selected date
    # = sum(Inv Qty x Invoice Rate) by Recd Date.  Change "basis" to "po" to use
    # PO value instead (sum(PO Qty x PO Rate) by PO Date).
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
    ("production", "Mattress & Yield"):  {"sheet": "production_logs", "calc": "prod_log", "type": "mattress"},
    ("production", "Pillow & Yield"):    {"sheet": "production_logs", "calc": "prod_log", "type": "pillow"},
    ("production", "Rollpack & Yield"):  {"sheet": "production_logs", "calc": "prod_log", "type": "rollpack"},

    # <<< FREIGHT DATA SOURCE >>>
    ("other", "Freight Report"): {
        "sheet": "freight_data",
        "calc": "freight_mtd",
    },

    # <<< Maintenance  >>>
    ("maint", "Current Breakdown Machines"): {
    "sheet": "maintenance_logs",
        "mode": "as_of",
        "calc": "generic_count",
        "col": "Issue Resolved",           
        "where": {"Issue Resolved": ""},   
    },
    ("maint", "Preventive Maintenance %"): {
        "sheet": "maintenance_logs",
        "mode": "as_of",
        "calc": "maintenance_pct",
    },
        # <<< Yahan se naye Order Ageing blocks shuru >>>
    # <<< ORDER MANAGEMENT DATA SOURCE >>>
    ("order", "Orders 0-7 Days Old"): {"sheet": "order_management", "calc": "order_age_0_7"},
    ("order", "Orders 7-14 Days Old"): {"sheet": "order_management", "calc": "order_age_7_14"},
    ("order", "Orders 14-21 Days Old"): {"sheet": "order_management", "calc": "order_age_14_21"},
    ("order", "Orders 21+ Days Old"): {"sheet": "order_management", "calc": "order_age_21_plus"},
    ("order", "Orders Left (No. / Qty)"): {"sheet": "order_management", "calc": "order_pending"},
    ("order", "Current Schedule"): {"sheet": "order_management", "calc": "order_current_schedule"},
    ("order", "Serviceability %"): {"sheet": "order_management", "calc": "order_serviceability"},
    
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
    # Baaki 2 blocks (Receivable/Payable Days aur Total Amt Received/Paid) ke liye abhi data nahi hai
    # isliye unhe hata dein ya unka "calc" empty chhod dein
# <<< YAHAN SE SALES KA CODE ADD KAREIN >>>
        # <<< SALES DATA SOURCE >>>
    ("sales", "Last Day Sale (Value & Bdls)"): {
        "sheet": "sales_report",
        "calc": "sales_last_month", # Yeh function ab asli Excel se calculate karega
    },
    ("sales", "T/O in This Month"): {
        "sheet": "sales_report",
        "calc": "sales_mtd",
    },
    ("sales", "Category Mix"): {
        "sheet": "sales_report",
        "calc": "sales_category_mix",
    },
    ("hr", "Manpower Present & Monthly Avg"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hr_manpower"},
    ("hr", "Overtime & Monthly Avg"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hr_overtime"},
    ("hr", "Dept-wise Report"): {"sheet": "hr_manpower", "mode": "on_date", "date_label": "date", "calc": "hr_dept"},

    ("foaming", "Tonnage Foaming"): {
        "sheet": "foaming_chemicals",
        "calc": "sum_consumption",
        "col": "CONS"                 # <--- Excel me column ka naam CONS hai
    },
    ("foaming", "TDI Balance"): {
        "sheet": "foaming_chemicals",
        "calc": "last_balance",
        "col": "TDI_Balance"          # (Isko baad me theek karenge)
    },
    # <<< YAHAN TAK >>>
}
# Shown on KPI blocks that have no source yet, so "Not connected" always says why.
MISSING_SOURCE = {
    ("purchase", "Goods Below MS"): "Needs a stock tab with item, current stock and minimum stock columns "
                                    "(not in the PO 'Consolidated' tab)",
}
DEFAULT_MISSING = "Source tab not provided yet (the PO STATUS sheet only holds purchase-order rows)"

# ====================================================================
# ====================================================================
# 6. LINKS
# ====================================================================
PURCHASE_SHEET = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRMyHArWBjTjiS4_B9LMLIkR2mYOVhviB5Yb-uQZ3sUWZV1W6dhkxQ6njifhKMIGq8eCCoK9U9dqz12/pubhtml"
)
# Power BI: this is a report VIEWING link only. It opens the report in a browser;
# it does not give this app any data. See POWERBI_NOTE / the Diagnostics panel.
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
            d = fetch_sheet(url, gid, None, header_hint=date_col).copy()
            d["TAB_GID"] = str(gid)
            frames.append(d)
        except Exception as exc:
            problems.append(f"gid {gid}: {type(exc).__name__}: {exc}")
    if not frames:
        raise DataError("Kisi bhi tab se data nahi mila. " + " | ".join(problems))
    df = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    # 05.10.2026 jaisi dates ke dots hatao
    df[date_col] = df[date_col].astype(str).str.replace(".", "-", regex=False)
    out = prepare(df, date_col, dayfirst, (), None, (), tuple(ignore) + ("TAB_GID",))
    return out, datetime.datetime.now(IST)


def get_sheet(name):
    """-> (DataFrame or None, error text or None, fetched-at or None)."""
    cfg = SHEETS.get(name)
    if not cfg or not cfg.get("url"):
        return None, f"sheet '{name}' has no link in SHEETS", None
    errors = st.session_state.setdefault("_errors", {})
    good = st.session_state.setdefault("_last_good", {})
    try:
        if isinstance(cfg.get("worksheet"), (list, tuple)):
            df, fetched = _fetch_multi_cached(cfg["url"], tuple(cfg["worksheet"]), cfg["date_col"],
                                            cfg.get("dayfirst", True), tuple(cfg.get("ignore_cols", ())))
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


def _card(slot, title, value, desc, color, date_text=None, error=False, extra=None):
    date_html = f'<div class="kpi-date">📅 {date_text}</div>' if date_text else ""
    safe = str(desc).replace('"', "'").replace("<", "&lt;")
    desc_html = (f'<div class="kpi-err" style="color:{color};" title="{safe}">{safe}</div>' if error else
                f'<div class="kpi-desc" style="color:{color};" title="{safe}">{safe}</div>')
    extra_html = (f'<div class="kpi-date" style="color:#0F172A;">Σ {extra}</div>') if extra else ""
    slot.markdown(
        f"""
        <div class="kpi-wrap">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        {date_html}
        {desc_html}
        {extra_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _disabled_date(title, key):
    st.date_input(f"{title} date", datetime.datetime.now(IST).date(), key=key,
                label_visibility="collapsed", format="DD/MM/YYYY", disabled=True)


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
            if str(spec.get("calc", "")).startswith("hr_"):
                dates = _hr_dates(df)
            else:
                dates = available_dates(df)

            # ROLLPACK ke liye F-Shed ki dates bhi jodo (taaki Oct month dropdown mein aaye)
            if spec.get("type") == "rollpack":
                _f, _e, _t = get_sheet("f_shed")
                if _f is not None and "_date" in _f.columns:
                    dates = sorted(set(dates) | set(_f["_date"].dropna().unique()), reverse=True)

            # Agar Mattress hai, toh M-Shed ki dates bhi jodo (October ke liye)

            # Agar Mattress hai, toh M-Shed ki dates bhi jodo (October ke liye)
            # Agar Mattress hai, toh M-Shed ki dates bhi jodo (October ke liye)
            if spec.get("type") == "mattress":
                _m, _e, _t = get_sheet("m_shed")
                if _m is not None:
                    dates = sorted(set(dates) | set(_m["_date"].dropna().unique()), reverse=True)

            # TOTAL ke liye bhi saari sheds ki dates jodo
            # TOTAL ke liye bhi saari sheds ki dates jodo
            if spec.get("type") == "total":
                for shed_key in ["m_shed", "f_shed", "bdls_de", "rolls_bc"]:
                    _s, _e, _t = get_sheet(shed_key)
                    if _s is not None and "_date" in _s.columns:
                        dates = sorted(set(dates) | set(_s["_date"].dropna().unique()), reverse=True)

            # --- MONTH dropdown ---
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
            
            mcol, dcol = st.columns([1, 1], gap="small")
            chosen_m = mcol.selectbox(
                f"{title} month", months, key=f"{key}_m", label_visibility="collapsed",
                format_func=lambda m: datetime.date(m[0], m[1], 1).strftime("%b-%y"),
            )
            
            month_dates = [d for d in dates if (d.year, d.month) == chosen_m]
            if not month_dates:
                _disabled_date(title, key)
                _card(slot, title, "No Data Available for This Month", desc, GREY, datetime.date(chosen_m[0], chosen_m[1], 1).strftime("%b-%Y"))
                return

            # --- PILLOW KE LIYE SIRF MONTH, DATE HIDDEN ---
            # Purana:
            # is_finance = str(spec.get("calc", "")).startswith("finance_")
            # if is_pillow or is_finance:

            # Naya (Isko copy-paste karein):
            is_pillow = (spec.get("calc") == "prod_log" and spec.get("type") == "pillow")
            is_finance = str(spec.get("calc", "")).startswith("finance_")
            is_sales = str(spec.get("calc", "")).startswith("sales_") # <-- YEH ADD KAREIN

            if is_pillow or is_finance or is_sales: # <-- Yahan is_sales add karein
                chosen = month_dates[0]
                date_label = f"Full Month ({chosen.strftime('%b-%Y')})" if is_pillow or is_sales else "As on date"
            else:
                chosen = dcol.selectbox(
                    f"{title} date", month_dates, key=f"{key}_{chosen_m[0]}_{chosen_m[1]}",
                    label_visibility="collapsed",
                    format_func=lambda d: d.strftime("%d-%m-%y"),
                )
                date_label = chosen.strftime(DATE_FMT)
            
            st.session_state[key] = chosen  # <--- YEH LINE BAHAR (EKDUM LEFT) AANI CHAHIYE
            prefix = spec.get("date_label", "as of" if spec.get("mode") == "as_of" else "")
            label = f"{prefix} {date_label}".strip()
            
            try:
                res = compute_kpi(df, spec, chosen)
            except Exception as exc:
                log.exception("KPI %s/%s failed", dept_key, title)
                _card(slot, title, "Config error", f"{type(exc).__name__}: {exc}", RED, label, error=True)
                return

            if res is None:
                _card(slot, title, "No Data Available for This Date", desc, GREY, chosen.strftime(DATE_FMT))
            elif err:
                _card(slot, title, res["value"], f"⚠ Stale: last updated {fetched:%d-%m %H:%M}", AMBER, label, extra=res.get("extra"))
            else:
                _card(slot, title, res["value"], res["desc"] or desc, res["color"] or BLUE, label, extra=res.get("extra"))
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
        for name in sorted({s["sheet"] for s in KPI_SOURCES.values()}):
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
@st.fragment
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


dashboard_body()
