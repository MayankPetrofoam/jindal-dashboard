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
    """Text -> datetime (unreadable -> NaT), tolerant of 9/1/2026 and 09/01/2026 mixes."""
    if int(pd.__version__.split(".")[0]) >= 2:
        return pd.to_datetime(series, dayfirst=dayfirst, errors="coerce", format="mixed")
    return pd.to_datetime(series, dayfirst=dayfirst, errors="coerce")


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


def po_pending(df, day, overrides=None):
    """Outstanding PO quantity as of `day`. None when no PO is dated on/before `day`."""
    issues = []
    c = _resolve_columns(df, overrides)
    w = df[df["_date"] <= day]
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


def purchase_mtd(df, day, overrides=None, basis="received"):
    """Purchase value from the 1st of `day`'s month up to `day`.

    basis "received": sum(Inv Qty x Invoice Rate) of invoices whose Recd Date falls in that window.
    basis "po"      : sum(PO Qty x PO Rate) of PO lines whose PO Date falls in that window.
    """
    issues = []
    c = _resolve_columns(df, overrides)
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


def compute_kpi(df, spec, day):
    """-> {"value", "desc" (or None), "color" (or None)} or None when there is no data."""
    calc = spec.get("calc")

  # ==========================================
    # 1. MAINTENANCE: CURRENT BREAKDOWN MACHINES
    # ==========================================
    if calc == "generic_count":
        # SIRF us din ka data filter karo (Exact match, <= nahi)
        sub = df[df["_date"] == day].copy()
        
        if sub.empty:
            return {"value": "0 Machines", "desc": "No breakdowns on this date", "color": BLUE}
            
        col = spec.get("col", "Issue Resolved")
        if col not in sub.columns:
             return {"value": "0", "desc": "Column not found", "color": RED}
             
        # Us din ki jo machines FALSE hain (kharab hain) unhe count karo
        is_breakdown = sub[col].astype(str).str.strip().str.upper() == "FALSE"
        count = is_breakdown.sum()
        
        return {"value": f"{count} Machines", "desc": f"Breakdowns reported on {day.strftime('%d-%b-%Y')}", "color": RED if count > 0 else BLUE}

    # ==========================================
    # 2. MAINTENANCE: PREVENTIVE %
    # ==========================================
    if calc == "maintenance_pct":
        # SIRF us din ka data
        sub = df[df["_date"] == day].copy()
        if sub.empty:
            return {"value": "0%", "desc": "No records on this date", "color": BLUE}
        
        resolved_col = "Issue Resolved"
        if resolved_col not in sub.columns:
             return {"value": "Error", "desc": "Issue Resolved column not found", "color": RED}
             
        # Us din ki total machines vs resolved (TRUE) machines
        is_resolved = sub[resolved_col].astype(str).str.strip().str.upper() == "TRUE"
        total = len(sub)
        resolved = is_resolved.sum()
        
        pct = (resolved / total) * 100
        return {"value": f"{pct:.1f}%", "desc": f"{resolved} of {total} resolved on this date", "color": BLUE}

    # ==========================================PRODUCTION MATRIX==========================================

    if spec.get("calc") == "prod_matrix":
        # Matrix mapping clean check execution
        matrix_df, dates = parse_production_matrix(df)
        # Match horizontal string date format
        day_str = day.strftime("%d-%b-%y") if hasattr(day, "strftime") else str(day)
        sub_df = matrix_df[matrix_df["Date"].str.lower().str.contains(day_str.lower(), na=False)]
        
        if sub_df.empty:
            return {"value": "0.00", "desc": "No Transactions on Date", "color": None}
            
        t = spec.get("type")
        if t == "total":
            return {"value": f"{sub_df['ActualProduction'].sum():,.0f} Units", "desc": f"Plant Eff: {sub_df['Efficiency'].mean():.1f}%", "color": None}
        elif t == "bdls":
            b_df = sub_df[sub_df["UnitType"].str.lower().str.contains("bdls|bundle", na=False)]
            return {"value": f"{b_df['ActualProduction'].sum():,.0f} Bdls", "desc": f"Yield: {b_df['Efficiency'].mean():.1f}%", "color": None}
        elif t == "rolls":
            r_df = sub_df[sub_df["UnitType"].str.lower().str.contains("rolls|mtr", na=False)]
            return {"value": f"{r_df['ActualProduction'].sum():,.0f} Rolls", "desc": f"Yield: {r_df['Efficiency'].mean():.1f}%", "color": None}
        elif t == "mattress":
            m_df = sub_df[sub_df["Shed"].str.lower().str.contains("mattress|quilt|shed h", na=False)]
            return {"value": f"{m_df['ActualProduction'].sum():,.0f} Pcs", "desc": f"Shed Eff: {m_df['Efficiency'].mean():.1f}%", "color": None}
        elif t == "pillow":
            p_df = sub_df[sub_df["Shed"].str.lower().str.contains("pillow|shed k", na=False)]
            return {"value": f"{p_df['ActualProduction'].sum():,.0f} Pcs", "desc": f"Shed Eff: {p_df['Efficiency'].mean():.1f}%", "color": None}
        elif t == "rollpack":
            rp_df = sub_df[sub_df["Shed"].str.lower().str.contains("rollpack|peeling|shed b", na=False)]
            return {"value": f"{rp_df['ActualProduction'].sum():,.0f} Units", "desc": f"Shed Eff: {rp_df['Efficiency'].mean():.1f}%", "color": None}
# ==========================================PURCHASE==========================================
    if calc == "po_pending":
        r = po_pending(df, day, spec.get("columns"))
        if r is None:
            return None
        uom = " · ".join(f"{u or '?'} {q:,.0f}" for u, q in r["qty_by_uom"].items())
        return {"value": f"{r['open_pos']:,} POs", "desc": uom or "Nothing outstanding", "color": None}
    if calc == "purchase_mtd":
        r = purchase_mtd(df, day, spec.get("columns"), spec.get("basis", "received"))
        if r is None:
            return None
        out = {"value": _inr(r["value"]), "desc": None, "color": None}
        if r["warn_items"]:
            out["desc"] = "⚠ mixed-currency rates: " + ", ".join(r["warn_items"][:3])
            out["color"] = AMBER
        return out
   # ==========================================
    # 5. FALLBACK
    # ========================================== 
    v = compute(df, spec, day)
    return None if v is None else {"value": v, "desc": None, "color": None}
    


def parse_production_matrix(df):
    """
    Processes horizontal grid sheets where columns represent dates dynamically.
    Handles merged cells (where date appears only once, but production spans 3 columns).
    """
    if df.empty or len(df) < 3:
        return pd.DataFrame(), []
    
    df = df.dropna(how='all').reset_index(drop=True)
    first_row = df.iloc[0].astype(str).str.strip().tolist()
    second_row = df.iloc[1].astype(str).str.strip().tolist()
    
    date_columns = {}
    current_date = None
    
    for idx, cell in enumerate(first_row):
        # If the cell contains a date pattern like "1-Oct-26"
        if cell and re.search(r'\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4}', cell):
            current_date = cell
        # If the cell is blank but current_date is set (merged cell logic), retain current_date
            
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
                # Clean the values
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
    # Add more tabs/sheets here, each with ITS OWN date_col.
     "production_logs": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vS-f8spNA_4dJLh7yGuzJdESA9D9eKfBEtYH3d-aI6vgc50qkwM__cbrk6wU0pRmg/pubhtml",
        "worksheet": "0",
        "date_col": "col_1", # Default fallback placeholder row
        "dayfirst": True
    },

    "maintenance_logs": {
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTrPocQhFp-3kIL0QhVYFzIrkD5Wd5QmoShNK3i08MZSx4Wu59y25d0uo687C71guf3vc5FdNcM56_H/pubhtml",
        "worksheet": "0",          
        "date_col": "Breakdown Date", 
        "dayfirst": True
    }
}

# ====================================================================
# 5b. KPI_SOURCES  (key = (department key, KPI title exactly as on screen))
# ====================================================================
KPI_SOURCES = {
    # Open POs (count) as of the selected date; description line shows the
    # outstanding quantity per unit (PCS / KGS / MTR).
    ("purchase", "Pending PO"): {
        "sheet": "purchase_po",
        "mode": "as_of",
        "calc": "po_pending",
    },
    # Value of goods received from the 1st of the month up to the selected date
    # = sum(Inv Qty x Invoice Rate) by Recd Date.  Change "basis" to "po" to use
    # PO value instead (sum(PO Qty x PO Rate) by PO Date).
    ("purchase", "Purchase Till Date"): {
        "sheet": "purchase_po",
        "mode": "month",
        "date_label": "month to",
        "calc": "purchase_mtd",
        "basis": "received",
    },
        # Production Department ke saare blocks ki live binding:
    ("production", "Total Production & Yield"): {"sheet": "production_logs", "calc": "prod_matrix", "type": "total"},
    ("production", "Bdls & Yield"): {"sheet": "production_logs", "calc": "prod_matrix", "type": "bdls"},
    ("production", "Rolls & Yield"): {"sheet": "production_logs", "calc": "prod_matrix", "type": "rolls"},
    ("production", "Mattress & Yield"): {"sheet": "production_logs", "calc": "prod_matrix", "type": "mattress"},
    ("production", "Pillow & Yield"): {"sheet": "production_logs", "calc": "prod_matrix", "type": "pillow"},
    ("production", "Rollpack & Yield"): {"sheet": "production_logs", "calc": "prod_matrix", "type": "rollpack"},

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
            ("📋 Plant Logs Register (Google Sheets)", "https://docs.google.com/spreadsheets/d/e/2PACX-1vS-f8spNA_4dJLh7yGuzJdESA9D9eKfBEtYH3d-aI6vgc50qkwM__cbrk6wU0pRmg/pubhtml"),
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
            ("📊 Freight Report (Power BI)", "https://app.powerbi.com/groups/me/reports/43dfa27d-52db-4423-b40d-2732870ef9f2/d02bed28a39f2f8e3034?experience=power-bi"),
            ("📋 Safety & Quality Log (Google Sheets)", None),
            ("📊 Customer Target vs Sale (Power BI)", None),
        ],
    },
]


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


def get_sheet(name):
    """-> (DataFrame or None, error text or None, fetched-at or None)."""
    cfg = SHEETS.get(name)
    if not cfg or not cfg.get("url"):
        return None, f"sheet '{name}' has no link in SHEETS", None
    errors = st.session_state.setdefault("_errors", {})
    good = st.session_state.setdefault("_last_good", {})
    try:
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


def _card(slot, title, value, desc, color, date_text=None, error=False):
    date_html = f'<div class="kpi-date">📅 {date_text}</div>' if date_text else ""
    safe = str(desc).replace('"', "'").replace("<", "&lt;")
    desc_html = (f'<div class="kpi-err" style="color:{color};" title="{safe}">{safe}</div>' if error else
                 f'<div class="kpi-desc" style="color:{color};" title="{safe}">{safe}</div>')
    slot.markdown(
        f"""
        <div class="kpi-wrap">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        {date_html}
        {desc_html}
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

            dates = available_dates(df)          # real dates found in THIS KPI's own source
            chosen = st.selectbox(
                f"{title} date", dates, key=key, label_visibility="collapsed",
                format_func=lambda d: d.strftime(DATE_FMT),
            )
            prefix = spec.get("date_label", "as of" if spec.get("mode") == "as_of" else "")
            label = f"{prefix} {chosen.strftime(DATE_FMT)}".strip()
            try:
                res = compute_kpi(df, spec, chosen)
            except Exception as exc:
                log.exception("KPI %s/%s failed", dept_key, title)
                _card(slot, title, "Config error", f"{type(exc).__name__}: {exc}", RED, label, error=True)
                return

            if res is None:
                _card(slot, title, "No Data Available for This Date", desc, GREY, chosen.strftime(DATE_FMT))
            elif err:
                _card(slot, title, res["value"], f"⚠ Stale: last updated {fetched:%d-%m %H:%M}", AMBER, label)
            else:
                _card(slot, title, res["value"], res["desc"] or desc, res["color"] or BLUE, label)
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
