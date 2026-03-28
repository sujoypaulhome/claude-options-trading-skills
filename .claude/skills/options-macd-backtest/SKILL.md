---
name: options-macd-backtest
description: Run, analyze, or improve the MACD-based options credit spread backtest. Covers signal generation (cross + exhaustion), EOD put spread entries, and interpreting results. Use when the user wants to backtest, tune parameters, or add a new ticker.
argument-hint: [run|analyze|add-ticker] [symbol]
---

# MACD Options Credit Spread Backtest

## Files
- Backtest: `C:/Users/sujoy/gex_march_26/total_options.py`
- Live signals: `C:/Users/sujoy/gex_march_26/combined_live/momentum_follow.py`
- Both must stay in sync when signal logic changes.

---

## Action: `$ARGUMENTS`

Parse the first word: `run` | `analyze` | `add-ticker`

---

## Running the Backtest

```bash
cd C:/Users/sujoy/gex_march_26
python total_options.py
```

Output: per-ticker trade log + summary table with WR%, total P&L, avg P&L/trade.

---

## Signal Architecture

### Two Signal Types

**1. MACD Cross** (lags by 1 bar)
- `regime` switches BULL→BEAR → `SELL_CALL_SPREAD` signal
- `regime` switches BEAR→BULL → `SELL_PUT_SPREAD` signal
- Entry fires the next bar (T+1 follow-through confirmation)

**2. MACD Exhaustion** (leads the cross by 1-2 bars — the edge)
- `bull_exhaust`: histogram peaked while in BULL regime → early SELL_CALL_SPREAD
- `bear_exhaust`: histogram troughed while in BEAR regime → early SELL_PUT_SPREAD
- Detection: `hist[i-1] > hist[i-2]` and `hist[i-1] > 0` (for bull peak)

```python
def compute_macd_full(daily_bars, fast=12, slow=26, sig=9) -> pd.DataFrame:
    close = daily_bars["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=sig, adjust=False).mean()
    histogram = macd_line - signal_line
    regime = pd.Series("BEAR", index=daily_bars.index)
    regime[macd_line > signal_line] = "BULL"
    return pd.DataFrame({"regime": regime, "macd_line": macd_line,
                         "signal_line": signal_line, "histogram": histogram})
```

### Entry Timing Split

**CRITICAL**: Call spreads and put spreads use different entry prices.

| Signal | Entry time | Price used |
|---|---|---|
| SELL_CALL_SPREAD | 10:00 AM ET | `open` price |
| SELL_PUT_SPREAD | 3:00 PM ET (EOD) | `close` price |

Rationale: put spreads enter EOD to capture the full day's bearish move and position for the next day. This is a bearish-year strategy — we want to enter puts at end of day when selling pressure has peaked.

In `simulate_trade_morning_check()`:
```python
price_col = "close" if signal.trade_type == "SELL_PUT_SPREAD" else "open"
```

---

## Interpreting Results

Key metrics per ticker:

| Metric | What it means |
|---|---|
| WR% | Win rate — above 75% is good for credit spreads |
| Avg P&L | Average profit per trade including commissions |
| Total P&L | Cumulative — use to compare configs |
| Trades | More trades = more statistical confidence |

**Benchmark results (2024-2026, after exhaustion + EOD fix):**
- Overall: 83 trades, WR=86.7%, Total=$5,612
- IWM: 86% WR, +$485
- SELL_PUT_SPREAD: 79% WR (up from 71% before EOD entry fix)

---

## Adding a New Ticker

1. Add to `FIXED_TICKERS` dict in `combined_live.py`:
```python
"TICKER_MACD": {
    "symbol": "TICKER",
    "regime_method": "MACD",
    "spread_width": 5,
    "min_credit": 0.50,
    "max_rr": 4.0,
    "tp_pct": 0.50,
    "sl_pct": 1.0,
    "dte_target": 7,
    "contracts": 1,
}
```

2. Run backtest and check WR% and total P&L
3. If WR < 70% or avg P&L < $20/trade → don't add to live
4. Add the same config to `total_options.py` `FIXED_TICKERS`

---

## Tuning Parameters

| Parameter | Effect | Typical range |
|---|---|---|
| `spread_width` | Max loss, min credit | 3–10 |
| `min_credit` | Floor for entry — use 10% of width | 0.30–0.50 |
| `tp_pct` | Take-profit target | 0.50–0.70 (live: 0.70) |
| `sl_pct` | Stop-loss multiplier | 1.5–2.5x credit |
| `dte_target` | Days to expiry at entry | 5–10 |
| MACD fast/slow/sig | Signal sensitivity | 12/26/9 (standard) |

**Rule**: backtest first. Only tune one parameter at a time. Measure WR% and total P&L.

---

## Keeping Backtest and Live in Sync

After any signal logic change in `total_options.py` / `momentum_follow.py`:
- Apply the same change to the other file
- `generate_signals_macd()` must be identical in both
- `simulate_trade_morning_check()` entry price logic must match live execution timing
