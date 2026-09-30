"""
MIS3060 - HW03: SEC EDGAR Earnings History Scraper
Author: Emma Maguire (Villanova University)

One script, one run. It performs all 8 steps:
  1. Sets the SEC-required User-Agent header on every HTTP request
  2. Pulls each company's EDGAR submissions JSON and keeps 8-Ks with Item 2.02
  3. Keeps the 4 most recent such filings per company (one per quarter)
  4. Opens each filing index, finds the earnings press release exhibit (.htm),
     downloads it, and strips the HTML to plain text
  5. Extracts revenue, diluted EPS, net income, and the reporting period
  6. Prints one row per filing as it is processed
  7. Saves everything to hw03/earnings_history.csv
  8. Writes "NOT_FOUND" wherever a field could not be extracted

Requirements:  pip install requests beautifulsoup4
Run from your project folder:  python hw03_earnings_scraper.py
"""

import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Step 1: SEC requires a descriptive User-Agent on every request.
HEADERS = {
    "User-Agent": "MIS3060 Villanova emagui03@villanova.edu",
    "Accept-Encoding": "gzip, deflate",
}

COMPANIES = [
    {"company": "Apple Inc.",            "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation",    "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.",  "ticker": "JPM",  "cik": "0000019617"},
    {"company": "Walmart Inc.",          "ticker": "WMT",  "cik": "0000104169"},
]

FILINGS_PER_COMPANY = 4
NOT_FOUND = "NOT_FOUND"
OUTPUT_PATH = Path("hw03") / "earnings_history.csv"
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "period",
               "revenue_reported", "eps_diluted", "net_income"]

# SEC allows max 10 requests/second; stay well under it.
REQUEST_PAUSE_SECONDS = 0.2

# One shared session so the User-Agent header is applied to ALL requests.
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# --------------------------------------------------------------------------
# HTTP helper
# --------------------------------------------------------------------------

def http_get(url, retries=3):
    """GET a URL with the SEC User-Agent, polite pacing, and simple retries."""
    for attempt in range(1, retries + 1):
        time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            resp = SESSION.get(url, timeout=30)
            if resp.status_code in (429, 503):          # throttled -> back off
                time.sleep(2 * attempt)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            print(f"    retry {attempt} for {url} ({exc})")
            time.sleep(2 * attempt)
    raise RuntimeError(f"Failed to fetch {url}")


# --------------------------------------------------------------------------
# Steps 2 & 3: find the four most recent Item 2.02 8-K filings
# --------------------------------------------------------------------------

def get_earnings_8ks(cik, limit=FILINGS_PER_COMPANY):
    """Return the most recent `limit` 8-K filings whose items include 2.02,
    keeping only one filing per calendar quarter."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = http_get(url).json()
    recent = data["filings"]["recent"]

    selected, quarters_seen = [], set()
    # EDGAR lists "recent" filings newest first.
    for i, form in enumerate(recent["form"]):
        if form != "8-K":
            continue
        items = recent["items"][i] or ""
        if "2.02" not in items:
            continue

        filing_date = recent["filingDate"][i]            # "YYYY-MM-DD"
        year, month = int(filing_date[:4]), int(filing_date[5:7])
        quarter_key = (year, (month - 1) // 3 + 1)
        if quarter_key in quarters_seen:                 # one per quarter
            continue
        quarters_seen.add(quarter_key)

        selected.append({
            "accession": recent["accessionNumber"][i],
            "filing_date": filing_date,
            "primary_doc": recent["primaryDocument"][i],
        })
        if len(selected) == limit:
            break
    return selected


# --------------------------------------------------------------------------
# Step 4: locate the press-release exhibit and convert it to plain text
# --------------------------------------------------------------------------

def filing_index_url(cik, accession):
    folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}"
    return f"{folder}/{accession}-index.htm", folder


def find_press_release_url(cik, filing):
    """Parse the filing index page and return the URL of the earnings
    press release exhibit (normally EX-99.1)."""
    index_url, folder = filing_index_url(cik, filing["accession"])
    soup = BeautifulSoup(http_get(index_url).text, "html.parser")

    best_url, best_score = None, -1
    for table in soup.find_all("table", class_="tableFile"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            link = cells[2].find("a")
            if not link:
                continue
            href = link.get("href", "").replace("/ix?doc=", "")   # inline XBRL viewer links
            doc_type = cells[3].get_text(strip=True).upper()
            description = cells[1].get_text(" ", strip=True).lower()
            if not href.lower().endswith((".htm", ".html")):
                continue
            if not doc_type.startswith("EX-99"):
                continue

            score = 2
            if doc_type == "EX-99.1":
                score += 3
            if any(k in description for k in ("press release", "earnings", "results")):
                score += 2
            if score > best_score:
                best_score = score
                best_url = "https://www.sec.gov" + href if href.startswith("/") else f"{folder}/{href}"

    # Fallback: no EX-99 exhibit found -> use the 8-K's primary document.
    if best_url is None and filing["primary_doc"]:
        best_url = f"{folder}/{filing['primary_doc']}"
    return index_url, best_url


def html_to_text(html):
    """Strip HTML tags, scripts and styles, and collapse whitespace."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = text.replace("\xa0", " ").replace("\u200b", " ")
    text = text.replace("\u2019", "'").replace("\u2014", "-").replace("\u2013", "-")
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Step 5: regex extraction
# --------------------------------------------------------------------------

ORDINALS = {"1": "first", "2": "second", "3": "third", "4": "fourth"}
MONEY = r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(billion|million)"
TABLE_NUMBER = r"\$?\s*\(?\s*(\d{1,3}(?:,\d{3})+)"            # e.g. 14,736  (tables are in millions)
EPS_NUMBER = r"\$\s?(\(?\s*\d+\.\d{2}\s*\)?)"


def _fmt_money(number, unit):
    return f"{number} {unit.lower()}"


def _fmt_eps(raw):
    raw = raw.replace(" ", "")
    if raw.startswith("(") and raw.endswith(")"):   # accounting-style negative
        return "-" + raw.strip("()")
    return raw.strip("()")


def extract_revenue(text):
    # Narrative sentences first (units stated), most specific first.
    narrative = [
        r"(?:total|quarterly|reported|consolidated|net)\s+revenues?\b[^$.]{0,40}?" + MONEY,
        r"(?:^|[.\u2022\u00b7;:] |\b(?:and|with)\s)\s*revenues?\s+(?:was|were|of|reached|totaled)\s+" + MONEY,
        r"\brevenues?\b[^$.]{0,40}?" + MONEY,
    ]
    for pat in narrative:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return _fmt_money(m.group(1), m.group(2))
    # Financial-statement fallback (values reported in millions).
    table = [
        r"Total\s+net\s+revenues?\s+" + TABLE_NUMBER,
        r"Total\s+revenues?\s+" + TABLE_NUMBER,
        r"Total\s+net\s+sales\s+" + TABLE_NUMBER,
        r"\bRevenues?\s+" + TABLE_NUMBER,
        r"\bNet\s+sales\s+" + TABLE_NUMBER,
    ]
    for pat in table:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return _fmt_money(m.group(1), "million")
    return NOT_FOUND


def extract_eps(text):
    patterns = [
        r"diluted\s+(?:earnings|net\s+income)\s+per\s+(?:common\s+)?share\b[^$]{0,40}?" + EPS_NUMBER,
        r"earnings\s+per\s+diluted\s+share\b[^$]{0,40}?" + EPS_NUMBER,
        r"diluted\s+EPS\b[^$]{0,20}?" + EPS_NUMBER,
        r"GAAP\s+EPS\s+(?:of|was)\s+" + EPS_NUMBER,
        r"net\s+income\s+of\s+\$\s?[\d,.]+\s*(?:billion|million),?\s+or\s+" + EPS_NUMBER + r"\s+per\s+share",
        r"\bEPS\s+(?:of|was)\s+" + EPS_NUMBER,
        r"\bDiluted\s+" + EPS_NUMBER,                  # income-statement line
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return _fmt_eps(m.group(m.lastindex))
    return NOT_FOUND


def extract_net_income(text):
    narrative = [
        r"net\s+income(?:\s+attributable\s+to\s+[A-Z][\w.&, ]{0,40}?)?\s+(?:was|of|totaled|were)\s+" + MONEY,
        r"net\s+income\b[^$.]{0,30}?" + MONEY,
    ]
    for pat in narrative:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return _fmt_money(m.group(1), m.group(2))
    table = [
        r"Net\s+income\s+attributable\s+to\s+(?!noncontrolling)[A-Z][\w.&, ]{0,40}?\s+" + TABLE_NUMBER,
        r"\bNet\s+income\s+" + TABLE_NUMBER,
    ]
    for pat in table:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return _fmt_money(m.group(1), "million")
    return NOT_FOUND


def extract_period(text):
    """Return something like 'fourth quarter fiscal 2024'. Uses the earliest
    match in the document (usually the headline)."""
    candidates = []

    # "fourth quarter fiscal 2024", "third-quarter 2024", "Fourth Quarter and Fiscal 2025"
    for m in re.finditer(
        r"\b(first|second|third|fourth)[\s-]+quarter\s+(?:of\s+)?(?:and\s+)?(fiscal\s+)?(?:year\s+)?(\d{4})\b",
        text, re.IGNORECASE):
        fiscal = "fiscal " if m.group(2) else ""
        candidates.append((m.start(), f"{m.group(1).lower()} quarter {fiscal}{m.group(3)}"))

    # "fiscal 2024 fourth quarter" (Apple style)
    for m in re.finditer(
        r"\bfiscal\s+(?:year\s+)?(\d{4})\s+(first|second|third|fourth)\s+quarter\b",
        text, re.IGNORECASE):
        candidates.append((m.start(), f"{m.group(2).lower()} quarter fiscal {m.group(1)}"))

    # "Q3 FY25" / "Q4 fiscal 2025" (Walmart / NVIDIA style)
    for m in re.finditer(r"\bQ([1-4])\s*(?:FY|fiscal\s+(?:year\s+)?)\s*'?(\d{2,4})\b",
                         text, re.IGNORECASE):
        year = m.group(2)
        year = "20" + year if len(year) == 2 else year
        candidates.append((m.start(), f"{ORDINALS[m.group(1)]} quarter fiscal {year}"))

    if candidates:
        return min(candidates)[1]

    # Fallback: "quarter ended September 30, 2024" (Microsoft style)
    m = re.search(r"quarter\s+ended\s+([A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4})", text)
    if m:
        return f"quarter ended {m.group(1)}"
    return NOT_FOUND


# --------------------------------------------------------------------------
# Main: run steps 2-8 for every company in a single pass
# --------------------------------------------------------------------------

def main():
    rows = []
    for co in COMPANIES:
        print(f"\n=== {co['company']} ({co['ticker']}) ===")
        try:
            filings = get_earnings_8ks(co["cik"])
        except Exception as exc:
            print(f"  Could not load submissions for {co['ticker']}: {exc}")
            continue
        if not filings:
            print(f"  No Item 2.02 8-K filings found for {co['ticker']}")

        for filing in filings:
            row = {
                "company": co["company"],
                "ticker": co["ticker"],
                "cik": co["cik"],
                "filing_date": filing["filing_date"],
                "period": NOT_FOUND,
                "revenue_reported": NOT_FOUND,
                "eps_diluted": NOT_FOUND,
                "net_income": NOT_FOUND,
            }
            try:
                _, exhibit_url = find_press_release_url(co["cik"], filing)
                if exhibit_url:
                    text = html_to_text(http_get(exhibit_url).text)
                    row["period"] = extract_period(text)
                    row["revenue_reported"] = extract_revenue(text)
                    row["eps_diluted"] = extract_eps(text)
                    row["net_income"] = extract_net_income(text)
            except Exception as exc:
                print(f"  Error processing {filing['accession']}: {exc}")

            # Step 8 safety net: never leave a blank cell.
            for key in CSV_COLUMNS:
                if row[key] in ("", None):
                    row[key] = NOT_FOUND

            rows.append(row)

            # Step 6: print as each filing is processed.
            def dollar(v):
                return v if v == NOT_FOUND else f"${v}"
            print(f"{row['ticker']} | {row['period']} | "
                  f"Revenue: {dollar(row['revenue_reported'])} | "
                  f"EPS: {dollar(row['eps_diluted'])} | "
                  f"Net Income: {dollar(row['net_income'])}")

    # Step 7: save to CSV.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUTPUT_PATH.resolve()}")
    missing = sum(1 for r in rows for k in CSV_COLUMNS if r[k] == NOT_FOUND)
    print(f"Cells marked {NOT_FOUND}: {missing}")


if __name__ == "__main__":
    main()