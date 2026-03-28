---
name: tastytrade-spread-entry
description: Execute a vertical credit spread (put or call) on TastyTrade via the Python SDK. Handles live market mid fetch, chase logic, OCO exits, and post-fill verification. Use when the user wants to enter a new spread position.
argument-hint: [symbol] [expiry YYYY-MM-DD] [short_strike] [long_strike] [call|put] [contracts]
---

# TastyTrade Vertical Spread Entry

You are executing a vertical credit spread via TastyTrade. Follow these steps exactly — they encode hard-won production lessons.

## Arguments
Parse `$ARGUMENTS` as: `symbol expiry short_strike long_strike call|put contracts`
Example: `IWM 2026-04-02 245 240 put 1`

---

## Step 1 — Pre-flight: Confirm ET Market Hours

**CRITICAL**: Never assume market status from local system time. Always check Eastern Time explicitly.

```python
from datetime import datetime
import pytz
et = pytz.timezone('America/New_York')
now_et = datetime.now(et)
market_open = "09:30" <= now_et.strftime("%H:%M") <= "16:00" and now_et.weekday() < 5
print("ET:", now_et.strftime("%H:%M:%S %Z"), "| Market open:", market_open)
```

Options market hours: **9:30 AM – 4:00 PM ET**. After 4:00 PM new DAY orders are rejected.

---

## Step 2 — Determine Starting Credit (Live Market Mid)

**Do NOT use `min_credit` as the chase starting price — this leaves money on the table.**

Use `get_spread_mid()` from `gex_tastytrade.py` to fetch live bid/ask via DXLink streamer:
- `spread_mid = (short.bid + short.ask) / 2 - (long.bid + long.ask) / 2`
- Start the chase at `max(market_mid, min_credit_floor)`
- If streamer times out, log a warning and fall back to floor

---

## Step 3 — Chase Entry

```python
entry_result = await chase_entry(
    session, account, symbol, expiry,
    opt_type,        # "Call" or "Put"
    short_strike, long_strike,
    credit=market_mid,   # live mid, NOT min_credit
    contracts=contracts,
    wait_secs=20,    # wait 20s per attempt
    step=0.02,       # reduce credit $0.02 per retry
    min_credit=0.10, # absolute floor
)
```

Chase logic:
1. Place LIMIT DAY at `current_credit`
2. Wait 20s — if filled, done
3. If unfilled: cancel → reduce by $0.02 → retry
4. Stop if credit falls below $0.10

---

## Step 4 — After Fill: Compute Actual Credit

**Do not trust the chase limit price as the actual fill.** Fetch real fill from positions:

```python
positions = await account.get_positions(session)
pos_map = {p.symbol.strip(): p for p in positions}
short_pos = pos_map[short_symbol.strip()]
long_pos  = pos_map[long_symbol.strip()]
actual_credit = float(short_pos.average_open_price) - float(long_pos.average_open_price)
```

Use `actual_credit` for all TP/SL calculations.

---

## Step 5 — Place Exits: Take Profit + Stop Loss

### ✅ Take Profit — Works as a Hard Broker Order

TP is a plain **GTC LIMIT DEBIT** order. It is passive — the market comes to you as the spread decays.

```
Spread opened at $1.48 credit
TP order sitting at $1.04 (70% decay target)
Every day, theta erodes the spread value downward
When market hits $1.04 → market maker fills your order automatically
```

**This is identical to what TastyTrade's "Close at 50%/70%" button creates under the hood.**

- Works on any number of legs — it's just a limit order
- No monitoring required — broker holds it server-side indefinitely (GTC)
- After-hours: GTC LIMIT orders placed after 4 PM ET are accepted with warning `tif.next_valid_session` — they queue and activate at next open. This is correct behavior.
- If rejected with `"would execute immediately"` during market hours → spread has already decayed past TP → close with DAY LIMIT immediately (it's a winner)

**Recommended TP = 70% of credit** (not 50% — more realistic intraday fill, captures most of the premium decay without holding to near-expiry gamma risk).

---

## ⚠️ CRITICAL: Stop Loss Does NOT Work the Same Way

**Read this before going live. The SL is fundamentally different from the TP.**

### Why TP works but SL doesn't

| | Take Profit | Stop Loss |
|---|---|---|
| What you need | Spread decays **down** to your price | Spread moves **up** past your price |
| Order mechanic | Passive LIMIT — market comes to you | Active STOP — broker must *watch and trigger* when threshold crossed |
| Exchange support on spreads | ✅ Standard limit order, fully supported | ❌ Contingent/stop triggers not supported on multi-leg at exchange level |

### ⚠️ CRITICAL: There Is No Hard Stop-Loss on Spreads

**This is the most important thing to understand before going live.**

TastyTrade does not support native stop orders on multi-leg spread positions at the exchange level. This is confirmed by the official API documentation:

> *"Stop orders are market orders that are triggered when the quote hits a specific price"*
> *"Market orders must only have 1 leg"*
> — [TastyTrade API Docs — Order Submission](https://developer.tastytrade.com/order-submission/)

What this means in practice:

| Order type | What happens |
|---|---|
| `STOP` on a spread | **Rejected at API level** — market orders restricted to 1 leg |
| `STOP_LIMIT` on a spread | **Accepted by API, routed, then silently cancelled** by exchange routing within seconds |
| TastyTrade "Stop on Spread" button | Platform-side simulation — **not accessible via the public REST API** |

**The only working stop-loss via API is software monitoring:**

```python
# Runs once at market open (morning_check)
positions = await account.get_positions(session)
short_pos = pos_map[short_symbol]
long_pos  = pos_map[long_symbol]
current_mark = float(short_pos.average_open_price) - float(long_pos.average_open_price)

if current_mark >= original_credit * sl_multiplier:
    # place DAY LIMIT to close now
    close_order = NewOrder(
        time_in_force=OrderTimeInForce.DAY,
        order_type=OrderType.LIMIT,
        legs=[BUY_TO_CLOSE short, SELL_TO_CLOSE long],
        price=Decimal(str(round(current_mark * 1.05, 2))),
        price_effect=PriceEffect.DEBIT,
    )
    await account.place_order(session, close_order)
```

**What this means for your risk:**
- If your process is not running, **there is no stop protection at all**
- If the underlying gaps against you overnight, the check fires at the next market open — you may be stopped out at a worse price than your SL target
- If the spread blows through your SL level between morning checks, it won't be caught until the next run

**Mitigation:**
- Run `morning_check` every trading day at market open without exception
- Consider an intraday check (e.g. every hour) for higher-risk positions
- Size contracts so that max loss (spread width − credit) is tolerable even without the SL firing
- Always know your **max loss = spread width − credit received** (not just the SL target)

---

## Step 6 — Verify 60s Later

Call `verify_and_reprotect()` 60 seconds after entry to confirm:
1. Position legs exist in the account
2. A working BUY_TO_CLOSE order exists for the short leg
3. If not → re-place OCO using `actual_credit`

---

## Step 7 — Update positions.json

Record the trade with:
```json
{
  "credit": <actual_credit>,
  "status": "open",
  "short_symbol": "<OCC symbol with spaces>",
  "long_symbol": "<OCC symbol with spaces>",
  "tp_order_id": <order_id>,
  "tp_price": <actual_credit * 0.70>,
  "tp_pct_actual": 0.70,
  "sl_price": <actual_credit * 2.00>
}
```

OCC symbol format: `"IWM   260402P00245000"` — note trailing spaces padding to fixed width. Always `.strip()` when comparing.

---

## Known Pitfalls

| Pitfall | Fix |
|---|---|
| Chase starts at `min_credit` not market | Use `get_spread_mid()` first |
| STOP_LIMIT on spread gets cancelled | Use `LIMIT` GTC for SL leg |
| "invalid_oco_price: would execute immediately" | Position already at TP → close with DAY LIMIT |
| Wrong actual credit (using chase price) | Fetch `avg_open_price` from positions after fill |
| "Market closed" when it isn't | Always check `datetime.now(pytz.timezone('America/New_York'))` |
