"""
hw03_yfinance_check.py
Pull AAPL's most recent quarterly revenue and net income using yfinance.
"""

import yfinance as yf

TICKER = "AAPL"

ticker = yf.Ticker(TICKER)
income = ticker.quarterly_income_stmt  # rows = line items, columns = quarter end dates

if income is None or income.empty:
    raise SystemExit(f"No quarterly income statement data returned for {TICKER}.")

# Columns are quarter end dates; pick the most recent one
latest_date = max(income.columns)
latest = income[latest_date]

revenue = latest.get("Total Revenue")
net_income = latest.get("Net Income")

print(f"{TICKER} - Most Recent Quarter")
print(f"Quarter end date: {latest_date.date()}")
print(f"Total Revenue:    ${revenue / 1e6:,.0f} million")
print(f"Net Income:       ${net_income / 1e6:,.0f} million")