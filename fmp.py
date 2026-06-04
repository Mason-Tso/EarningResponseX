"""Financial Modeling Prep data layer.

Pulls everything relevant to an earnings reaction from FMP's `/stable` API and
bundles it into a single dict the writer can hand to Claude. The headline beat
and the YoY/QoQ deltas are computed here (in Python) so the numbers in the post
are never the model's arithmetic.
"""

from __future__ import annotations

import requests

BASE = "https://financialmodelingprep.com/stable"

# Map the textual fiscal period ("Q3") to the numeric quarter the transcript
# endpoint wants ("3").
_PERIOD_TO_NUM = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}


class FMPError(RuntimeError):
    """Raised when FMP returns an error payload or no usable data."""


def _get(endpoint: str, params: dict, api_key: str):
    params = {**params, "apikey": api_key}
    resp = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and ("Error Message" in data or "error" in data):
        raise FMPError(data.get("Error Message") or data.get("error"))
    return data


# --- individual endpoints -------------------------------------------------


def get_profile(symbol: str, api_key: str) -> dict | None:
    data = _get("profile", {"symbol": symbol}, api_key)
    return data[0] if data else None


def get_earnings(symbol: str, api_key: str, limit: int = 12) -> list[dict]:
    return _get("earnings", {"symbol": symbol, "limit": limit}, api_key)


def get_income_statements(symbol: str, api_key: str, limit: int = 6) -> list[dict]:
    return _get(
        "income-statement",
        {"symbol": symbol, "period": "quarter", "limit": limit},
        api_key,
    )


def get_analyst_estimates(symbol: str, api_key: str, limit: int = 4) -> list[dict]:
    return _get(
        "analyst-estimates",
        {"symbol": symbol, "period": "quarter", "limit": limit},
        api_key,
    )


def get_key_metrics(symbol: str, api_key: str, limit: int = 4) -> list[dict]:
    return _get(
        "key-metrics",
        {"symbol": symbol, "period": "quarter", "limit": limit},
        api_key,
    )


def get_ratios(symbol: str, api_key: str, limit: int = 4) -> list[dict]:
    return _get(
        "ratios",
        {"symbol": symbol, "period": "quarter", "limit": limit},
        api_key,
    )


def get_transcript(symbol: str, year: int, quarter: int, api_key: str) -> dict | None:
    data = _get(
        "earning-call-transcript",
        {"symbol": symbol, "year": year, "quarter": quarter},
        api_key,
    )
    return data[0] if data else None


def get_press_releases(symbol: str, api_key: str, limit: int = 3) -> list[dict]:
    try:
        return _get(
            "news/press-releases",
            {"symbols": symbol, "limit": limit},
            api_key,
        )
    except (FMPError, requests.HTTPError):
        return []


# --- derived computations -------------------------------------------------


def _pct_change(new, old):
    if new is None or old is None or old == 0:
        return None
    return (new - old) / abs(old) * 100.0


def _beat_pct(actual, estimate):
    if actual is None or estimate is None or estimate == 0:
        return None
    return (actual - estimate) / abs(estimate) * 100.0


def _reported_rows(earnings: list[dict]) -> list[dict]:
    """Earnings rows that have actuals, newest first."""
    rows = [e for e in earnings if e.get("epsActual") is not None]
    rows.sort(key=lambda e: e.get("date", ""), reverse=True)
    return rows


def _derive(reported_rows: list[dict]) -> dict:
    """Headline beat + YoY/QoQ from the reported-earnings (adjusted) series."""
    if not reported_rows:
        raise FMPError("No reported earnings with actuals found for this ticker.")

    latest = reported_rows[0]
    prev_q = reported_rows[1] if len(reported_rows) > 1 else None
    year_ago = reported_rows[4] if len(reported_rows) > 4 else None

    eps_a = latest.get("epsActual")
    eps_e = latest.get("epsEstimated")
    rev_a = latest.get("revenueActual")
    rev_e = latest.get("revenueEstimated")

    return {
        "date": latest.get("date"),
        "eps_actual": eps_a,
        "eps_estimated": eps_e,
        "eps_beat_pct": _beat_pct(eps_a, eps_e),
        "eps_beat": (eps_a is not None and eps_e is not None and eps_a >= eps_e),
        "revenue_actual": rev_a,
        "revenue_estimated": rev_e,
        "revenue_beat_pct": _beat_pct(rev_a, rev_e),
        "revenue_beat": (rev_a is not None and rev_e is not None and rev_a >= rev_e),
        "eps_qoq_pct": _pct_change(eps_a, prev_q.get("epsActual")) if prev_q else None,
        "eps_yoy_pct": _pct_change(eps_a, year_ago.get("epsActual")) if year_ago else None,
        "revenue_qoq_pct": _pct_change(rev_a, prev_q.get("revenueActual")) if prev_q else None,
        "revenue_yoy_pct": _pct_change(rev_a, year_ago.get("revenueActual")) if year_ago else None,
        "prev_quarter_date": prev_q.get("date") if prev_q else None,
        "year_ago_date": year_ago.get("date") if year_ago else None,
    }


# --- the one call the CLI uses -------------------------------------------


def gather(symbol: str, api_key: str, include_transcript: bool = True) -> dict:
    """Collect and bundle all relevant data for `symbol`'s latest report."""
    symbol = symbol.upper().strip()

    earnings = get_earnings(symbol, api_key)
    reported = _reported_rows(earnings)
    derived = _derive(reported)

    # Fiscal year/quarter for the transcript come from the matching income
    # statement (the earnings endpoint doesn't expose fiscal period labels).
    income = []
    fiscal_year = None
    fiscal_quarter_num = None
    try:
        income = get_income_statements(symbol, api_key)
        if income:
            top = income[0]
            fiscal_year = int(top.get("fiscalYear")) if top.get("fiscalYear") else None
            fiscal_quarter_num = _PERIOD_TO_NUM.get(top.get("period"))
    except (FMPError, requests.HTTPError):
        pass

    transcript = None
    if include_transcript and fiscal_year and fiscal_quarter_num:
        try:
            transcript = get_transcript(symbol, fiscal_year, fiscal_quarter_num, api_key)
        except (FMPError, requests.HTTPError):
            transcript = None

    def _safe(fn, *args):
        try:
            return fn(*args)
        except (FMPError, requests.HTTPError):
            return []

    return {
        "symbol": symbol,
        "profile": _safe(get_profile, symbol, api_key) or None,
        "reported": derived,
        "fiscal": {
            "year": fiscal_year,
            "period": income[0].get("period") if income else None,
        },
        "earnings_series": reported[:8],
        "income_statements": income,
        "key_metrics": _safe(get_key_metrics, symbol, api_key),
        "ratios": _safe(get_ratios, symbol, api_key),
        "analyst_estimates": _safe(get_analyst_estimates, symbol, api_key),
        "transcript": transcript,
        "press_releases": _safe(get_press_releases, symbol, api_key),
    }
