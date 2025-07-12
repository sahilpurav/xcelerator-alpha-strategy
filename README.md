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

## 🛠️ Installation

Follow these steps to set up the project in a Python virtual environment:

1. **Install Python 3.13.x**
   Ensure you have Python 3.13.x installed on your system. You can verify the version using:
   ```bash
   python3 --version
   ```

2. **Create a Virtual Environment**
   If `venv` is not already installed, you can install it using:
   ```bash
   python3 -m ensurepip --upgrade
   ```
   Then, create a virtual environment:
   ```bash
   python3 -m venv .venv
   ```

3. **Activate the Virtual Environment**
   Activate the virtual environment using the following command:
   ```bash
   source .venv/bin/activate
   ```

4. **Install Dependencies**
   Once the virtual environment is activated, install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the CLI**
   You can now use the CLI commands as described in the [CLI Commands](#️-cli-commands) section.

**Note:** Always ensure the virtual environment is activated before running any commands.

## 🔑 Environment Configuration

The strategy requires a `.env` file to store sensitive credentials and configuration settings. Below is an explanation of the required fields and their purpose:

### Example `.env` File

```bash
KITE_APP_KEY=
KITE_APP_SECRET=
KITE_APP_USERNAME=
KITE_APP_PASSWORD=
KITE_APP_TOTP_KEY=

ENABLE_TWILIO_WHATSAPP=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM_NUMBER=
TWILIO_WHATSAPP_TO_NUMBER=

CACHE=true
```

### Field Descriptions

- **KITE_APP_KEY**: Your Zerodha Kite Connect API key.
- **KITE_APP_SECRET**: Your Zerodha Kite Connect API secret.
- **KITE_APP_USERNAME**: Your Zerodha account username.
- **KITE_APP_PASSWORD**: Your Zerodha account password.
- **KITE_APP_TOTP_KEY**: Time-based OTP key for 2FA login.

- **ENABLE_TWILIO_WHATSAPP**: Set to `true` to enable WhatsApp notifications via Twilio.
- **TWILIO_ACCOUNT_SID**: Twilio account SID for WhatsApp integration.
- **TWILIO_AUTH_TOKEN**: Twilio authentication token.
- **TWILIO_WHATSAPP_FROM_NUMBER**: Twilio WhatsApp sender number.
- **TWILIO_WHATSAPP_TO_NUMBER**: Your WhatsApp number to receive notifications.

- **CACHE**: Set to `true` to enable caching for faster performance.

### Important Notes

1. **Kite Connect API**: This strategy requires access to the Zerodha Kite Connect API, which is a paid service costing approximately ₹500 per month. You need to purchase the API subscription from Zerodha.

2. **Sensitive Information**: Do not share your `.env` file or its contents publicly. It contains sensitive credentials that can compromise your account.

3. **Custom Configuration**: Replace the placeholder values in the `.env` file with your actual credentials and settings before running the strategy.

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

**Parameters:**
- `--top-n`: Number of stocks to select (default: 15)
- `--band`: Band size for portfolio stability (default: 5)
- `--cash`: Cash equivalent symbol (default: "LIQUIDCASE.NS")
- `--rank-day`: Day of week for ranking (e.g., Monday, Tuesday). Defaults to the latest trading day.
- `--dry-run`: Simulate without placing orders (default: False)

#### Add Capital (Top-Up)

Add capital to the existing portfolio:

```bash
# Standard top-up
python cli.py topup

# Dry run mode (simulation without live orders)
python cli.py topup --dry-run
```

**Parameters:**
- `--dry-run`: Simulate without placing orders (default: False)

### 📊 Portfolio Monitoring

#### View Holdings

Display your current portfolio:

```bash
# Formatted table view
python cli.py holdings

# TSV format for spreadsheets
python cli.py holdings --tsv
```

**Parameters:**
- `--tsv`: Output in tab-separated format for spreadsheet import (default: False)

#### View Positions

Show current trading positions:

```bash
# Formatted table view
python cli.py positions

# TSV format for spreadsheets
python cli.py positions --tsv
```

**Parameters:**
- `--tsv`: Output in tab-separated format for spreadsheet import (default: False)

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

**Parameters:**
- `--start`: Start date in YYYY-MM-DD format (required)
- `--end`: End date in YYYY-MM-DD format (optional, defaults to the last trading day)
- `--rebalance-day`: Day of week for rebalancing (default: Wednesday)
- `--band`: Band size for portfolio stability (default: 5)
- `--top-n`: Number of stocks to select (default: 15)
- `--cash`: Cash equivalent symbol (default: "LIQUIDCASE.NS")

#### Cache Management

Reset cached data and strategy state:

```bash
python cli.py clean
```

**Description:**
Deletes all cached files and resets the strategy state, including removing cached price data and output files.

### 📋 CLI Parameters Reference

| Command     | Key Parameters                                             | Description                     |
| ----------- | ---------------------------------------------------------- | ------------------------------- |
| `rebalance` | `--top-n`, `--band`, `--cash`, `--rank-day`, `--dry-run`   | Weekly momentum rebalancing     |
| `topup`     | `--dry-run`                                               | Add capital to existing portfolio |
| `holdings`  | `--tsv`                                                    | View current portfolio holdings |
| `positions` | `--tsv`                                                    | View current trading positions  |
| `backtest`  | `--start`, `--end`, `--rebalance-day`, `--band`, `--cash` | Historical strategy testing     |
| `clean`     | -                                                          | Reset cached data and state     |

## 🔒 Dry Run Mode

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
