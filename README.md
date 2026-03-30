# Option Price Calculator

Streamlit app for multi-leg options: Yahoo Finance quotes, Black–Scholes Greeks, scenario VIX, manual spot overrides, trade price for P/L, and P/L vs date and underlying price (including a heatmap).

## Setup

```bash
cd optionCalc
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run Main.py
```

## Requirements

See `requirements.txt` (Streamlit, yfinance, numpy, pandas, plotly).
