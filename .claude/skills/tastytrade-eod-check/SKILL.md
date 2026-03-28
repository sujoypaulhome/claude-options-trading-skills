---
name: tastytrade-eod-check
description: Run the 3:30 PM ET TastyTrade position check. Verifies every open position has a working GTC TP order at the correct price. Fixes missing or mispriced orders automatically. Use after the EOD scan or any time you want to audit live positions.
argument-hint: [--dry-run]
---

# TastyTrade EOD Position Check (3:30 PM ET)

Runs `eod_position_check()` to audit all open positions against live broker orders.

## When to Run

| Time ET | Action |
|---|---|
| 10:15 AM | Morning scan: `python combined_live.py --broker tastytrade` |
| 3:00 PM | EOD scan: `python combined_live.py --broker tastytrade --eod --skip-gex --skip-dynamic` |
| **3:30 PM** | **This check: `python combined_live.py --broker tastytrade --broker-check`** |

Run it now:

```bash
cd C:/Users/sujoy/gex_march_26/combined_live
python combined_live.py --broker tastytrade --broker-check $ARGUMENTS
```

---

## TP vs SL — Why One Is a Hard Order and the Other Isn't

**Take Profit** = plain GTC LIMIT DEBIT order sitting at the broker.
- The spread naturally decays toward zero as expiry approaches (theta)
- When the market price hits your TP level, a market maker fills it automatically
- No monitoring needed — broker holds it indefinitely. Identical to TastyTrade's "Close at 50%" button
- Confirmed working: a pending `status=Received` GTC LIMIT order in your account **will execute** when the spread decays to that price

**Stop Loss** = cannot be a hard broker order on spreads.
- A stop requires the broker to *watch* the price and *trigger* a new order when a threshold is crossed
- TastyTrade API docs confirm: `"Stop orders are market orders"` + `"Market orders must only have 1 leg"` → STOP blocked at API level
- STOP_LIMIT: accepted by API, routed, then silently cancelled by exchange routing
- Result: SL is software-only — only fires when your monitoring script runs

**This check verifies your TP orders. SL has no broker-side order to verify — it depends entirely on `morning_check` running.**

---

## What the Check Does

For every position in `positions.json` with `status=open` and `credit != null`:

1. **Fetches all working orders** from TastyTrade (non-terminal: not Rejected/Cancelled/Expired/Filled)
2. **Matches orders to positions** by leg symbols (strips OCC symbol whitespace padding)
3. For each position:
   - **Found, correct price** → logs OK
   - **Found, wrong price** → calls `update_tp_percentage()`: cancel old + place new GTC LIMIT
   - **Not found** → places fresh GTC LIMIT TP

After the check, updates `tp_order_id` in `positions.json`.

---

## Interpreting Results

```
[pos_id] IWM  short=IWM   260402P00245000  long=IWM   260402P00240000
credit=$1.48  expected_tp=$1.04  sl=$2.96
Found order #449959600  price=$1.04  status=Received  OK
```

- **OK** → nothing to do
- **PRICE MISMATCH** → auto-fixed via cancel+replace
- **No working TP order found** → fresh order placed
- **legs not in account** → position may have already closed; check broker manually

---

## After-Hours Behavior

GTC LIMIT orders placed after 4 PM ET return warning:
`tif.next_valid_session: Your order will begin working during next valid session.`

Status will be `Received`. This is correct — the order queues and activates at next open.

---

## ⚠️ SL Is Software-Only — This Check Does Not Replace a Hard Stop

This check verifies your **take-profit** orders only. Stop-loss protection on spreads cannot be enforced at the broker level.

Per [TastyTrade API docs](https://developer.tastytrade.com/order-submission/): STOP orders are market orders restricted to 1 leg. STOP_LIMIT on multi-leg spreads is accepted by the API but silently cancelled by exchange routing. The platform "Stop on Spread" button is a server-side simulation not accessible via API.

**Your SL is only checked when `morning_check` runs.** If this script does not run on a given day, open positions have no stop protection. Run it every trading day at market open.

---

## Manual Ad-hoc Check

To inspect working orders without running the full check:

```python
import asyncio
from gex_tastytrade import get_session, get_account, get_working_orders

async def check():
    session = await get_session()
    account = await get_account(session)
    orders = await get_working_orders(session, account)
    for o in orders:
        print(f"#{o['order_id']}  {o['status']}  ${o['price']}  TIF={o['tif']}")
        for leg in o['legs']:
            print(f"  {leg['symbol']}  {leg['action']}  qty={leg['qty']}")

asyncio.run(check())
```
