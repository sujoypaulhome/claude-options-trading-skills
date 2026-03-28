---
name: tastytrade
description: Master TastyTrade options skill. Routes to the right workflow based on intent. Covers spread entry, EOD position check, TP updates, and MACD backtest. Just describe what you want to do.
argument-hint: [enter spread | check positions | update tp | backtest]
---

# TastyTrade Options — Master Skill

Read `$ARGUMENTS` and route to the correct workflow below.

| If the user wants to... | Go to |
|---|---|
| Enter / open a new spread | → **WORKFLOW A: Spread Entry** |
| Check / verify open positions and orders | → **WORKFLOW B: EOD Position Check** |
| Update / change / move take profit | → **WORKFLOW C: Update TP** |
| Run / analyze / tune the backtest | → **WORKFLOW D: MACD Backtest** |
| See open positions / account status | → **WORKFLOW B: EOD Position Check** |
| No arguments or unclear | → Ask: "Entry, position check, update TP, or backtest?" |

---

# OPTIONS TRADING STRATEGY

Three independent regimes run in parallel, combined into one equity curve.

**12-month combined result (Mar 2025 – Mar 2026): 148 trades, 77% WR, +$6,105**

---

## Core Philosophy

**High IV is the primary edge.**
When credit/width ratio is high, the market is paying well to take risk. The goal is MORE qualifying trades at good IV — not fewer perfectly-filtered trades.

**Law of large numbers IS the strategy.**
A 70% win rate on 20 trades is luck. A 70% win rate on 200 trades is a strategy. Over-filtering destroys the statistical edge.

**Risk/reward is the real gate at entry.**
If IV is acceptable AND R/R ≤ 4.0x, take the trade. Everything else (ATR, VSM) is a secondary veto — use sparingly.

**Key finding:** At `max_risk_reward=4.0`, the RR filter is the binding constraint — not the IV floor.
- RR ≤ 4.0 requires credit ≥ 20% of width
- IV floor at 10-15% is looser — all newly-passing IV trades still fail RR anyway
- IV floor is a sanity check; RR is the real gate

**RR calibration results:**

| max_risk_reward | Min credit required | Trades | WR | P&L |
|---|---|---|---|---|
| 2.5x | 28.6% | ~40 | 71.9% | +$1,168 |
| 5.0x | 16.7% | 72 | 76.4% | +$2,270 |
| **4.0x** | **20.0%** | **108** | **78.7%** | **+$4,088** |

**4.0x is the sweet spot.** Do not go below (fewer trades, marginal quality gain) or above (thin premium barely covers commissions).

---

## Method 1 — GEX Weekly: 3x Leveraged ETFs with Max IV/RR

**Universe:** TQQQ, SPXL (SOXL removed — near coin-flip WR)
**Expiry:** 1-week (Friday)
**Entry days:** Mon + Wed only

### Entry Logic

Entry requires ALL of the following to pass:

1. **IV Floor:** `credit / spread_width ≥ 15%`
   - Below 15%: not enough premium to survive one loss
   - No ceiling on IV — high IV is the point, not the problem

2. **Max Risk/Reward ≤ 2.5x**
   - `max_rr = (width - credit) / credit ≤ 2.5`
   - Never risk more than 2.5x the credit received

3. **VSM Veto (adverse direction only)**
   - VSM = Volatility-Scaled Momentum (daily returns ÷ ATR, 10-bar rolling)
   - `SELL_CALL_SPREAD` blocked only when VSM > +1.5 (strong bullish surge against calls)
   - `SELL_PUT_SPREAD` blocked only when VSM < -1.5 (strong bearish crash against puts)
   - VSM aligned with trade direction = NOT vetoed (selling calls in a downtrend is fine)
   - **Old VSM veto #2 (block all when |VSM|>1.5 regardless of direction) = REMOVED**
     — was blocking valid call spreads during downtrends

4. **Iron Condor when |VSM| < 0.5**
   - Low momentum = range-bound = sell BOTH call AND put spread simultaneously
   - Combined TP and SL on total credit
   - Result: 10 trades, 80% WR, +$319 in 6-month test
   - Doubles premium when market is genuinely stuck

5. **RR Scaling: 2x contracts when RR ≤ 1.0x**
   - When risk ≤ credit received → exceptionally favorable → double size
   - ⚠️ Known risk: doubling into adverse VSM (-1.64) caused -$580 single loss (SPXL Sep 2025)
   - Open question: require |VSM| < threshold before scaling?

### Strike Placement

Anchored at GEX walls (Volume Profile walls from Polygon options snapshot):
- Call spread short strike: at or above the GEX call wall
- Put spread short strike: at or below the GEX put wall
- **Near-wall placement IS the edge** — not a flaw. The wall IS the reversal point.
- VSM veto handles the case where price just ran through a wall (|VSM| will be high)

### 6-Month Results (Sep 2025 – Mar 2026, v5-full)

| Ticker | Trades | WR | P&L | Notes |
|---|---|---|---|---|
| TQQQ | 21 | 81% | +$566 | Best performer |
| NVDL | ~20 | 77% | ~+$300 | Consistent high IV |
| METU | ~17 | 76.5% | ~+$244 | — |
| SPXL | 10 | 60% | -$231 | Problem child — 2x scaling into adverse VSM |
| Iron Condors | 10 | 80% | +$319 | When |VSM| < 0.5 |
| Monthly companion | 9 | 88.9% | +$348 | 14 DTE, +$3 OTM |
| **Total** | **79** | **75.9%** | **+$1,081** | |

**Tuesday drag:** Mon=+$662, **Tue=-$599**, Wed=+$1,018. Most Tue damage is one -$580 SPXL trade. Not yet decisive — hold off before removing Tuesday.

### What Does NOT Work — Do Not Retry

| Filter | Result | Verdict |
|---|---|---|
| ATR filter (min ATR percentile) | Reduces count, no WR gain. High-IV filter already gates vol quality | **DO NOT RE-ADD** |
| ATR upper bound (skip >75th pctile) | TQQQ/SPXL/SOXL got 0 trades — leveraged ETFs live at high ATR | **DO NOT RETRY** |
| IV ceiling (skip >40% IV) | Filtered SPXL's best trades (48% IV). High IV = the point | **DO NOT RETRY** |
| min_otm_pct=1% (skip near-wall strikes) | 67→27 trades, WR 70%→55.6%, P&L +$1,260→-$157. Near-wall trades ARE winners | **DO NOT ADD** |
| min_otm_pct=2% | 67→5 trades, P&L -$49 | **DO NOT ADD** |
| Remove 50% TP on weeklies | WR 70%→55.6%, P&L +$1,260→+$501. NVDL reversed on 7 of 13 winners | **DO NOT RETRY** |
| SL = 2x credit | Losses run too far | **DO NOT REVERT** |

**Why the 50% TP matters:** It serves a dual role — captures profit AND protects against reversal. NVDL (2x NVDA) can fully reverse within a week. SPXL (SPY-based) improved without TP ($349→$520) but NVDL is far too volatile to hold.

---

## Method 2 — MACD Cross + Exhaustion: Regime-Anchored Spreads

**Universe:** QQQ, NVDA, IWM, TSLA
**Expiry:** 2 weeks out (min 6 days ahead, next available Friday)
**Check:** Daily morning open price (10AM proxy) — not intraday bars

### Two Signal Types

#### Signal A: MACD Cross (fires T+1 confirmation)

The MACD line (12-26 EMA) crossing the signal line (9-period EMA of MACD) = entry trigger.

```
BULL→BEAR cross → SELL_CALL_SPREAD at resistance
BEAR→BULL cross → SELL_PUT_SPREAD at support
Entry fires NEXT bar (T+1 follow-through confirmation — not the cross bar itself)
```

MACD as **entry trigger**, not a regime filter. Full stop.

#### Signal B: MACD Exhaustion (fires 1–2 bars BEFORE the cross — the edge)

Exhaustion detects when momentum is peaking BEFORE the actual cross. Fires early → better entry price, more time for the spread to decay.

```python
# Bull exhaustion: histogram peaked in BULL regime
# histogram was rising (bullish), now starting to fall → momentum rolling over
bull_exhaust = (
    regime == "BULL" and
    hist[i-1] > 0 and              # still positive (in bull territory)
    hist[i-1] > hist[i-2] and      # last bar was higher than bar before
    hist[i] < hist[i-1]            # current bar lower → peak confirmed
)
→ SELL_CALL_SPREAD (sell calls early, before MACD rolls over)

# Bear exhaustion: histogram troughed in BEAR regime
bear_exhaust = (
    regime == "BEAR" and
    hist[i-1] < 0 and              # still negative (in bear territory)
    hist[i-1] < hist[i-2] and      # last bar was lower than bar before
    hist[i] > hist[i-1]            # current bar higher → trough confirmed
)
→ SELL_PUT_SPREAD (sell puts early, before MACD recovers)
```

**Why exhaustion is the edge:** It enters 1-2 days before the cross. The spread is at maximum premium. By the time the cross happens (which everyone can see), the best credit is already gone. Exhaustion captures it first.

### Entry Timing Split (Critical)

| Signal | Entry time | Price used in backtest |
|---|---|---|
| SELL_CALL_SPREAD | 10:00 AM ET open | `open` price |
| SELL_PUT_SPREAD | 3:00 PM ET EOD | `close` price |

**Why EOD for puts:** Put spreads enter at end of day to capture the full day's bearish move. This is a bearish-year strategy — selling pressure peaks EOD, giving the best entry credit on put spreads.

### Larger Regime Context (MACD within Trend)

MACD exhaustion signals are most powerful when they align with the **larger regime**:

```
Large regime = weekly MACD direction
Small signal = daily MACD exhaustion

Best trades:
  Weekly MACD negative (BEARISH) + daily bull_exhaust → SELL_CALL_SPREAD (double-confirmed bearish)
  Weekly MACD positive (BULLISH) + daily bear_exhaust → SELL_PUT_SPREAD (double-confirmed bullish)

Weaker trades (single timeframe confirmation only):
  Weekly MACD positive + daily bull_exhaust → counter-trend, smaller size or skip
```

This is the same dual-MACD principle from the SPX track — weekly MACD sets direction, daily catches the exhaustion point within that direction.

### MACD Results (12-Month)

| Ticker | Trades | WR | P&L | Notes |
|---|---|---|---|---|
| **QQQ** | 13 | **90%** | **+$1,022** | Best single ticker. Reliable MACD, good data |
| NVDA | 8 | 87.5% | +$640 | High IV, strong trend moves |
| IWM | 7 | 86% | +$485 | Solid. Put spread EOD entry key |
| TSLA | 12 | 58% | -$138 | Problem child — see below |

**QQQ over TQQQ:** TQQQ MACD had 54% WR — 3x leverage amplifies MACD whipsaws. QQQ = same signal, better execution, tighter spreads. **Do not put TQQQ on MACD.**

**TSLA problems:**
- Wall placement too tight (1.5% on a $300-500 stock = $4-7 OTM; TSLA moves 3-5% daily)
- MACD fake-outs — TSLA reverses faster than MACD detects
- Three single-trade blowups: -$647 (Nov 2025), -$458 (Apr 2025), -$328 (Feb 2026)
- Open question: widen wall to 3-4%, or remove TSLA from MACD entirely

**Why daily morning check instead of intraday bars:**
- 5-min option bars unavailable for many OTM strikes on Polygon
- Daily check eliminates ~70% of NO_CHAIN rejections
- Fewer false SL triggers from intraday noise → call spread WR went from ~65% to 77-82%

---

## Method 3 — HMM Dynamic Bi-Weekly Selector

**Universe:** Candidate pool of ~20 liquid tickers (NVDA, AAPL, GDX, NVDL, etc.)
**Selection:** Top 3 scored by `IV_rank × momentum_factor` every 2 weeks
**Expiry:** 1 week

### How It Works

Every 2 weeks, score each candidate:
```
score = IV_rank (0-1, where 1 = highest IV vs own history)
      × momentum_factor (regime-adjusted directional strength)
```

Pick top 3. This prevents over-concentration and rotates automatically into high-IV regimes (earnings aftermath, macro stress, sector moves).

### Dynamic Results (12-Month)

| Ticker | Trades | WR | P&L | Notes |
|---|---|---|---|---|
| NVDA | 6 | **100%** | **+$1,073** | Selected in high-IV windows — earnings, AI moves |
| NVDL | 49 | 78% | +$970 | Selected most windows — consistently high IV |
| GDX | 10 | 80% | +$198 | Gold vol spikes in macro stress |
| AAPL | 3 | **100%** | **+$459** | Rarely selected — only when IV unusually elevated |

**Key pattern:** Tickers that score into the top 3 during high-IV regimes perform dramatically better. The selector naturally avoids low-IV periods.

**Drawdown clustering:** Major losses happen when multiple tickers hit SL in the same window. April 2025 tariff shock: TSLA -$458 + NVDA_MACD -$440 + SPXL -$178 + -$183 = -$1,100 in one week. This is a market-crash event, not a strategy failure — cannot be avoided through filtering.

---

## Combined Strategy Results

| Date | Config | Trades | WR | P&L | Notes |
|---|---|---|---|---|---|
| 2026-03-25 | RR=5.0, IV=15% | 112 | 75.0% | +$4,287 | |
| **2026-03-25** | **RR=4.0, IV=10%** | **148** | **77.0%** | **+$6,105** | **Sweet spot** |

**12-month breakdown by method:**
- GEX Weekly (TQQQ/SPXL + NVDL/METU): ~$1,400
- MACD Cross + Exhaustion: ~$2,600 (QQQ dominant)
- HMM Dynamic: ~$2,100 (NVDA + NVDL dominant)

---

## IV Crush Track (Scanner Working, Backtest Pending)

Separate earnings-driven iron condor track. **NOT yet live.**

Entry: 1-2 days before earnings announcement
Exit: Morning after print (IV crush already happened)
Structure: Iron condor with short strikes at GEX call/put walls, wings at 1.5× implied move

**Filters for good crush candidates:**
- IV/HV ratio ≥ 1.3 (prefer ≥ 1.8) — implied vol must be elevated vs historical
- Implied move ≥ 2% (prefer ≥ 4%)
- IV/HV ≥ 1.8 AND implied move ≥ 4% = STRONG signal

**Directional bias on exit:**
- If VSM neutral → close entire IC at 50% TP
- If VSM bullish → put spread rides to 70% TP; call spread closes immediately after print
- If VSM bearish → call spread rides to 70% TP; put spread closes immediately after print

Data sources: Polygon `filing_date` for historical dates, Finnhub for forward calendar.
Status: Scanner confirmed working. Backtest implementation pending.

---

# BACKTEST AND LIVE TRADING — TECHNICAL REFERENCE

Everything a developer needs to build or replicate this system from scratch.

---

## Prerequisites

### Python Version
Python **3.10+** required. `hmmlearn` and `tastytrade` SDK have no support for 3.9.

### Required Packages
```bash
pip install tastytrade>=12.0 pandas numpy scipy requests python-dotenv pytz hmmlearn
```

| Package | Used for |
|---|---|
| `tastytrade>=12.0` | Order execution, DXLinkStreamer quotes, account management |
| `pandas / numpy` | Bar data, signal computation |
| `scipy` | Butterworth low-pass filter for VSM (`scipy.signal.butter`, `lfilter`) |
| `requests` | Polygon API calls (direct HTTP, no SDK wrapper) |
| `hmmlearn` | Gaussian HMM for intraday regime detection (Method 3) |
| `python-dotenv` | `.env` file loading |
| `pytz` | ET timezone checks — always use ET for market hours decisions |

### `.env` File — Required Variables
```bash
# Polygon
POLYGON_API_KEY=your_key_here          # Starter tier minimum — see Polygon section below

# TastyTrade
TASTYTRADE_CLIENT_SECRET=...           # From OAuth2 app credentials
TASTYTRADE_REFRESH_TOKEN=...           # From OAuth2 Create Grant flow
TASTYTRADE_ACCOUNT=5WI45384            # Account number
TASTYTRADE_ENV=production              # "production" or "sandbox"

# Finnhub (IV Crush track only)
FINNHUB_API_KEY=...                    # Free tier: 60 calls/min, forward calendar only
```

### Polygon API Tier
**Free tier will not work.** The backtest and live scanner require options chain snapshots and historical options bars. Minimum: **Starter ($29/mo)**. For full historical options OHLCV: **Developer** tier.

Key rate limit behavior: `poly_get()` in `gex_common.py` handles 429s automatically — backs off 15s × attempt (up to 5 retries).

---

## File Map

```
gex_march_26/
├── total_options.py          ← Run this for the combined backtest (all 3 methods)
├── gex_weekly_backtest.py    ← GEX Weekly only (Method 1 standalone)
├── iv_crush_backtest.py      ← IV Crush scanner (scanner working, backtest pending)
│
combined_live/
├── combined_live.py          ← Live runner — morning scan, EOD scan, broker-check
├── momentum_follow.py        ← HMM signal generation + MACD signals (Methods 2 & 3)
├── gex_weekly_backtest.py    ← GEX Weekly live version (Method 1, mirrors backtest)
├── gex_common.py             ← Shared: Polygon HTTP, bar fetch, ATR, GEX walls, VSM
├── gex_tastytrade.py         ← TastyTrade broker execution (entry, OCO, verify)
├── positions.json            ← Live state: pending + open positions
└── live_trade_log.csv        ← Closed trades with P&L history
```

**Start here:**
- Build/run backtest → `total_options.py`
- Understand signals → `momentum_follow.py` (MACD) + `gex_weekly_backtest.py` (GEX/VSM)
- Understand shared data layer → `gex_common.py`
- Understand live execution → `combined_live.py` + `gex_tastytrade.py`

---

## Key Concepts: GEX Walls, VSM, HMM

### GEX Walls — Highest Open Interest Strikes

"GEX wall" in this codebase = the strike with the **highest open interest** on the nearest weekly expiry, fetched from the Polygon options chain snapshot.

```python
# gex_common.py: fetch_gex_walls(symbol)
data = poly_get(f"https://api.polygon.io/v3/snapshot/options/{symbol}",
                {"expiration_date": nearest_friday, "sort": "strike_price", "limit": 250})

calls_by_oi = df[df["type"] == "call"].sort_values("oi", ascending=False)
puts_by_oi  = df[df["type"] == "put"].sort_values("oi", ascending=False)

call_wall = calls_by_oi.iloc[0]["strike"]   # highest OI call strike
put_wall  = puts_by_oi.iloc[0]["strike"]    # highest OI put strike
```

**Why high-OI strikes act as S/R:**
Dealers who sold those options are delta-hedging. A call wall = dealers sold calls there = they short the underlying as price rises through the strike (to stay delta-neutral), creating selling pressure. A put wall = dealers sold puts = they buy the underlying as price falls through, creating support. Price tends to pin at or reverse from these levels.

**Fallback if no OI data:** `call_wall = spot × 1.02`, `put_wall = spot × 0.98`

**Second wall:** `next_call_wall` and `next_put_wall` = 2nd-highest OI strike. Used when first wall is too close to spot.

---

### VSM — Volatility-Scaled Momentum (Exact Formula)

VSM answers: "How many ATRs has price moved over the last N bars?" — normalized so high-vol and low-vol instruments are comparable.

```python
# gex_weekly_backtest.py: compute_vsm(bars_5min, momentum_period=14, atr_period=14)
# Uses 5-min bars (the underlying, not the spread)

# Step 1: raw momentum = price change over 14 bars
raw_momentum = close - close.shift(14)

# Step 2: ATR using True Range (high-low, high-prev_close, low-prev_close)
tr  = max(high-low, |high-prev_close|, |low-prev_close|)
atr = tr.rolling(14).mean()

# Step 3: scale momentum by ATR
vsm_raw = raw_momentum / atr      # "how many ATRs has price moved?"

# Step 4: Butterworth low-pass filter (causal — lfilter only, NOT filtfilt)
# CRITICAL: lfilter has zero look-ahead bias. filtfilt would leak future data.
from scipy.signal import butter, lfilter
b, a     = butter(2, cutoff=0.08, btype='low', analog=False)
vsm      = lfilter(b, a, vsm_raw)   # smooth noise, preserve trend direction
```

**Interpretation:**
```
VSM > +1.5  → Strong bullish trend  → DO NOT sell call spreads (price is rallying against you)
VSM < -1.5  → Strong bearish trend  → DO NOT sell put spreads  (price is falling against you)
|VSM| < 0.5 → Momentum exhausted    → Safe to fade both sides  → Iron Condor
0.5-1.5     → Moderate             → Directional spread, watch closely
```

VSM is computed on **5-min bars of the underlying** (QQQ for TQQQ, SPY proxy for SPXL, etc.), not on the spread itself.

---

### HMM — Gaussian Hidden Markov Model (Method 3)

A 3-state Gaussian HMM trained on rolling 15-min bars of the underlying, used to detect intraday regime (BULL / BEAR / NEUTRAL) for the dynamic bi-weekly selector.

**Features (per 15-min bar):**
```python
# momentum_follow.py: compute_features_15min(df)
ret_bar   = log(close / close.shift(1))              # bar log-return
range_pct = (high - low) / close                     # volatility regime
vol_z     = (volume - volume.rolling(26).mean())     # volume z-score
            / volume.rolling(26).std()               # (1 trading day = 26 bars)
```

**Training:**
```python
# GaussianHMM(n_components=3, covariance_type="diag", n_iter=200)
# Trained on last 30 days × 26 bars/day = ~780 bars
# State labeling: highest mean ret_bar = BULL, lowest = BEAR, middle = NEUTRAL
```

**Important:** The HMM is retrained from scratch on each run using recent bars only (rolling 30-day window). This means regime labels may shift — BULL/BEAR are always relative to the training window, not absolute.

**HMM is used for:** Method 3 intraday signal timing (when to enter during the day based on regime at 15-min resolution). The MACD method (Method 2) does NOT use HMM — it uses daily bars and MACD crossovers only.

---

### Dynamic Selector Score (Method 3) — Corrected Formula

The bi-weekly dynamic selector scores each candidate ticker by:

```python
# combined_live.py: _score_ticker(sym, cfg, as_of)
bars  = fetch_daily_bars(underlying, lookback=90_days)
rets  = log(close / close.shift(1)).dropna()
hv    = rets.std() * sqrt(252)       # 20-day annualized historical vol
avg_vol = bars["volume"].mean()      # average daily volume (liquidity proxy)
score   = hv * log1p(avg_vol)        # HIGH VOL × LIQUID = best candidates
```

This is **not** "IV_rank × momentum_factor" — it is `historical_volatility × log(volume)`. Tickers with both high vol AND high liquidity score best. Low-liquidity high-vol names are penalized by the log dampening.

Top 3 scorers are selected for that bi-weekly window. Runs every scan day but only updates the active set when the 2-week window rolls.

---

## Polygon API Endpoints Reference

All calls go through `gex_common.poly_get()` which injects the API key and handles 429 retries.

| Endpoint | Used for |
|---|---|
| `GET /v2/aggs/ticker/{symbol}/range/1/day/{from}/{to}` | Daily OHLCV bars (underlying) — backtest + MACD signals |
| `GET /v2/aggs/ticker/{symbol}/range/5/minute/{from}/{to}` | 5-min bars — VSM computation, GEX intraday tracking |
| `GET /v2/aggs/ticker/{symbol}/range/15/minute/{from}/{to}` | 15-min bars — HMM training (Method 3) |
| `GET /v3/snapshot/options/{symbol}` | Options chain snapshot — GEX walls (OI by strike), live credit estimation |
| `GET /v3/snapshot/options/{symbol}/{occ_ticker}` | Single option mid-price — live TP/SL check in `morning_check` |
| `GET /v3/reference/options/contracts` | Available expiry dates for a symbol |
| `GET /v2/snapshot/locale/us/markets/stocks/tickers/{symbol}` | Spot price (fallback) |
| `GET /v3/trades/{symbol}` | Latest trade price (primary spot price source) |

**OCC ticker format:**
```python
# gex_common.py: build_occ_ticker(symbol, expiry, option_type, strike)
# e.g. IWM put expiring 2026-04-02 at $245 strike:
f"O:{symbol}{expiry.strftime('%y%m%d')}{option_type}{int(strike*1000):08d}"
# → "O:IWM260402P00245000"
# TastyTrade OCC format adds padding spaces: "IWM   260402P00245000"
```

---

## How Option Prices Are Modeled

### In Backtest

The backtest does **not** use Black-Scholes or any pricing model. It fetches real historical option bar data from Polygon:

- **Entry credit**: `fetch_option_price(symbol, expiry, type, strike, signal_time)` → Polygon 5-min bar close at `signal_time` for the OCC ticker
- **TP/SL check**: Same function, called at each daily bar's open (10AM proxy)
- **No chain → skip**: If Polygon returns no bars for a strike (`NO_CHAIN`), the trade is skipped. This happens for deep OTM strikes or less liquid expiries. Switching to daily bars (from 5-min) eliminated ~70% of these rejections.

### In Live Trading

`_spread_current_value(pos)` in `combined_live.py`:
```python
# Fetches current mid from Polygon snapshot for each leg
short_mid = poly_get(f"/v3/snapshot/options/{symbol}/{short_occ}")["results"]["day"]["close"]
long_mid  = poly_get(f"/v3/snapshot/options/{symbol}/{long_occ}")["results"]["day"]["close"]
current_debit_to_close = short_mid - long_mid
```

This is the value used by `morning_check()` to compare against `tp_debit` and `sl_debit`.

---

## Strike Selection Algorithm

```
1. Get GEX walls from Polygon snapshot (highest OI call/put strikes)
2. Determine direction:
   - SELL_CALL_SPREAD → short strike at or above call_wall
   - SELL_PUT_SPREAD  → short strike at or below put_wall
3. Apply min_wall_dist_pct (e.g. 1.5% = wall must be ≥1.5% from spot)
   - If wall is too close: use next_call_wall / next_put_wall
4. Snap to increment (snap_increment per ticker):
   - QQQ, IWM: snap to nearest $1
   - NVDA, AMZN: snap to nearest $5
   - NVDL, GDX: snap to nearest $1
5. Long strike = short ± spread_width, also snapped
```

**Spread widths per ticker (from config):**
| Ticker | Width | Snap | Min wall dist |
|---|---|---|---|
| TQQQ / SPXL (GEX Weekly) | $3 | $1 | 1.5% |
| QQQ (MACD) | $5 | $1 | 1.5% |
| IWM (MACD) | $5 | $1 | 1.0% |
| NVDA (MACD) | $10 | $5 | 1.5% |
| NVDL (Dynamic) | $3 | $1 | 1.5% |
| GDX (Dynamic) | $2 | $1 | 1.0% |
| META / NFLX (Dynamic) | $20 | $10 | 1.5% |
| SPX (MACD, disabled by default) | $25 | $5 | 1.5% |

---

## Cost Model

```python
SLIPPAGE   = 0.05   # $0.05/share per leg at entry AND exit
COMMISSION = 0.10   # $0.10 flat per trade (backtest)
```

**Live TastyTrade commissions:** $1.00/contract to open, $0.00 to close.

**Backtest vs live discrepancy:** The backtest uses $0.10 flat which is more optimistic than live $1.00/contract. For 1-contract trades the difference is $0.90/trade. At 148 trades/year this is ~$133 in unmodeled cost. Not critical at this scale but worth noting when comparing backtest P&L to live results.

---

## positions.json — Full Schema

Every signal starts as `pending`. After `--fill <id> <credit>` it becomes `open`. After TP/SL/expiry it is removed from positions.json and written to `live_trade_log.csv`.

```json
{
  "id":           "4244e77e",          // short UUID — use for --fill command
  "source":       "MACD",             // "MACD" | "GEX" | "HMM"
  "symbol":       "IWM",              // traded instrument (may differ from underlying)
  "underlying":   "IWM",              // underlying for bar/wall fetching
  "trade_type":   "SELL_PUT_SPREAD",  // "SELL_CALL_SPREAD" | "SELL_PUT_SPREAD" | "IRON_CONDOR"
  "entry_date":   "2026-03-26",
  "expiry":       "2026-04-02",
  "spread_width": 5.0,
  "contracts":    1,
  "tp_pct":       0.5,                // TP fires when spread decays to credit*(1-tp_pct)
  "sl_pct":       1.0,                // SL fires when spread grows to credit*(1+sl_pct)
  "min_credit":   0.5,                // floor for chase entry (not the starting price)
  "max_rr":       4.0,
  "credit":       null,               // null = pending. Set by --fill to actual fill credit
  "status":       "pending",         // "pending" | "open" | (removed when closed)

  // For SELL_PUT_SPREAD:
  "short_put":    245.0,
  "long_put":     240.0,

  // For SELL_CALL_SPREAD:
  "short_call":   500.0,
  "long_call":    505.0,

  // Set after --fill or broker execution:
  "short_symbol": "IWM   260402P00245000",  // OCC with TastyTrade space padding
  "long_symbol":  "IWM   260402P00240000",
  "tp_order_id":  449959600,
  "tp_price":     1.04,
  "tp_pct_actual": 0.70,
  "sl_price":     2.96,

  // MACD-specific:
  "config_key":   "IWM_MACD",
  "macd_trigger": "CROSS T+1 follow-through: regime=BULL",
  "spot_at_signal": 248.0
}
```

**Status lifecycle:**
```
signal generated → status=pending, credit=null
--fill <id> <credit> → status=open, credit=<actual>
morning_check TP hit → removed from positions.json, written to live_trade_log.csv
morning_check SL hit → removed from positions.json, written to live_trade_log.csv
expiry reached → removed (assumed expires worthless = full profit)
```

---

## TP / SL Threshold Formulas

```python
# morning_check() in combined_live.py
tp_debit = credit * (1.0 - tp_pct)   # e.g. credit=1.48, tp_pct=0.50 → tp=0.74
sl_debit = credit * (1.0 + sl_pct)   # e.g. credit=1.48, sl_pct=1.0  → sl=2.96

# Interpretation:
# tp_pct=0.50 → close when spread has lost 50% of its value (captured 50% of credit)
# sl_pct=1.0  → close when spread is worth 2× the credit (you've lost the credit back)
# SL debit = credit + credit = 2× entry credit (break-even stop — you give back what you made)
```

---

## End-to-End Live Trading Pipeline

```
10:15 AM ET ── python combined_live.py --broker tastytrade
│
├── morning_check():
│     For each status=open position:
│       Fetch current spread value via Polygon snapshot
│       If cur_val <= tp_debit → log TAKE PROFIT, place DAY LIMIT BTC, write to trade_log
│       If cur_val >= sl_debit → log STOP LOSS,  place DAY LIMIT BTC, write to trade_log
│       Else → HOLD, keep in positions.json
│
└── Signal scan (GEX Weekly + MACD):
      Generate new signals → append to positions.json (status=pending, credit=null)
      execute_signal() via gex_tastytrade.py → entry order → chase fill
      After fill: --fill <id> <credit> to set status=open with actual credit


3:00 PM ET ── python combined_live.py --broker tastytrade --eod --skip-gex --skip-dynamic
│
└── MACD put spread signals only (EOD entry at close price)
      Same execute_signal() → chase → verify_and_reprotect()


3:30 PM ET ── python combined_live.py --broker tastytrade --broker-check
│
└── eod_position_check():
      For each status=open position:
        Look for working GTC TP order in TastyTrade
        If missing → place fresh GTC LIMIT TP
        If wrong price → update_tp_percentage() (cancel + replace)
        Log OK / fixed


Next morning ── morning_check() runs again
      SL is ONLY checked here — no intraday SL protection (broker stop orders
      not supported on multi-leg spreads — see ⚠️ SL section in WORKFLOW A)
```

---

## Scheduling

**Windows (Task Scheduler):**
```
Task 1: 10:15 AM ET (Mon-Fri)
  python C:\path\combined_live.py --broker tastytrade

Task 2: 3:00 PM ET / 12:00 PM PT (Mon-Fri)
  python C:\path\combined_live.py --broker tastytrade --eod --skip-gex --skip-dynamic

Task 3: 3:30 PM ET / 12:30 PM PT (Mon-Fri)
  python C:\path\combined_live.py --broker tastytrade --broker-check
```

**Mac/Linux (crontab):**
```bash
15 10 * * 1-5  cd /path && python combined_live.py --broker tastytrade
0  15 * * 1-5  cd /path && python combined_live.py --broker tastytrade --eod --skip-gex --skip-dynamic
30 15 * * 1-5  cd /path && python combined_live.py --broker tastytrade --broker-check
```
*Adjust for your timezone — times above are ET.*

**If a run fails:** Check `logs/YYYYMMDD.log`. The most common causes are Polygon rate limits (auto-retried) and SSL timeouts (re-run manually). No auto-retry loop — investigate the log before rerunning.

---

## Capital Requirements

| Item | Amount |
|---|---|
| Minimum recommended account | $10,000 |
| Buying power per $5 spread (1 contract) | ~$400–480 (width − credit) |
| Buying power per $10 spread (NVDA, 1 contract) | ~$800–950 |
| Max simultaneous positions (typical) | 4–6 across all 3 methods |
| Max simultaneous positions (stress) | 8–10 |
| Worst single-week drawdown (Apr 2025 tariff shock) | −$1,100 (~11% on $10k) |
| Expected annual P&L range (1 contract/signal) | $4,000–$7,000 |

Scale contracts proportionally. At 2 contracts/signal on a $20k account the P&L and drawdown both double.

---

# WORKFLOW A — Spread Entry

Execute a vertical credit spread on TastyTrade. Follow every step — each encodes a production lesson.

## A1. Pre-flight: Confirm ET Market Hours

**Never assume market status from local system time.**

```python
from datetime import datetime
import pytz
et = pytz.timezone('America/New_York')
now_et = datetime.now(et)
market_open = "09:30" <= now_et.strftime("%H:%M") <= "16:00" and now_et.weekday() < 5
print("ET:", now_et.strftime("%H:%M:%S %Z"), "| Market open:", market_open)
```

Options hours: **9:30 AM – 4:00 PM ET**. After 4 PM, DAY orders are rejected.

## A2. Starting Credit — Fetch Live Market Mid

**Do NOT start chase at `min_credit` — this leaves money on the table (confirmed: sold $1.48 spread for $0.46).**

Use `get_spread_mid()` from `gex_tastytrade.py`:
```python
market_mid = await get_spread_mid(session, short_opt, long_opt)
credit = round(market_mid, 2) if market_mid and market_mid > min_credit else min_credit
```
- `spread_mid = (short.bid + short.ask)/2 − (long.bid + long.ask)/2` via DXLink streamer
- Fall back to `min_credit` floor if streamer times out (log a warning)

## A3. Chase Entry

```python
entry_result = await chase_entry(
    session, account, symbol, expiry, opt_type,
    short_strike, long_strike,
    credit=market_mid,   # live mid, NOT min_credit
    contracts=contracts,
    wait_secs=20, step=0.02, min_credit=0.10,
)
```

Chase: place LIMIT DAY → wait 20s → if unfilled cancel → reduce $0.02 → retry until floor.

## A4. Actual Fill Credit

**Do not trust the chase limit price.** Fetch real fill from positions:

```python
positions = await account.get_positions(session)
short_pos = {p.symbol.strip(): p for p in positions}[short_symbol.strip()]
long_pos  = {p.symbol.strip(): p for p in positions}[long_symbol.strip()]
actual_credit = float(short_pos.average_open_price) - float(long_pos.average_open_price)
```

Use `actual_credit` for all TP/SL calculations.

## A5. Take Profit — Hard Broker Order ✅

TP is a passive **GTC LIMIT DEBIT** order. The spread decays to your price; a market maker fills it automatically. No monitoring needed — identical to TastyTrade's "Close at 50%" button.

```
Spread opened at $1.48 → TP at $1.04 (70%)
Theta erodes spread daily → when market hits $1.04 → auto-fill ✅
```

**Recommended TP = 70% of actual_credit.** (Not 50% — better fill rate, captures most decay without holding to expiry gamma risk.)

OCO rules for both TP and SL legs:
- Both `OrderType.LIMIT` (NOT STOP_LIMIT)
- Both prices away from current market or rejected with `invalid_oco_price`
- Both `PriceEffect.DEBIT`

If OCO rejected with `"would execute immediately"` → spread already at/past TP → close with DAY LIMIT now.

After 4 PM ET: GTC LIMIT accepted with warning `tif.next_valid_session` — queues for next open. Correct behavior.

## A6. ⚠️ Stop Loss — Software Only, NO Hard Broker Order

**This is the most critical thing to understand before going live.**

| Order type | What happens |
|---|---|
| `STOP` on spread | Rejected at API — market orders restricted to 1 leg |
| `STOP_LIMIT` on spread | API accepts it → routed → silently cancelled by exchange |
| Platform "Stop on Spread" button | Server-side simulation — not in public API |

*Source: [TastyTrade API docs](https://developer.tastytrade.com/order-submission/): "Stop orders are market orders" + "Market orders must only have 1 leg"*

**Why TP works but SL doesn't:**
- TP: spread decays **down** to your resting limit → market comes to you → fills ✅
- SL: spread moves **up** past threshold → needs active stop trigger → not supported on multi-leg ❌

**The only working SL is software monitoring** (`morning_check` runs at market open daily):
```python
current_mark = float(short_pos.average_open_price) - float(long_pos.average_open_price)
if current_mark >= actual_credit * 2.0:
    # place DAY LIMIT to close immediately
```

**Risk implications:**
- If your process is not running → zero stop protection
- Gap overnight → SL fires at open, possibly at a worse price
- Max loss = spread width − credit (not just the SL target)
- Size contracts so max loss is tolerable without the SL firing

**Mitigation:** run `morning_check` every trading day at open. Consider hourly intraday check for higher-risk positions.

## A7. Verify 60s Later

```python
verify_result = await verify_and_reprotect(
    session, account, short_symbol, long_symbol,
    contracts=contracts, wait_secs=60,
)
```

Confirms legs exist, BUY_TO_CLOSE order is working. If not → re-places OCO from `actual_credit`.

## A8. Save to positions.json

```json
{
  "credit": 1.48,
  "status": "open",
  "short_symbol": "IWM   260402P00245000",
  "long_symbol":  "IWM   260402P00240000",
  "tp_order_id": 449959600,
  "tp_price": 1.04,
  "tp_pct_actual": 0.70,
  "sl_price": 2.96
}
```

OCC symbols have trailing space padding. Always `.strip()` when comparing.

---

# WORKFLOW B — EOD Position Check (3:30 PM ET)

Verifies every open position has a working GTC TP order at the correct price. Fixes anything missing or wrong.

## Schedule

| Time ET | Command |
|---|---|
| 10:15 AM | `python combined_live.py --broker tastytrade` |
| 3:00 PM | `python combined_live.py --broker tastytrade --eod --skip-gex --skip-dynamic` |
| **3:30 PM** | `python combined_live.py --broker tastytrade --broker-check` |

## What It Checks

For each `status=open` position with `credit != null` in `positions.json`:
1. Fetches all working orders from TastyTrade
2. Matches by leg symbols (strips OCC padding)
3. **Found, correct price** → OK
4. **Found, wrong price** → `update_tp_percentage()`: cancel + replace
5. **Not found** → places fresh GTC LIMIT TP
6. Saves updated `tp_order_id` back to `positions.json`

**This check verifies TP orders only. SL has no broker-side order — it runs in `morning_check`.**

## Manual Ad-hoc Inspection

```python
import asyncio
from gex_tastytrade import get_session, get_account, get_working_orders

async def check():
    session = await get_session()
    account = await get_account(session)
    for o in await get_working_orders(session, account):
        print(f"#{o['order_id']}  {o['status']}  ${o['price']}  TIF={o['tif']}")
        for leg in o['legs']:
            print(f"  {leg['symbol']}  {leg['action']}  qty={leg['qty']}")

asyncio.run(check())
```

---

# WORKFLOW C — Update Take Profit

Cancel a pending GTC TP order and replace at a new percentage.

## TP Percentage Guidelines

| Pct | Use case |
|---|---|
| 50% | Conservative — quick exit, high fill probability |
| **70%** | **Recommended** — realistic intraday fill, most decay captured |
| 80% | Aggressive — hold longer, more gamma risk near expiry |

## Steps

1. Read `positions.json` → get `credit`, `tp_order_id`, `short_symbol`, `long_symbol`
2. Compute `new_tp_price = round(credit * new_tp_pct, 2)`
3. Call `update_tp_percentage()`:

```python
result = await update_tp_percentage(
    session, account,
    short_symbol=pos["short_symbol"],
    long_symbol=pos["long_symbol"],
    original_credit=float(pos["credit"]),
    new_tp_pct=0.70,
    old_order_id=int(pos["tp_order_id"]),
    contracts=int(pos.get("contracts", 1)),
)
```

Function: cancels old order → waits 2s → confirms cancellation → places new GTC LIMIT.

4. Update `positions.json`: `tp_order_id`, `tp_price`, `tp_pct_actual`

**After-hours**: GTC LIMIT accepted with `tif.next_valid_session` warning. Best time to update — no rejection risk from "would execute immediately".

---

# WORKFLOW D — MACD Backtest

## Run

```bash
cd C:/Users/sujoy/gex_march_26
python total_options.py
```

## Signal Architecture

**MACD Cross** (T+1 confirmation):
- BULL→BEAR → `SELL_CALL_SPREAD` at 10:00 AM ET using `open` price
- BEAR→BULL → `SELL_PUT_SPREAD` at 3:00 PM ET using `close` price

**MACD Exhaustion** (fires 1–2 days before cross — the edge):
- `bull_exhaust`: histogram peaked in BULL → early SELL_CALL_SPREAD
- `bear_exhaust`: histogram troughed in BEAR → early SELL_PUT_SPREAD

```python
def compute_macd_full(daily_bars, fast=12, slow=26, sig=9):
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

**Entry timing is critical:**
```python
price_col = "close" if signal.trade_type == "SELL_PUT_SPREAD" else "open"
```

Put spreads enter EOD (close price) — captures full day's bearish move.
Call spreads enter at open — captures overnight gap direction.

## Benchmark Results (2024–2026)

- 83 trades | WR = 86.7% | Total = $5,612
- IWM: 86% WR, +$485
- SELL_PUT_SPREAD: 79% WR after EOD entry fix

## Adding a Ticker

```python
"TICKER_MACD": {
    "symbol": "TICKER",
    "regime_method": "MACD",
    "spread_width": 5,       # $5 wide = max loss $500 - credit
    "min_credit": 0.50,      # floor = ~10% of width
    "max_rr": 4.0,           # skip if risk/reward worse than 4:1
    "tp_pct": 0.50,          # backtest TP (live uses 0.70)
    "sl_pct": 1.0,           # SL at 1x credit = 2x credit debit to close
    "dte_target": 7,         # target 7 days to expiry
    "contracts": 1,
}
```

Gate: WR ≥ 70% and avg P&L ≥ $20/trade before adding to live.

**Keep backtest and live in sync:** `generate_signals_macd()` must be identical in both `total_options.py` and `combined_live/momentum_follow.py`.
