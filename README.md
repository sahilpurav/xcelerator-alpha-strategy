# 📈 Xcelerator Alpha Strategy (Weekly Rebalance)

A fully rule-based, momentum-driven strategy built for Indian equities using Python and Zerodha Kite Connect.  
This strategy selects high-momentum stocks from the Nifty 500 universe and manages live rebalances, top-ups, and exits with automated broker execution.

## 🚀 Features

- ✅ Composite momentum scoring (returns + RSI + 52W high proximity)
- ✅ Weekly rebalancing with band logic (no churn unless needed)
- ✅ Smart top-ups based on current portfolio weights
- ✅ Fully live trading using Zerodha Kite Connect
- ✅ ASM/GSM filtering (long-term and Stage II exclusions)
- ✅ Smart rebalancing with market regime detection
- ✅ **Dry run mode** for rebalancing commands (simulation without live orders)
- ✅ **Complete CLI interface** for all trading operations
- ✅ **Historical backtesting** with customizable parameters
- ✅ **Portfolio monitoring** and position tracking

## 🖥️ CLI Commands

The strategy provides a comprehensive command-line interface for all operations:

### 📈 Live Trading Commands

#### Weekly Rebalance

Execute the core momentum strategy rebalancing with smart market regime detection:

```bash
# Standard rebalance
python cli.py rebalance

# Dry run mode (simulation without live orders)
python cli.py rebalance --dry-run

# Custom parameters
python cli.py rebalance --top-n 20 --band 7 --cash "LIQUIDCASE.NS" --rank-day "Wednesday" --dry-run
```

### 📊 Portfolio Monitoring

#### View Holdings

Display your current portfolio:

```bash
# Formatted table view
python cli.py holdings

# TSV format for spreadsheets
python cli.py holdings --tsv
```

#### View Positions

Show current trading positions:

```bash
python cli.py positions --tsv
```

### 📈 Backtesting & Analysis

#### Historical Backtest

Test the strategy on historical data:

```bash
# Basic backtest
python cli.py backtest --start 2020-01-01

# Custom parameters
python cli.py backtest --start 2020-01-01 --end 2023-12-31 \
  --rebalance-day Wednesday --band 7 --cash "LIQUIDCASE.NS"
```

#### Cache Management

Reset cached data and strategy state:

```bash
python cli.py clean
```

### 📋 CLI Parameters Reference

| Command     | Key Parameters                                             | Description                     |
| ----------- | ---------------------------------------------------------- | ------------------------------- |
| `rebalance` | `--top-n`, `--band`, `--cash`, `--rank-day`, `--dry-run`   | Weekly momentum rebalancing     |
| `holdings`  | `--tsv`                                                    | View current portfolio holdings |
| `positions` | `--tsv`                                                    | View current trading positions  |
| `backtest`  | `--start`, `--end`, `--rebalance-day`, `--band`, `--cash` | Historical strategy testing     |
| `clean`     | -                                                          | Reset cached data and state     |

**Parameter Details:**

- `--dry-run`: Simulates execution without placing live orders (default: False)
- `--top-n`: Number of stocks in portfolio (default: 15)
- `--band`: Portfolio stability band - higher values reduce churn (default: 5)
- `--cash`: Cash equivalent symbol (default: "LIQUIDCASE.NS")
- `--rank-day`: Day of week for ranking (Monday, Tuesday, etc.)
- `--rebalance-day`: Day of week for backtesting rebalances (default: Wednesday)
- `--tsv`: Output in tab-separated format for spreadsheet import

### 🔒 Dry Run Mode

The rebalance command supports dry run mode for safe testing:

```bash
# Test rebalance logic without executing trades
python cli.py rebalance --top-n 20 --band 5 --dry-run
```

**Benefits of Dry Run Mode:**

- ✅ **Zero Risk**: No real trades are executed
- ✅ **Full Simulation**: Complete strategy logic runs as normal
- ✅ **Order Preview**: See exactly what orders would be placed
- ✅ **Portfolio Impact**: Understand how trades would affect your positions
- ✅ **Testing**: Validate strategy behavior before committing capital

**When to Use Dry Run:**

- Before your first live trade
- When testing new parameters
- During market volatility periods
- For educational/learning purposes
- Before significant capital deployment

## 🧯 Troubleshooting

### ❌ Error: `OSError: [Errno 86] Bad CPU type in executable`

This occurs on **Apple M4 Macs** when `undetected-chromedriver` downloads an **Intel-only (x86_64)** ChromeDriver binary, which is not natively supported on Apple Silicon.

---

### ✅ Solution 1: Install Rosetta (Quick Fix)

Install [Rosetta 2](https://support.apple.com/en-us/HT211861), Apple’s Intel-to-ARM translation layer:

```bash
softwareupdate --install-rosetta --agree-to-license
```
