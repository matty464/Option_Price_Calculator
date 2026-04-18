# Option Price Calculator

Streamlit app for multi-leg options: Yahoo Finance quotes, Black–Scholes Greeks, scenario VIX, manual spot overrides, trade price for P/L, and P/L vs date and underlying price (including a heatmap).

## Disclaimer

This software is provided for **educational and informational purposes only**. It is **not** financial, investment, tax, or legal advice, and **nothing here is a recommendation** to buy, sell, or hold any security or derivative.

- **Accuracy:** Outputs depend on third-party data (e.g. Yahoo Finance), simplified models (e.g. Black–Scholes without dividends, static vol assumptions), and your inputs. Quotes can be **delayed or wrong**; Greeks, implied vol, and P/L scenarios are **approximations** and may **differ materially** from your broker, the exchange, or realized outcomes.

- **Risk:** Options involve substantial risk. You are solely responsible for your trading and should consult a **qualified professional** before making investment decisions.

The authors and contributors **disclaim liability** for any loss or damage arising from use of this tool.

## Setup

Clone the repo (or download the project folder), then from the project root:

```bash
cd Option_Price_Calculator   # or path to your copy, e.g. optionCalc
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## How to run the app

Start Streamlit with **`Main.py`** (capital **M** — important on Linux/macOS):

```bash
streamlit run Main.py
```

Streamlit prints a local URL (usually `http://localhost:8501`). Open it in your browser. Stop the server with `Ctrl+C` in the terminal.

If `streamlit` is not found, activate the virtual environment first, or run:

```bash
python -m streamlit run Main.py
```

### Desktop bundles (PyInstaller)

- **macOS:** build on a Mac → **`OptionPriceCalculator.app`** or a folder with a Unix executable. See **[BUILD_MAC.md](BUILD_MAC.md)**.
- **Windows:** build on Windows → **`OptionPriceCalculator.exe`** + `_internal` folder (zip the whole directory). See **[BUILD_WINDOWS.md](BUILD_WINDOWS.md)**.

Entry script for both: **`launcher.py`** (same behavior as `streamlit run Main.py`, opens the browser automatically).

## Requirements

See `requirements.txt` (Streamlit, yfinance, numpy, pandas, plotly).

## Support / Donations

If you find this tool useful, tips are appreciated — no obligation whatsoever!

| Chain | Address |
|---|---|
| **Bitcoin (BTC)** | `bc1qemvr8eq33z3sgvrdfmls339grdq3snea9cre04` |
| **Ethereum (ETH)** | `0x7262a0d14a092605B8592ca74219930cBeF09C8A` |
| **Solana (SOL)** | `5QS5LHaeF8kC72Ua9HuRszh4nr2uyNMsHVksaZhaGgd1` |
| **Dogecoin (DOGE)** | `D7FYhFWqUzL4xunf84K8obyVaAcn9ByVxs` |
| **Bitcoin Cash (BCH)** | `bitcoincash:qrppntvg7j39jdutca4sgndk3phflhcvz5yf9gjxts` |
| **Litecoin (LTC)** | `ltc1qte5jwedkcqm95y8g76m3ltrlghrj5e2qd5gw4z` |
