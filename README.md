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
- ✅ Dry run and confirmation mode before live orders
- ✅ Normalized ranks for clear comparison
- ✅ **Weight optimization** for ranking algorithm parameters
- ✅ **Complete CLI interface** for all trading operations
- ✅ **Historical backtesting** with customizable parameters
- ✅ **Portfolio monitoring** and position tracking

## 🖥️ CLI Commands

The strategy provides a comprehensive command-line interface for all operations:

### 📈 Live Trading Commands

#### Initial Investment
Start your portfolio with fresh capital:
```bash
python cli.py initial --amount 100000 --top-n 15
```

#### Weekly Rebalance  
Execute the core momentum strategy rebalancing:
```bash
# Standard rebalance
python cli.py rebalance

# Preview mode (dry run)
python cli.py rebalance --preview

# Custom band size (higher = less portfolio churn)
python cli.py rebalance --band 7
```

#### Capital Top-up
Add more capital to existing positions:
```bash
python cli.py topup --amount 50000 --preview
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

#### Cache Management
Reset cached data and strategy state:
```bash
python cli.py clear-cache
```

### 📋 CLI Parameters Reference

| Command | Key Parameters | Description |
|---------|----------------|-------------|
| `initial` | `--amount`, `--top-n` | Start portfolio with fresh capital |
| `rebalance` | `--preview`, `--band` | Weekly momentum rebalancing |
| `topup` | `--amount`, `--preview` | Add capital to existing positions |
| `holdings` | `--tsv` | View current portfolio holdings |
| `positions` | `--tsv` | View current trading positions |
| `backtest` | `--start`, `--end`, `--rebalance-day`, `--band` | Historical strategy testing |
| `clear-cache` | - | Reset cached data and state |

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
| `--max-dd` | Maximum allowed drawdown percentage | `-17.0` |
| `--top-n` | Number of stocks in portfolio | `15` |
| `--band` | Band size for portfolio stability | `5` |
| `--include-common` | Include predefined weight combinations | `false` |
| `--save-results` | Save results to CSV file | `true` |

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