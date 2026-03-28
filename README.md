# Claude Code Skills: Options Trading on TastyTrade

A set of [Claude Code](https://claude.ai/claude-code) skills for trading vertical credit spreads on TastyTrade using the official Python SDK. Built from real production trading experience — not toy examples.

## What These Skills Do

| Skill | Invoke with | Description |
|---|---|---|
| `tastytrade` | `/tastytrade` | **Main skill** — routes to all workflows. Entry, EOD check, update TP, backtest. |
| `tastytrade-spread-entry` | `/tastytrade-spread-entry` | Execute a vertical credit spread with live mid-price chase |
| `tastytrade-eod-check` | `/tastytrade-eod-check` | 3:30 PM ET audit: verify every open position has a working GTC TP order |
| `tastytrade-update-tp` | `/tastytrade-update-tp` | Cancel a pending TP order and replace at a new percentage |
| `options-macd-backtest` | `/options-macd-backtest` | Run, analyze, or tune the MACD credit spread backtest |

Start with `/tastytrade` — it covers everything.

---

## Prerequisites

### Accounts & API Keys
- **TastyTrade account** with options trading enabled (Level 2+)
- **TastyTrade API credentials**: username + password (OAuth2 token auto-managed)
- **Polygon.io API key**: Starter tier minimum (~$29/month) — required for historical daily bars, live options snapshot (GEX walls), and options chain data

### Python Environment
```
Python 3.10+
tastytrade>=12.0        # TastyTrade official SDK
polygon-api-client      # Polygon REST + WebSocket
pandas, numpy
scikit-learn            # HMM (hmmlearn), optional
hmmlearn                # optional (Method 3 only)
python-dotenv
pytz
scipy                   # Butterworth filter for VSM
```

### Environment Variables (`.env`)
```
TASTYTRADE_USERNAME=your_username
TASTYTRADE_PASSWORD=your_password
POLYGON_API_KEY=your_polygon_key
```

---

## Quick Install

### 1. Clone this repo into your project

```bash
# Option A: clone directly into your project root
git clone https://github.com/sujoypaulhome/claude-options-trading-skills.git .claude-skills-temp
cp -r .claude-skills-temp/.claude ./
rm -rf .claude-skills-temp

# Option B: clone standalone and symlink
git clone https://github.com/sujoypaulhome/claude-options-trading-skills.git
```

### 2. Place skills where Claude Code can find them

Skills must live under `.claude/skills/` relative to your working directory:

```
your-project/
├── .claude/
│   └── skills/
│       ├── tastytrade/
│       │   └── SKILL.md
│       ├── tastytrade-spread-entry/
│       │   └── SKILL.md
│       ├── tastytrade-eod-check/
│       │   └── SKILL.md
│       ├── tastytrade-update-tp/
│       │   └── SKILL.md
│       └── options-macd-backtest/
│           └── SKILL.md
├── .env
└── your_trading_code.py
```

### 3. Start Claude Code and invoke a skill

```bash
claude
```

Then type:
```
/tastytrade
```

---

## Trading Strategy Overview

These skills encode three signal methods for credit spreads:

### Method 1: GEX Walls (3x Leverage ETFs)
- Tickers: TQQQ, SPXL (3x leverage = amplified gamma exposure)
- Weekly puts/calls bracketing GEX walls (highest OI strike)
- VSM veto filter: skip entries when momentum contradicts direction
- RR ≥ 4.0x required (e.g., $0.50 credit on $2 wide spread)
- Iron Condor when both walls are within 2% of spot

### Method 2: MACD Cross + Exhaustion
- Standard MACD (12/26/9) regime detection
- **Exhaustion filter** fires 1-2 bars BEFORE the cross — the edge
- Call spreads at 10 AM ET open; put spreads at 3 PM ET close
- Tickers: IWM, QQQ, SPY, TQQQ
- Backtested 2024-2026: **86.7% win rate, $5,612 on 83 trades**

### Method 3: HMM Dynamic Selector
- 3-state Gaussian HMM on 15-min bars (log_return, range_pct, volume_z_score)
- Dynamic ticker selection: `score = HV_20 × log1p(avg_volume)`
- Selects top 3 tickers per session

**Combined results (148 trades): 77% win rate, $6,105**

---

## Key Concepts Covered in the Skills

- **Why GTC LIMIT TP works**: Passive resting limit — spread decays via theta, market maker fills automatically. Identical to TastyTrade "Close at 50%" button.
- **Why stop-loss does NOT work as a broker order**: TastyTrade API doc confirms STOP = market order = 1 leg only. STOP_LIMIT on spreads gets silently cancelled by exchange routing. SL is software-only — only fires when your script runs.
- **Chase entry**: Start at live market mid (via DXLink streamer), reduce by $0.02 every 20s until filled or floor reached.
- **Actual fill credit**: Always fetch from `avg_open_price` on positions after fill — don't trust the chase limit price.
- **OCC symbol format**: `"IWM   260402P00245000"` — fixed-width with spaces. Always `.strip()` when comparing.

---

## Daily Schedule

| Time ET | Action |
|---|---|
| 10:15 AM | Morning scan: `python combined_live.py --broker tastytrade` |
| 3:00 PM | EOD scan: `python combined_live.py --broker tastytrade --eod --skip-gex --skip-dynamic` |
| 3:30 PM | Position check: `python combined_live.py --broker tastytrade --broker-check` |

---

## ⚠️ Risk Disclaimer

This is real production trading code with real money. Understand the risks before using:

- **Max loss per spread** = spread width − credit received (not just the SL target)
- **SL only fires when your script runs** — if your process is down, you have zero stop protection
- Spreads can lose their full width if the underlying moves against you and your script doesn't run
- Always size so that max loss is tolerable without the SL firing

---

## Installing Claude Code

Claude Code is Anthropic's official CLI. Install it for yourself or share with others:

### Option 1: npm CLI (recommended for developers)
```bash
npm install -g @anthropic-ai/claude-code
claude  # starts the interactive session
```
Requires Node.js 18+. Get it at [nodejs.org](https://nodejs.org).

### Option 2: Desktop App (easier for non-developers)
Download from [claude.ai/claude-code](https://claude.ai/claude-code) — available for Mac and Windows.

### Option 3: VS Code Extension
Search "Claude Code" in the VS Code Extensions marketplace.

Once installed, navigate to your project directory and run `claude`. Skills in `.claude/skills/` are automatically available as `/skill-name` commands.

---

## License

MIT — fork freely, trade responsibly.
