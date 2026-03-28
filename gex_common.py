"""
GEX Common — Shared utilities for the live scanner and backtest.
================================================================
Polygon API helpers, bar fetching, ATR, option pricing, GEX walls,
and 0DTE schedule constants.

Usage:
    import gex_common
    gex_common.init("YOUR_POLYGON_API_KEY")
    # then call gex_common.fetch_5min_bars(...) etc.
"""

import time
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests


# ============================================================================
# Module-level state (set once via init())
# ============================================================================

_API_KEY: str = ""
_BASE: str = "https://api.polygon.io"


def init(api_key: str, base_url: str = "https://api.polygon.io"):
    """Initialize the module with a Polygon API key."""
    global _API_KEY, _BASE
    _API_KEY = api_key
    _BASE = base_url


# ============================================================================
# 0DTE Schedule Constants
# ============================================================================

DAILY_0DTE = {"SPY", "QQQ", "IWM"}
MWF_0DTE = {"TSLA", "NVDA", "AMZN", "META", "AAPL", "MSFT", "AVGO", "GOOGL", "IBIT"}


def has_0dte(symbol: str, trade_date: date = None) -> bool:
    """Check whether symbol has a 0DTE expiration on the given date (default: today)."""
    if trade_date is None:
        trade_date = date.today()
    dow = trade_date.weekday()
    if symbol in DAILY_0DTE:
        return dow < 5
    if symbol in MWF_0DTE:
        return dow in (0, 2, 4)
    return dow == 4  # Friday only


# ============================================================================
# Polygon HTTP Helpers (with 429 retry)
# ============================================================================

def poly_get(url: str, params: Dict = None) -> Dict:
    """GET with Polygon API key injection and 429 retry (5 attempts)."""
    if params is None:
        params = {}
    params["apiKey"] = _API_KEY
    last = None
    for attempt in range(5):
        r = requests.get(url, params=params, timeout=30)
        last = r
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                pass
        if r.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"    Rate limited, waiting {wait}s...")
            time.sleep(wait)
        else:
            time.sleep(1)
    raise RuntimeError(f"Polygon GET failed {last.status_code}: {last.text[:200]}")


def poly_next(next_url: str) -> Dict:
    """Follow Polygon pagination next_url with retry."""
    if "apiKey=" not in next_url:
        sep = "&" if "?" in next_url else "?"
        next_url = f"{next_url}{sep}apiKey={_API_KEY}"
    last = None
    for attempt in range(5):
        r = requests.get(next_url, timeout=30)
        last = r
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                pass
        if r.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"    Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        time.sleep(1)
    raise RuntimeError(f"Polygon NEXT failed {last.status_code}: {last.text[:200]}")


# ============================================================================
# Price & Expiration
# ============================================================================

def get_underlying_price(symbol: str) -> Optional[float]:
    """Best-effort latest stock/ETF price (tries trades → snapshot → prev close)."""
    try:
        js = poly_get(f"{_BASE}/v3/trades/{symbol}",
                      {"limit": 1, "sort": "timestamp", "order": "desc"})
        res = js.get("results") or []
        if res:
            px = res[0].get("price") or res[0].get("p")
            if px is not None and np.isfinite(float(px)):
                return float(px)
    except Exception:
        pass
    try:
        js = poly_get(
            f"{_BASE}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}")
        tkr = js.get("ticker") or {}
        p = ((tkr.get("lastTrade") or {}).get("p")
             or (tkr.get("day") or {}).get("c")
             or (tkr.get("prevDay") or {}).get("c"))
        if p is not None and np.isfinite(float(p)):
            return float(p)
    except Exception:
        pass
    try:
        js = poly_get(f"{_BASE}/v2/aggs/ticker/{symbol}/prev")
        res = js.get("results") or []
        if res and res[0].get("c") is not None:
            return float(res[0]["c"])
    except Exception:
        pass
    return None


def nearest_expiration(symbol: str, min_dte: int = 0, max_dte: int = 7) -> Optional[str]:
    """Find the nearest option expiration date within [min_dte, max_dte]."""
    today = date.today()
    params = {
        "underlying_ticker": symbol,
        "expired": "false",
        "order": "asc",
        "sort": "expiration_date",
        "limit": 1000,
    }
    data = poly_get(f"{_BASE}/v3/reference/options/contracts", params)
    exps = set()
    while True:
        for it in data.get("results", []) or []:
            exp = it.get("expiration_date")
            if exp:
                exps.add(exp)
        nxt = data.get("next_url")
        if not nxt:
            break
        data = poly_next(nxt)

    if not exps:
        return None

    candidates = []
    for e in sorted(exps):
        dte = (date.fromisoformat(e) - today).days
        if min_dte <= dte <= max_dte:
            candidates.append((dte, e))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    # fallback: nearest overall
    all_sorted = sorted(
        [(abs((date.fromisoformat(e) - today).days), e) for e in exps],
        key=lambda x: x[0],
    )
    return all_sorted[0][1] if all_sorted else None


# ============================================================================
# Option Helpers
# ============================================================================

def build_occ_ticker(symbol: str, expiry: date, option_type: str,
                     strike: float) -> str:
    """Build OCC-format option ticker. option_type: 'C' or 'P'."""
    exp_str = expiry.strftime("%y%m%d")
    strike_int = int(strike * 1000)
    return f"O:{symbol}{exp_str}{option_type}{strike_int:08d}"


def fetch_option_price(symbol: str, expiry: date, option_type: str,
                       strike: float, signal_time: str) -> Optional[float]:
    """Fetch option price near signal_time from 5-min aggregate bars."""
    occ = build_occ_ticker(symbol, expiry, option_type, strike)
    date_str = expiry.isoformat()
    try:
        js = poly_get(
            f"{_BASE}/v2/aggs/ticker/{occ}/range/5/minute/{date_str}/{date_str}",
            {"adjusted": "true", "sort": "asc", "limit": 5000},
        )
    except RuntimeError:
        return None

    results = js.get("results") or []
    if not results:
        return None

    try:
        sig_dt = pd.Timestamp(signal_time)
        sig_epoch_ms = int(sig_dt.timestamp() * 1000)
    except Exception:
        return None

    best = None
    for bar in results:
        t = bar.get("t", 0)
        if t <= sig_epoch_ms:
            best = bar
        else:
            break

    if best is not None and best.get("c") is not None:
        return float(best["c"])
    return None


# ============================================================================
# Bar Fetching
# ============================================================================

def fetch_5min_bars(symbol: str, start_date: date,
                    end_date: date) -> pd.DataFrame:
    """Fetch 5-min bars with pagination, converted to America/New_York tz."""
    all_results = []
    js = poly_get(
        f"{_BASE}/v2/aggs/ticker/{symbol}/range/5/minute/{start_date}/{end_date}",
        {"adjusted": "true", "sort": "asc", "limit": 50000},
    )
    all_results.extend(js.get("results") or [])
    while js.get("next_url"):
        js = poly_next(js["next_url"])
        all_results.extend(js.get("results") or [])

    if not all_results:
        return pd.DataFrame()

    df = pd.DataFrame(all_results)
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df["t"] = df["t"].dt.tz_convert("America/New_York")
    df = df.rename(columns={"o": "open", "h": "high", "l": "low",
                             "c": "close", "v": "volume"})
    df = df.set_index("t")
    df = df[["open", "high", "low", "close", "volume"]].copy()
    return df


def fetch_daily_bars(symbol: str, start_date: date,
                     end_date: date) -> pd.DataFrame:
    """Fetch daily OHLCV bars with pagination. Index is date (no tz)."""
    all_results = []
    js = poly_get(
        f"{_BASE}/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}",
        {"adjusted": "true", "sort": "asc", "limit": 50000},
    )
    all_results.extend(js.get("results") or [])
    while js.get("next_url"):
        js = poly_next(js["next_url"])
        all_results.extend(js.get("results") or [])

    if not all_results:
        return pd.DataFrame()

    df = pd.DataFrame(all_results)
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.date
    df = df.rename(columns={"o": "open", "h": "high", "l": "low",
                             "c": "close", "v": "volume"})
    df = df.set_index("t")
    return df[["open", "high", "low", "close", "volume"]].copy()


# ============================================================================
# ATR
# ============================================================================

def compute_atr(bars: pd.DataFrame, periods: int = 14) -> pd.Series:
    """ATR using True Range on OHLC bars."""
    high = bars["high"]
    low = bars["low"]
    prev_close = bars["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=periods, min_periods=periods).mean()


# ============================================================================
# Williams %R
# ============================================================================

def compute_williams_r(bars: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    Williams %R from OHLC bars.

    Formula:
        %R = (Highest High over window - Close) / (Highest High - Lowest Low) * -100

    Range: -100 (most oversold) to 0 (most overbought).
    Standard thresholds:
        Overbought : %R >= -20  (price near top of recent range)
        Oversold   : %R <= -80  (price near bottom of recent range)

    Args:
        bars   : DataFrame with columns [high, low, close]. Any timeframe.
        window : Lookback period. Default 14 (standard Williams choice).

    Returns:
        pd.Series aligned to bars.index. NaN for first (window-1) rows.
    """
    highest_high = bars["high"].rolling(window=window, min_periods=window).max()
    lowest_low   = bars["low"].rolling(window=window, min_periods=window).min()
    wr = (highest_high - bars["close"]) / (highest_high - lowest_low) * -100
    wr.name = f"williams_r_{window}"
    return wr


def fetch_williams_r(symbol: str, start_date: date, end_date: date,
                     window: int = 14) -> pd.Series:
    """
    Fetch daily bars for symbol and return Williams %R series.

    Fetches enough history to warm up the indicator (window extra days before
    start_date) so the returned series has valid values from start_date onward.

    Args:
        symbol     : Ticker, e.g. "SPY", "IWM", "O:IWM260402P00245000"
        start_date : First date you want valid %R values for.
        end_date   : Last date inclusive.
        window     : Lookback period (default 14).

    Returns:
        pd.Series of %R values indexed by date, trimmed to [start_date, end_date].
        Empty Series if Polygon returns no data.

    Example:
        wr = fetch_williams_r("IWM", date(2026, 1, 1), date(2026, 3, 28))
        latest = wr.iloc[-1]   # today's %R
        if latest <= -80:
            print("Oversold — consider put spread entry")
    """
    # Pull extra history so window warms up cleanly
    warmup_start = start_date - timedelta(days=window * 2)
    bars = fetch_daily_bars(symbol, warmup_start, end_date)
    if bars.empty:
        return pd.Series(dtype=float, name=f"williams_r_{window}")

    wr = compute_williams_r(bars, window=window)
    # Trim to requested range
    return wr.loc[wr.index >= start_date]


# ============================================================================
# Relative Volume (RVOL)
# ============================================================================

def compute_rvol(bars: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Relative Volume = current bar volume / rolling average volume over window bars.

    RVOL > 1.0  : above-average volume
    RVOL > 1.5  : elevated — institutional interest likely
    RVOL > 2.0  : high conviction — strong signal confirmation
    RVOL < 0.8  : low volume — treat any signal with suspicion

    Args:
        bars   : DataFrame with a 'volume' column. Any timeframe.
        window : Lookback for average volume. Default 20 (1 trading month).

    Returns:
        pd.Series aligned to bars.index. NaN for first (window-1) rows.
    """
    avg_vol = bars["volume"].rolling(window=window, min_periods=window).mean()
    rvol = bars["volume"] / avg_vol
    rvol.name = f"rvol_{window}"
    return rvol


def fetch_rvol(symbol: str, start_date: date, end_date: date,
               window: int = 20) -> pd.Series:
    """Fetch daily bars and return RVOL series, warmed up from start_date."""
    warmup_start = start_date - timedelta(days=window * 2)
    bars = fetch_daily_bars(symbol, warmup_start, end_date)
    if bars.empty:
        return pd.Series(dtype=float, name=f"rvol_{window}")
    rvol = compute_rvol(bars, window=window)
    return rvol.loc[rvol.index >= start_date]


# ============================================================================
# Williams %R + RVOL Combined Signals
# ============================================================================

def williams_r_rvol_signal(
    bars: pd.DataFrame,
    wr_window: int = 14,
    rvol_window: int = 20,
    rvol_threshold: float = 1.5,
    oversold: float = -80.0,
    overbought: float = -20.0,
    midline: float = -50.0,
) -> pd.DataFrame:
    """
    Combine Williams %R and RVOL into three signal types per bar.

    Signal types
    ────────────
    BREAKOUT_BULL
        %R crossed UP through midline (-50) from oversold (<= -80) on high RVOL.
        Previous bar %R <= oversold, current bar %R > midline, RVOL >= threshold.
        Interpretation: strong bullish reversal confirmed by volume.

    BREAKOUT_BEAR
        %R crossed DOWN through midline from overbought (>= -20) on high RVOL.
        Previous bar %R >= overbought, current bar %R < midline, RVOL >= threshold.
        Interpretation: strong bearish reversal confirmed by volume.

    CONTINUATION_BULL
        Price in established uptrend (%R between midline and overbought: -50 to -20),
        slight pullback (%R dipped vs prior bar but stays above oversold),
        RVOL >= threshold.
        Interpretation: dip within an uptrend — bulls buying the dip with conviction.

    CONTINUATION_BEAR
        Price in established downtrend (%R between oversold and midline: -80 to -50),
        slight bounce (%R rose vs prior bar but stays below overbought),
        RVOL >= threshold.
        Interpretation: bounce within a downtrend — bears adding on strength.

    WEAKENING_BULL
        Price makes a new 14-bar high but %R is LOWER than 2 bars ago, RVOL < 1.0.
        Interpretation: higher price on less momentum + shrinking volume → reversal risk.

    WEAKENING_BEAR
        Price makes a new 14-bar low but %R is HIGHER than 2 bars ago, RVOL < 1.0.
        Interpretation: lower price on less downside momentum + shrinking volume → reversal risk.

    Args:
        bars            : DataFrame with [open, high, low, close, volume]. Any timeframe.
        wr_window       : Williams %R lookback (default 14).
        rvol_window     : RVOL average window (default 20).
        rvol_threshold  : Minimum RVOL to confirm a breakout/continuation (default 1.5).
        oversold        : %R threshold for oversold zone (default -80).
        overbought      : %R threshold for overbought zone (default -20).
        midline         : %R midline used for breakout cross detection (default -50).

    Returns:
        DataFrame with columns [close, wr, rvol, signal] aligned to bars.index.
        'signal' is a string: one of the six types above, or '' (no signal).
        Multiple signals on the same bar are joined with '|'.
    """
    wr   = compute_williams_r(bars, window=wr_window)
    rvol = compute_rvol(bars, window=rvol_window)

    prev_wr    = wr.shift(1)
    prev2_wr   = wr.shift(2)
    high_roll  = bars["high"].rolling(window=wr_window).max()
    low_roll   = bars["low"].rolling(window=wr_window).min()
    prev_high  = high_roll.shift(1)
    prev_low   = low_roll.shift(1)

    signals = []
    for i in range(len(bars)):
        sig_parts = []

        curr_wr   = wr.iloc[i]
        prev_wr_v = prev_wr.iloc[i]
        p2_wr     = prev2_wr.iloc[i]
        curr_rv   = rvol.iloc[i]
        curr_cl   = bars["close"].iloc[i]
        curr_hi   = bars["high"].iloc[i]
        curr_lo   = bars["low"].iloc[i]
        ph        = prev_high.iloc[i]
        pl        = prev_low.iloc[i]

        if any(np.isnan(v) for v in [curr_wr, prev_wr_v, p2_wr, curr_rv]):
            signals.append("")
            continue

        high_vol = curr_rv >= rvol_threshold
        low_vol  = curr_rv < 0.8

        # --- BREAKOUT signals ---
        if prev_wr_v <= oversold and curr_wr > midline and high_vol:
            sig_parts.append("BREAKOUT_BULL")
        if prev_wr_v >= overbought and curr_wr < midline and high_vol:
            sig_parts.append("BREAKOUT_BEAR")

        # --- CONTINUATION signals ---
        # Bull continuation: %R in uptrend zone, dipped slightly, high volume
        if (midline < curr_wr <= overbought
                and prev_wr_v > curr_wr          # slight pullback in %R
                and curr_wr > oversold            # not fallen into oversold
                and high_vol):
            sig_parts.append("CONTINUATION_BULL")

        # Bear continuation: %R in downtrend zone, bounced slightly, high volume
        if (oversold <= curr_wr < midline
                and prev_wr_v < curr_wr          # slight bounce in %R
                and curr_wr < overbought          # not bounced into overbought
                and high_vol):
            sig_parts.append("CONTINUATION_BEAR")

        # --- WEAKENING signals ---
        # Bull weakening: new price high but %R diverges lower, shrinking volume
        if (not np.isnan(ph)
                and curr_hi > ph                 # price new high
                and curr_wr < p2_wr              # %R lower than 2 bars ago
                and low_vol):
            sig_parts.append("WEAKENING_BULL")

        # Bear weakening: new price low but %R diverges higher, shrinking volume
        if (not np.isnan(pl)
                and curr_lo < pl                 # price new low
                and curr_wr > p2_wr              # %R higher than 2 bars ago (less negative)
                and low_vol):
            sig_parts.append("WEAKENING_BEAR")

        signals.append("|".join(sig_parts))

    result = pd.DataFrame({
        "close": bars["close"].values,
        "wr":    wr.values,
        "rvol":  rvol.values,
        "signal": signals,
    }, index=bars.index)
    return result


def fetch_williams_r_rvol(symbol: str, start_date: date, end_date: date,
                           wr_window: int = 14, rvol_window: int = 20,
                           rvol_threshold: float = 1.5) -> pd.DataFrame:
    """
    Convenience wrapper: fetch daily bars and return full signal DataFrame.

    Returns columns [close, wr, rvol, signal] trimmed to [start_date, end_date].
    """
    warmup_days  = max(wr_window, rvol_window) * 3
    warmup_start = start_date - timedelta(days=warmup_days)
    bars = fetch_daily_bars(symbol, warmup_start, end_date)
    if bars.empty:
        return pd.DataFrame(columns=["close", "wr", "rvol", "signal"])
    df = williams_r_rvol_signal(bars, wr_window=wr_window, rvol_window=rvol_window,
                                rvol_threshold=rvol_threshold)
    return df.loc[df.index >= start_date]


# ============================================================================
# GEX Wall Detection
# ============================================================================

def fetch_gex_walls(symbol: str) -> Optional[Dict]:
    """
    Fetch GEX walls from Polygon option chain snapshot (highest OI strikes).
    Returns dict: {spot, expiry, call_wall, next_call_wall, put_wall, next_put_wall}
    or None on failure.
    """
    exp = nearest_expiration(symbol)
    if not exp:
        print(f"    [{symbol}] No expiration found")
        return None

    params = {
        "expiration_date": exp,
        "order": "asc",
        "sort": "strike_price",
        "limit": 250,
    }
    data = poly_get(f"{_BASE}/v3/snapshot/options/{symbol}", params)
    contracts = []

    def parse_batch(js):
        for res in js.get("results", []) or []:
            details = res.get("details", {}) or {}
            typ = (details.get("contract_type")
                   or res.get("contract_type") or "").lower()
            strike = details.get("strike_price") or res.get("strike_price")
            oi = res.get("open_interest")
            if typ in ("call", "put") and strike is not None:
                contracts.append({
                    "strike": float(strike),
                    "type": typ,
                    "oi": float(oi) if oi is not None else 0.0,
                })

    parse_batch(data)
    while data.get("next_url"):
        data = poly_next(data["next_url"])
        parse_batch(data)

    if not contracts:
        print(f"    [{symbol}] No option contracts found")
        return None

    df = pd.DataFrame(contracts)
    calls = df[df["type"] == "call"].sort_values("oi", ascending=False)
    puts = df[df["type"] == "put"].sort_values("oi", ascending=False)

    spot = get_underlying_price(symbol)
    if spot is None:
        print(f"    [{symbol}] Could not get underlying price")
        return None

    result = {"spot": spot, "expiry": exp}

    if not calls.empty:
        result["call_wall"] = float(calls.iloc[0]["strike"])
        result["next_call_wall"] = float(calls.iloc[1]["strike"]) if len(calls) > 1 else result["call_wall"]
    else:
        result["call_wall"] = spot * 1.02
        result["next_call_wall"] = spot * 1.04

    if not puts.empty:
        result["put_wall"] = float(puts.iloc[0]["strike"])
        result["next_put_wall"] = float(puts.iloc[1]["strike"]) if len(puts) > 1 else result["put_wall"]
    else:
        result["put_wall"] = spot * 0.98
        result["next_put_wall"] = spot * 0.96

    print(f"    [{symbol}] CW={result['call_wall']:.0f} "
          f"(next={result['next_call_wall']:.0f}) | "
          f"PW={result['put_wall']:.0f} "
          f"(next={result['next_put_wall']:.0f}) | "
          f"Spot={spot:.2f} | Exp={exp}")
    return result
