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

## 🧯 Troubleshooting

### ❌ Error: `OSError: [Errno 86] Bad CPU type in executable`

This occurs on **Apple M4 Macs** when `undetected-chromedriver` downloads an **Intel-only (x86_64)** ChromeDriver binary, which is not natively supported on Apple Silicon.

---

### ✅ Solution 1: Install Rosetta (Quick Fix)

Install [Rosetta 2](https://support.apple.com/en-us/HT211861), Apple’s Intel-to-ARM translation layer:

```bash
softwareupdate --install-rosetta --agree-to-license