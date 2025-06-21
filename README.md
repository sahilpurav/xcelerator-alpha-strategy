# 📈 Xcelerator Alpha Strategy (Weekly Rebalance)

A fully rule-based, momentum-driven strategy built for Indian equities using Python and Zerodha Kite Connect.  
This strategy selects high-momentum stocks from the Nifty 500 universe and manages live rebalances, top-ups, and exits with automated broker execution.

## 🚀 Features

- ✅ Composite momentum scoring (returns + RSI + 52W high proximity)
- ✅ Weekly rebalancing with band logic (no churn unless needed)
- ✅ Smart top-ups based on current portfolio weights
- ✅ Fully live trading using Zerodha Kite Connect
- ✅ ASM/GSM filtering (long-term and Stage II exclusions)
- ✅ Intelligent capital recycling (no partial sells, top-up underweight winners)
- ✅ **Dry run mode** for all trading commands (simulation without live orders)
- ✅ Normalized ranks for clear comparison
- ✅ **Weight optimization** for ranking algorithm parameters
- ✅ **Complete CLI interface** for all trading operations
- ✅ **Historical backtesting** with customizable parameters
- ✅ **Portfolio monitoring** and position tracking

## 🖥️ CLI Commands

The strategy provides a comprehensive command-line interface for all operations:

### 📈 Live Trading Commands

All live trading commands support **dry run mode** using the `--dry-run` flag, which simulates the execution without placing actual orders. This is essential for testing and validation before committing real capital.

#### Initial Investment
Start your portfolio with fresh capital:
```bash
# Interactive mode with prompts
python cli.py initial

# Direct parameter specification
python cli.py initial --amount 100000 --top-n 15

# Dry run mode (simulation without live orders)
python cli.py initial --amount 100000 --top-n 15 --dry-run
```

#### Weekly Rebalance  
Execute the core momentum strategy rebalancing:
```bash
# Standard rebalance
python cli.py rebalance

# Dry run mode (simulation without live orders)
python cli.py rebalance --dry-run

# Custom parameters
python cli.py rebalance --top-n 20 --band 7 --dry-run
```

#### Capital Top-up
Add more capital to existing positions:
```bash
# Interactive mode with prompts
python cli.py topup

# Direct parameter specification with dry run
python cli.py topup --amount 50000 --dry-run
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
  --rebalance-day Wednesday --band 7
```

#### Stock Rankings for Specific Date
Get momentum rankings for any historical date:
```bash
# Basic ranking for a specific date
python cli.py rank --date 2024-06-05

# Custom parameters with different weights and display count
python cli.py rank --date 2024-06-05 --weights "0.7,0.2,0.1" --top-n 20

# Force cache refresh if needed
python cli.py rank --date 2024-06-05 --force-refresh
```

#### Cache Management
Reset cached data and strategy state:
```bash
python cli.py clean
```

### 📋 CLI Parameters Reference

| Command | Key Parameters | Description |
|---------|----------------|-------------|
| `initial` | `--amount`, `--top-n`, `--dry-run` | Start portfolio with fresh capital (interactive prompts) |
| `rebalance` | `--top-n`, `--band`, `--dry-run` | Weekly momentum rebalancing |
| `topup` | `--amount`, `--dry-run` | Add capital to existing positions (interactive prompt) |
| `holdings` | `--tsv` | View current portfolio holdings |
| `positions` | `--tsv` | View current trading positions |
| `backtest` | `--start`, `--end`, `--rebalance-day`, `--band` | Historical strategy testing |
| `rank` | `--date`, `--weights`, `--top-n`, `--force-refresh` | Get stock rankings for specific date |
| `clean` | - | Reset cached data and state |

**Parameter Details:**
- `--dry-run`: Simulates execution without placing live orders (default: False)
- `--amount`: Capital amount in ₹ (prompted if not provided)
- `--top-n`: Number of stocks in portfolio (default: 15 for initial/rebalance, 50 for rank)
- `--band`: Portfolio stability band - higher values reduce churn (default: 5)
- `--tsv`: Output in tab-separated format for spreadsheet import

### 🔒 Dry Run Mode

All trading commands (`initial`, `rebalance`, `topup`) support dry run mode for safe testing:

```bash
# Test initial investment without placing orders
python cli.py initial --amount 100000 --top-n 15 --dry-run

# Test rebalance logic without executing trades
python cli.py rebalance --top-n 20 --band 5 --dry-run

# Test capital top-up without placing orders
python cli.py topup --amount 50000 --dry-run
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

## ⚖️ Weight Optimization

The strategy uses a composite momentum score based on three factors:
- **Return Rank** (default weight: 0.8) - Stock returns over various periods
- **RSI Rank** (default weight: 0.1) - Relative Strength Index ranking
- **Proximity Rank** (default weight: 0.1) - Distance from 52-week high

You can optimize these weights to maximize CAGR while maintaining risk constraints.

### 🔍 Compare Weight Combinations

Test specific weight combinations and compare their performance:

```bash
# Compare two weight combinations
python cli.py compare-weights "0.8,0.1,0.1" "0.6,0.2,0.2" --start 2020-01-01

# Test a combination against common alternatives
python cli.py compare-weights "0.7,0.2,0.1" --start 2020-01-01 --include-common

# Specify end date and portfolio parameters
python cli.py compare-weights "0.5,0.3,0.2" --start 2020-01-01 --end 2023-12-31 \
  --top-n 20 --band 3 --max-dd -15.0
```

### 🎯 Optimize Weights Automatically

Find optimal weights using mathematical optimization:

```bash
# Grid search optimization (comprehensive but slower)
python cli.py optimize-weights --start 2020-01-01 --method grid --step 0.1

# Quick grid search with coarse step
python cli.py optimize-weights --start 2020-01-01 --method grid --step 0.2

# Scipy optimization (faster, mathematical approach)
python cli.py optimize-weights --start 2020-01-01 --method scipy

# Custom constraints and parameters
python cli.py optimize-weights --start 2020-01-01 --end 2023-12-31 \
  --method grid --step 0.05 --max-dd -20.0 --top-n 20
```

### 📊 Weight Optimization Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--start` | Start date for backtest (YYYY-MM-DD) | Required |
| `--end` | End date for backtest | Today |
| `--method` | Optimization method: `grid` or `scipy` | `grid` |
| `--step` | Grid search step size (0.05=fine, 0.1=normal, 0.2=coarse) | `0.1` |
| `--max-dd` | Maximum allowed drawdown percentage | `-20.0` |
| `--top-n` | Number of stocks in portfolio | `15` |
| `--band` | Band size for portfolio stability | `5` |
| `--include-common` | Include predefined weight combinations | `false` |
| `--save-results` | Save results to CSV file | `true` |

### 📊 Stock Ranking Parameters

The `rank` command provides detailed momentum rankings for any historical date:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--date` | Date for ranking calculation (YYYY-MM-DD) | Required |
| `--weights` | Ranking weights as 'return,rsi,proximity' (must sum to 1.0) | `0.8,0.1,0.1` |
| `--top-n` | Number of top stocks to display | `50` |
| `--save-results` | Save results to CSV file | `true` |
| `--force-refresh` | Force cache refresh even if data exists | `false` |

**Weight Components:**
- **Return Weight**: Importance of multi-timeframe returns (22, 44, 66 days)
- **RSI Weight**: Importance of multi-timeframe RSI momentum (22, 44, 66 days)  
- **Proximity Weight**: Importance of proximity to 52-week high

**Cache Intelligence:**
The command automatically ensures 400 days of historical data is available before the ranking date. If the cache is missing data or stale, it will regenerate from the required start date.

### 💡 Weight Optimization Tips

- **Start with coarse search**: Use `--step 0.2` for quick exploration
- **Refine promising areas**: Use `--step 0.05` around good combinations  
- **Consider time periods**: Optimal weights may vary across market cycles
- **Balance risk vs return**: Higher return weights often increase both CAGR and drawdown
- **Use scipy for fine-tuning**: After grid search identifies good regions

Results are automatically saved to `output/` folder with timestamp and can be used for further analysis.

## 🧯 Troubleshooting

### ❌ Error: `OSError: [Errno 86] Bad CPU type in executable`

This occurs on **Apple M4 Macs** when `undetected-chromedriver` downloads an **Intel-only (x86_64)** ChromeDriver binary, which is not natively supported on Apple Silicon.

---

### ✅ Solution 1: Install Rosetta (Quick Fix)

Install [Rosetta 2](https://support.apple.com/en-us/HT211861), Apple’s Intel-to-ARM translation layer:

```bash
softwareupdate --install-rosetta --agree-to-license
```