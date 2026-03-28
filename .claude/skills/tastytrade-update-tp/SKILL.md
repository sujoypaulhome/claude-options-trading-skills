---
name: tastytrade-update-tp
description: Cancel a pending TastyTrade GTC take-profit order and replace it at a new percentage of the original credit. Use when adjusting the take-profit target on an open position (e.g. from 50% to 70%).
argument-hint: [pos_id or order_id] [new_tp_pct e.g. 0.70]
---

# Update Take-Profit on a TastyTrade Pending Order

Changes the TP target on an existing GTC LIMIT order.

## Arguments
`$ARGUMENTS` = `<pos_id_or_order_id> <new_tp_pct>`
Examples:
- `4244e77e 0.70` — update position 4244e77e to 70% TP
- `449959600 0.60` — update order #449959600 to 60% TP

---

## Step 1 — Look Up the Position

Read `positions.json` to get:
- `credit` (actual fill credit, not min_credit)
- `tp_order_id` (current pending order to cancel)
- `short_symbol`, `long_symbol`
- `contracts`

```python
import json
with open("positions.json") as f:
    positions = json.load(f)
pos = next(p for p in positions if p["id"] == "<pos_id>" or str(p.get("tp_order_id")) == "<order_id>")
```

---

## Step 2 — Compute New TP Price

```python
new_tp_pct   = float("$1")          # e.g. 0.70
actual_credit = float(pos["credit"])
new_tp_price  = round(actual_credit * new_tp_pct, 2)
print(f"New TP: ${new_tp_price} ({new_tp_pct*100:.0f}% of ${actual_credit})")
```

---

## Step 3 — Cancel and Replace

Use `update_tp_percentage()` from `gex_tastytrade.py`:

```python
import asyncio
from gex_tastytrade import get_session, get_account, update_tp_percentage

async def run():
    session = await get_session()
    account = await get_account(session)
    result = await update_tp_percentage(
        session=session,
        account=account,
        short_symbol=pos["short_symbol"],
        long_symbol=pos["long_symbol"],
        original_credit=float(pos["credit"]),
        new_tp_pct=new_tp_pct,
        old_order_id=int(pos["tp_order_id"]),
        contracts=int(pos.get("contracts", 1)),
        dry_run=False,
    )
    print(result)

asyncio.run(run())
```

The function:
1. Calls `account.delete_order(session, old_order_id)`
2. Waits 2s and confirms cancellation
3. Fetches instrument types from live positions
4. Places new `NewOrder(GTC, LIMIT, [BTC short, STC long], price=new_tp_price, DEBIT)`

---

## Step 4 — Update positions.json

After success, update:
```json
{
  "tp_order_id": <new_order_id>,
  "tp_price": <new_tp_price>,
  "tp_pct_actual": <new_tp_pct>
}
```

---

## TP Percentage Guidelines

| Pct | Use case |
|---|---|
| 50% | Conservative — quick exit, high fill probability |
| 70% | **Recommended** — realistic intraday fill, captures most premium decay |
| 80% | Aggressive — hold longer, more gamma risk near expiry |

**Rule of thumb**: 70% is the sweet spot. A spread at 70% decay still has plenty of time premium left to cover slippage, and fills reliably within 1-3 trading days on a well-placed spread.

---

## After-Hours Behavior

Market closes 4:00 PM ET. After that:
- GTC LIMIT orders are **accepted** with warning: `tif.next_valid_session`
- Status = `Received` — activates at next morning's open
- This is the **correct time** to update TP if market is closed — no rejection risk
