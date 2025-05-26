## 🧯 Troubleshooting

### ❌ Error: `OSError: [Errno 86] Bad CPU type in executable`

This occurs on **Apple M4 Macs** when `undetected-chromedriver` downloads an **Intel-only (x86_64)** ChromeDriver binary, which is not natively supported on Apple Silicon.

---

### ✅ Solution 1: Install Rosetta (Quick Fix)

Install [Rosetta 2](https://support.apple.com/en-us/HT211861), Apple’s Intel-to-ARM translation layer:

```bash
softwareupdate --install-rosetta --agree-to-license