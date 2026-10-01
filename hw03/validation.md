# 5 — Validate the Extracted Data
## 5A - Check: Earnings
| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| Apple Q3 FY2026 Revenue | $109,417 M | $109.4 B | Yes |
| Apple Q3 EPS FY2026  Diluted | $2.02 | $2.02 | Yes |

## 5B - Check: Executive Events
| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title: Ben Borders, Principal Accounting Officer | Yes | https://www.wsj.com/market-data/quotes/AAPL/company-people  |
| Event type: Appointment | Yes | https://www.linkedin.com/in/ben-borders-78772a5/ |
| Effective date: 2026-01-01 | Yes | https://www.linkedin.com/in/ben-borders-78772a5/ |


## 5C - Cross-Validation: Earnings via Yahoo Finance
| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | 109,417 M | 109,417 M | Yes |
| Net Income | 29,789 M| 29,789 M| Yes |

## 5D - Pipeline Integrity Checks

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | 20 | Pass |
| `executive_events.csv` row count | At least 0 (document actual) | 23 | Pass |
| `corporate_events_timeline.csv` created | Yes | Yes | Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 0 | Pass |

*Note: Following message is from ai when I copied and pasted the results from the code into Claude. I think it is important to mention

"I refined the executive extraction through three versions to remove false names and recover missed departures; a few minor gaps remain (e.g., Doug McMillon's retirement was not captured)."