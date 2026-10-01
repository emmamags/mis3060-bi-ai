# AI Usage Log - HW03
## A - Prompts sent to Claude
### Specification A:
You are my colleague at a popular tech firm who is an expert in all things coding. I need you to produce one single Python script that performs all of the following 7 steps in a single run. Do not perform the following items in separate scripts. Let me know if you need any clarification on any of these items.

Use exactly these five companies and CIKs (do not look them up):

| Company | Ticker | SEC CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

1. Sets the SEC EDGAR User-Agent header to "MIS3060 Villanova emagui03@villanova.edu" on all HTTP requests

2. For each of the five companies, queries the EDGAR submissions API at https://data.sec.gov/submissions/CIK{cik}.json and filters for 8-K filings where the items field contains "2.02" (Results of Operations)

3. Selects the most recent four such filings per company (one per quarter)

4. For each filing, constructs the filing index URL, identifies the earnings press release exhibit (.htm file), downloads it, and strips HTML to plain text

5.  Extracts from the plain text: quarterly revenue (as a number in millions or billions), diluted EPS, net income, and the reporting period (e.g., "fourth quarter fiscal 2024")

6.  Prints the extracted row for each filing as it is processed, in the format: [Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X

7. Saves all rows to hw03/earnings_history.csv with columns: company, ticker, cik, filing_date, period, revenue_reported, eps_diluted, net_income

8. Where a field cannot be extracted (regex returns no match), stores the string "NOT_FOUND" rather than leaving the cell blank — blank cells and missing data are two different things

### Specification B:
You are my colleague at a popular tech firm who is an expert in all things coding. I need you to produce one single Python script that performs all of the following 7 steps in a single run. Do not perform the following items in separate scripts. Let me know if you need any clarification on any of these items.

Use exactly these five companies and CIKs (do not look them up):

| Company | Ticker | SEC CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

1. Sets the SEC EDGAR User-Agent header to "MIS3060 Villanova emagui03@villanova.edu" on all HTTP requests

2. For each of the five companies, queries the EDGAR submissions API and filters for 8-K filings where the items field contains "5.02" (Departure of Directors or Officers) and the filingDate is within the past 12 months

3. For each matching filing, downloads the full 8-K text, strips HTML, and extracts: event type ("departure" or "appointment" or "both"), the person's full name, their title, and the effective date of the change

4. If a filing reports multiple events (e.g., one departure and one appointment), creates a separate row for each event

5. Prints each extracted event as it is processed: [Ticker] | [Date] | [Event Type] | [Name] | [Title]

6. If no Item 5.02 filings are found for a company in the past 12 months, prints [Ticker]: No executive events in past 12 months — this is valid data, not an error

7. Saves all events to hw03/executive_events.csv with columns: company, ticker, cik, filing_date, event_type, person_name, title, effective_date

### Timeline prompt
Write a Python script that reads `hw03/earnings_history.csv` and `hw03/executive_events.csv`. Do the following:
1. For each executive event in the events table, calculate the number of days between the executive event's `filing_date` and the nearest earnings filing date for the same company in the earnings table. Call this `days_to_nearest_earnings`.
 2. Add a column `event_timing` that categorizes each executive event as: `'before earnings'` if the event came before the nearest earnings filing, `'after earnings'` if it came after, or `'same week'` if within 7 days of an earnings filing. 
 3. Save the combined table to `hw03/corporate_events_timeline.csv` with all columns from both source tables plus `days_to_nearest_earnings` and `event_timing`. 
 4. Print a summary: for each company, list any executive events and whether they occurred before or after the nearest earnings announcement. 
 5. Print a final count: how many events occurred before vs. after an earnings announcement across all five companies.


## B - Iterations / fixes

### Earnings pipeline (no regex fixes needed):

1. Claude asked which five companies to use because I didn't list them, so I added the company table to both specifications.

2. Before running the code I put it into another Claude cowork to review and it found a bug: the line .replace("", " ") would have inserted a space between every character and broken all extraction. I had Claude recomend and changed it to .replace("\u200b", " ").

3. The script then extracted all 20 rows (5 companies × 4 quarters) with 0 NOT_FOUND values, so no follow-up regex fixes were needed.

### Executive events pipeline (3 versions):

#### v1: ran successfully but produced about 14 false-positive "names" such as "Target Award," "Transition Date," "Sam's Club," and "Non-Competition Agreements." Most came from NVIDIA's compensation-only filing and Walmart's legal language.

#### v2: I asked Claude to add stop words, skip compensation-only filings, merge partial names (e.g., "Nora Johnson" into "Suzanne Nora Johnson"), and only use "both" when one person changes roles. This removed all the junk, but it overcorrected: it dropped two real NVIDIA departures (Donald Robertson and Ajay Puri) and labeled Apple's Kate Adams as an appointment when she was retiring.

#### v3: I gave Claude the specific missing and mislabeled events. v3 restored the NVIDIA departures, fixed Kate Adams, recovered Walmart's Kathryn McLay, and improved titles (e.g., JPM "Co-President" instead of just "CEO"). The final file has 23 events. A few gaps remain, such as Walmart CEO Doug McMillon's retirement not being captured.
 
 * Note: I had ai help me describe what went wrong in each version for this log.

## C - Something AI did that I didn't specify

One thing the AI did that I did not ask for was rename the filing_date column from each table to event_filing_date and earnings_filing_date in the timeline script. This was the correct and smart decision, because when the two files were merged into the timeline CSV, there would have been two columns with the same name and the reader would not have been able to discern which one was which.