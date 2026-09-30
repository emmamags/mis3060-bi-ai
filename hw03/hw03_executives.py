"""
MIS3060 - HW03: Executive change events (8-K Item 5.02) from SEC EDGAR  [v2]
----------------------------------------------------------------------
One script, one run. For each of five companies it:
  1. Sends every HTTP request with the required SEC User-Agent header
  2. Pulls the EDGAR submissions API and keeps 8-Ks whose `items` contain
     "5.02" and whose filingDate falls in the past 12 months
  3. Downloads each 8-K, strips the HTML, and extracts event type
     (departure / appointment / both), person name, title, effective date
  4. Writes one row per person-event (a filing with a departure AND an
     appointment becomes two rows)
  5. Prints each event as it is processed
  6. Prints "<TICKER>: No executive events in past 12 months" when a company
     has no Item 5.02 filings in the window (valid data, not an error)
  7. Saves everything to hw03/executive_events.csv

Requirements:  pip install requests beautifulsoup4
Run:           python executive_events.py
"""

import csv
import html
import os
import re
import sys
import time
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
USER_AGENT = "MIS3060 Villanova emagui03@villanova.edu"

COMPANIES = [
    {"company": "Apple Inc.",            "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation",    "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.",  "ticker": "JPM",  "cik": "0000019617"},
    {"company": "Walmart Inc.",          "ticker": "WMT",  "cik": "0000104169"},
]

OUTPUT_PATH = os.path.join("hw03", "executive_events.csv")
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "event_type",
               "person_name", "title", "effective_date"]

TODAY = date.today()
CUTOFF = TODAY - timedelta(days=365)          # "past 12 months"
REQUEST_PAUSE = 0.15                          # stay well under SEC's 10 req/sec

# Make sure the em dash etc. print cleanly in a Windows terminal
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# --------------------------------------------------------------------------
# Step 1: HTTP session with the SEC User-Agent on every request
# --------------------------------------------------------------------------
session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
})


def sec_get(url, as_json=False, retries=4):
    """GET a URL from SEC with the User-Agent header, polite pacing, and retries."""
    for attempt in range(1, retries + 1):
        time.sleep(REQUEST_PAUSE)
        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            print(f"   (network error: {exc}; retrying)")
            time.sleep(2 * attempt)
            continue
        if resp.status_code == 200:
            return resp.json() if as_json else resp.text
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            time.sleep(2 * attempt)
            continue
        resp.raise_for_status()
    return None


# --------------------------------------------------------------------------
# Step 2: find Item 5.02 8-Ks filed in the past 12 months
# --------------------------------------------------------------------------
def _rows_from_block(block):
    """Turn EDGAR's column-oriented arrays into a list of dicts."""
    keys = ["accessionNumber", "filingDate", "reportDate", "form",
            "items", "primaryDocument"]
    n = len(block.get("accessionNumber", []))
    return [{k: (block.get(k) or [""] * n)[i] for k in keys} for i in range(n)]


def get_502_filings(cik):
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = sec_get(url, as_json=True)

    filings = _rows_from_block(data["filings"]["recent"])

    # Heavy filers (e.g., JPM files thousands of note prospectuses) can push
    # 12 months of history out of "recent" into extra pages. Fetch those too.
    for extra in data["filings"].get("files", []):
        if extra.get("filingTo", "") >= CUTOFF.isoformat():
            page = sec_get(f"https://data.sec.gov/submissions/{extra['name']}", as_json=True)
            filings.extend(_rows_from_block(page))

    matches, seen = [], set()
    for f in filings:
        if f["form"] != "8-K":
            continue
        if "5.02" not in (f["items"] or ""):
            continue
        try:
            fdate = datetime.strptime(f["filingDate"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if fdate < CUTOFF or f["accessionNumber"] in seen:
            continue
        seen.add(f["accessionNumber"])
        matches.append(f)

    matches.sort(key=lambda f: f["filingDate"])   # oldest first
    return matches


# --------------------------------------------------------------------------
# Step 3a: download the 8-K and strip HTML
# --------------------------------------------------------------------------
def download_8k_text(cik, filing):
    cik_int = str(int(cik))
    acc = filing["accessionNumber"]
    acc_nodash = acc.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}"

    if filing.get("primaryDocument"):
        raw = sec_get(f"{base}/{filing['primaryDocument']}")
    else:
        # Fall back to the full submission file and keep only the 8-K document
        raw = sec_get(f"{base}/{acc}.txt")
        m = re.search(r"<DOCUMENT>\s*<TYPE>8-K.*?</DOCUMENT>", raw, re.S | re.I)
        raw = m.group(0) if m else raw

    return clean_text(raw)


def clean_text(raw):
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ")
    text = html.unescape(text)
    text = (text.replace("\xa0", " ").replace("\u2019", "'").replace("\u2018", "'")
                .replace("\u201c", '"').replace("\u201d", '"')
                .replace("\u2013", "-").replace("\u2014", "-"))
    return re.sub(r"\s+", " ", text).strip()


def isolate_item_502(text):
    """Return just the Item 5.02 section (falls back to the whole text)."""
    starts = [m.start() for m in re.finditer(r"Item\s*5\.02", text, re.I)]
    if not starts:
        return text
    # Skip a table-of-contents mention if a later, longer section exists
    start = starts[-1] if len(starts) > 1 and len(text) - starts[-1] > 300 else starts[0]
    tail = text[start + 9:]
    end = re.search(r"Item\s*\d{1,2}\.\d{2}|SIGNATURES?\b|Pursuant to the requirements of the Securities",
                    tail, re.I)
    return text[start: start + 9 + (end.start() if end else len(tail))]


# --------------------------------------------------------------------------
# Step 3b: rule-based extraction of names, titles, event types, dates
# --------------------------------------------------------------------------
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9

DATE_RE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
    r"Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})")

DEPART_RE = re.compile(
    r"\b(retire[sd]?|retiring|retirement|resign(?:ed|s|ing|ation)?|step(?:ped|s|ping)? down|"
    r"depart(?:ure|ed|s|ing)?|terminat(?:e|ed|es|ion)|will not stand for re-?election|"
    r"not to stand for re-?election|not (?:to )?seek re-?election|(?:leave|leaving|left) the (?:Company|Firm|Board)|"
    r"separat(?:e|ed|ion) from|ceas(?:e|ed|es) to (?:serve|be)|will no longer serve|"
    r"transition(?:ed|ing)? (?:out|from))\b", re.I)

APPOINT_RE = re.compile(
    r"\b(appoint(?:ed|s|ing|ment)?|elect(?:ed|s|ing|ion)?|named|nominat(?:ed|es|ion)|promot(?:ed|ion)|"
    r"hired|will become|to become|will (?:assume|serve as)|to serve as|"
    r"join(?:ed|s|ing)? (?:the Company|the Firm|us) as)\b", re.I)

# Phrases that look like appointments but are not (removed before matching)
APPOINT_FALSE_POS = re.compile(
    r"re-?election|continue[sd]? to serve(?: as)?|stand for election|"
    r"remain(?:s|ed)?(?: as| in)?|serve as (?:an )?advisor|named executive officers?", re.I)

# Compensation language: if present, a name only counts when a departure or
# appointment keyword sits close to it (otherwise it's a pay-only disclosure)
COMP_RE = re.compile(r"base salar(?:y|ies)|target award|bonus", re.I)
KEYWORD_NEAR_CHARS = 100

SUCCEED_RE = re.compile(r"\b(?:will )?succeed(?:s|ed|ing)?\b|\bsuccessor to\b", re.I)

TITLE_ATOMS = [
    r"(?:Executive |Senior |Corporate )*Vice President(?:,? (?:of )?(?:[A-Z][A-Za-z&]+|&)(?: (?:[A-Z][A-Za-z&]+|&|and))*)?",
    r"Chief (?:[A-Z][a-z]+ ){1,3}Officer",
    r"(?:CEO|CFO|COO|CTO|CAO|CHRO|CLO)",
    r"President",
    r"(?:Non-Executive |Independent |Executive )?Chair(?:man|woman|person)?(?: of the Board(?: of Directors)?)?",
    r"Lead Independent Director",
    r"General Counsel",
    r"(?:Corporate )?Secretary",
    r"(?:Corporate )?(?:Controller|Treasurer)",
    r"Principal (?:Accounting|Financial|Executive) Officer",
    r"(?:[Ii]ndependent |[Nn]on-[Ee]mployee )?[Dd]irector",
    r"member of the Board(?: of Directors)?",
]
TITLE_RE = re.compile(r"\b(?:" + "|".join(TITLE_ATOMS) + r")\b")
TITLE_JOINERS = {", ", " and ", ", and ", " & ", " and the ", "; "}

# Capitalized words that are NOT part of a person's name
STOP_WORDS = set("""
the a an and of for to in on at by as with from upon following pursuant effective
company corporation inc incorporated co llc corp board directors director chief officer
executive vice president senior chair chairman chairwoman lead independent committee
compensation audit nominating governance annual meeting shareholders stockholders
agreement plan letter exhibit press release current report form item section securities
exchange act commission sec financial operating technology global general counsel
secretary treasurer controller principal accounting human resources united states
apple microsoft nvidia jpmorgan chase walmart america north international bank na
mr ms mrs dr jr sr ii iii iv his her their he she they it this that such also
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday fiscal year quarter
retirement resignation appointment election on however additionally consumer community
commercial investment corporate asset wealth management banking markets services
worldwide operations marketing sales legal risk people u s usa new york
certain officers arrangements compensatory departure departures appointments elections
award awards target targets opportunity salary incentive equity date covenant agreement
agreements competition club
""".split())

NAME_TOKEN = r"(?:[A-Z][a-zA-Z'\-]+|[A-Z]\.)"
NAME_CANDIDATE_RE = re.compile(rf"{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{1,4}}(?:,?\s+(?:Jr\.|Sr\.|II|III|IV))?")
HONORIFIC_RE = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.\s+([A-Z][a-zA-Z'\-]+)")


def _is_stop(tok):
    return tok.strip(".,").lower() in STOP_WORDS


def find_full_names(text):
    """Return [(name, start, end)] for things that look like full personal names."""
    found = []
    for m in NAME_CANDIDATE_RE.finditer(text):
        tokens = m.group(0).split()
        # break the candidate into runs of non-stop tokens
        run, run_start = [], m.start()
        pos = m.start()
        runs = []
        for tok in tokens:
            tstart = text.index(tok, pos)
            pos = tstart + len(tok)
            if _is_stop(tok):
                if run:
                    runs.append((run, run_start))
                run = []
            else:
                if not run:
                    run_start = tstart
                run.append(tok)
        if run:
            runs.append((run, run_start))
        for run, rstart in runs:
            words = [t for t in run if not re.fullmatch(r"[A-Z]\.", t)]
            if len(run) >= 2 and len(words) >= 2 and not run[0].endswith("."):
                name = " ".join(run).rstrip(",")
                # leading single initial like "J. Smith" is allowed via words>=2 check above
                found.append((name, rstart, rstart + len(name)))
    return found


def split_sentences(text):
    protected = re.sub(r"\b(Mr|Ms|Mrs|Dr|Jr|Sr|Inc|Co|Corp|No|St|U\.S)\.", r"\1<DOT>", text)
    protected = re.sub(r"\b([A-Z])\.", r"\1<DOT>", protected)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", protected)
    return [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]


def parse_date(s):
    m = DATE_RE.search(s)
    if not m:
        return None
    month = MONTHS.get(m.group(1).lower().rstrip("."), MONTHS.get(m.group(1)[:3].lower()))
    try:
        return date(int(m.group(3)), month, int(m.group(2))).isoformat()
    except (TypeError, ValueError):
        return None


def title_spans(sentence):
    """All titles in a sentence as (start, end), with adjacent pieces merged."""
    matches = list(TITLE_RE.finditer(sentence))
    if not matches:
        return []
    # merge adjacent atoms: "Executive Vice President and Chief Financial Officer"
    merged, cur = [], [matches[0].start(), matches[0].end()]
    for m in matches[1:]:
        if sentence[cur[1]:m.start()] in TITLE_JOINERS:
            cur[1] = m.end()
        else:
            merged.append(tuple(cur))
            cur = [m.start(), m.end()]
    merged.append(tuple(cur))
    return merged


def _clean_title(title):
    title = title.strip(" ,;")
    if title.lower() in ("director", "independent director", "non-employee director",
                         "member of the board", "member of the board of directors"):
        title = "Director" if "independent" not in title.lower() else "Independent Director"
    return title


def find_title(sentence, name_end):
    """Pick the title closest to (preferably right after) the person's name."""
    merged = title_spans(sentence)
    if not merged:
        return ""
    after = [s for s in merged if s[0] >= name_end and s[0] - name_end <= 200]
    best = after[0] if after else min(merged, key=lambda s: abs(s[0] - name_end))
    return _clean_title(sentence[best[0]:best[1]])


def role_change_in_sentence(sentence, name_end, other_name_starts):
    """
    Detect one person leaving one role AND taking another in the same sentence, e.g.
    'Sarah Lee, EVP Global People, will step down from that role and was appointed COO'.
    Both keywords must follow this person's name before any other person is named, and
    the two roles must be different. Returns (old_title, new_title) or None.
    """
    limit = min([p for p in other_name_starts if p > name_end] + [name_end + 250])
    cleaned = APPOINT_FALSE_POS.sub(lambda m: " " * len(m.group(0)), sentence)
    dep = next((m for m in DEPART_RE.finditer(sentence) if name_end <= m.start() < limit), None)
    app = next((m for m in APPOINT_RE.finditer(cleaned) if name_end <= m.start() < limit), None)
    if not dep or not app:
        return None
    spans = title_spans(sentence)
    first, second = sorted([dep, app], key=lambda m: m.start())
    # title for the first keyword: between the name and the second keyword
    t_first = [sp for sp in spans if name_end <= sp[0] < second.start()]
    # title for the second keyword: the first title after it
    t_second = [sp for sp in spans if second.start() <= sp[0] <= second.end() + 80]
    if not t_first or not t_second:
        return None
    a = _clean_title(sentence[t_first[0][0]:t_first[0][1]])
    b = _clean_title(sentence[t_second[0][0]:t_second[0][1]])
    if a.lower() == b.lower():
        return None
    return (a, b) if first is dep else (b, a)


def find_effective_date(sentences, report_date):
    for s in sentences:
        m = re.search(r"effective\b(?:\s+as\s+of|\s+on)?\s*(.{0,40})", s, re.I)
        if m:
            d = parse_date(m.group(1))
            if d:
                return d
    for s in sentences:
        if re.search(r"effective immediately|immediately effective", s, re.I):
            return parse_date(s) or report_date      # "On <date> ... effective immediately"
    for s in sentences:
        # ignore "On <date>, X informed/announced..." - that's the announcement date
        for m in DATE_RE.finditer(s):
            if not re.search(r"\b(?:On|on|dated|As of|as of)\s*$", s[:m.start()]):
                d = parse_date(m.group(0))
                if d:
                    return d
    return "Not specified"


def classify_names_in_sentence(sentence, names):
    """Return {name: (event_type, distance_to_keyword)} using keyword proximity."""
    result = {}
    if not names:
        return result

    # "A will succeed B" / "A, as successor to B"  -> A appointment, B departure
    succ = SUCCEED_RE.search(sentence)
    if succ:
        before = [n for n in names if n[2] <= succ.start()]
        after = [n for n in names if n[1] >= succ.end()]
        if before:
            result[before[-1][0]] = ("appointment", 0)
        if after:
            result[after[0][0]] = ("departure", 0)

    cleaned = APPOINT_FALSE_POS.sub(lambda m: " " * len(m.group(0)), sentence)
    keywords = [(m.start(), "departure") for m in DEPART_RE.finditer(sentence)]
    keywords += [(m.start(), "appointment") for m in APPOINT_RE.finditer(cleaned)]
    if succ:
        keywords.append((succ.start(), "appointment"))
    if not keywords:
        return result

    for name, start, end in names:
        if name in result:
            continue
        # distance from the name to the nearest keyword (0 if touching)
        def dist(k):
            return 0 if start <= k[0] <= end else min(abs(k[0] - start), abs(k[0] - end))
        kpos, etype = min(keywords, key=dist)
        result[name] = (etype, dist((kpos, etype)))
    return result


def _core_tokens(name):
    return re.sub(r",?\s+(Jr\.|Sr\.|II|III|IV)$", "", name).split()


def _is_partial_of(short, long):
    """True if `short` is a contiguous piece of `long` (e.g. 'Nora Johnson' in 'Suzanne Nora Johnson')."""
    a, b = _core_tokens(short), _core_tokens(long)
    if len(a) >= len(b):
        return False
    return any(b[i:i + len(a)] == a for i in range(len(b) - len(a) + 1))


def extract_events(section, report_date):
    """Return a list of {event_type, person_name, title, effective_date}."""
    section = re.sub(r"Item\s*5\.02\.?\s*Departure of Directors.*?Certain Officers\.?", " ",
                     section, count=1, flags=re.I)
    is_comp_filing = bool(COMP_RE.search(section))

    # Canonical names: drop partial names when the full name is in the same filing
    all_names = {n for n, _, _ in find_full_names(section)}
    canonical = {}
    for n in all_names:
        longer = [m for m in all_names if _is_partial_of(n, m)]
        canonical[n] = max(longer, key=len) if longer else n

    surname_map = {}
    for n in set(canonical.values()):
        surname = _core_tokens(n)[-1]
        if len(n) > len(surname_map.get(surname, "")):
            surname_map[surname] = n

    # people[name] = list of mentions: (event_type, title, sentence)
    people = {}
    for sentence in split_sentences(section):
        names = [(canonical.get(n, n), a, b) for n, a, b in find_full_names(sentence)]
        # resolve "Mr. Smith" to the full name found elsewhere in the section
        for m in HONORIFIC_RE.finditer(sentence):
            full = surname_map.get(m.group(1))
            if full:
                names.append((full, m.start(), m.end()))
        # keep only one mention per person per sentence (the first)
        uniq, seen = [], set()
        for n in sorted(names, key=lambda x: x[1]):
            if n[0] not in seen:
                seen.add(n[0])
                uniq.append(n)

        for name, (etype, distance) in classify_names_in_sentence(sentence, uniq).items():
            # Pay-only disclosures: ignore names with no departure/appointment keyword nearby
            if is_comp_filing and distance > KEYWORD_NEAR_CHARS:
                continue
            name_end = next(n[2] for n in uniq if n[0] == name)
            others = [n[1] for n in uniq if n[0] != name]
            change = role_change_in_sentence(sentence, name_end, others)
            if change:   # same person: leaves old role, takes a different new one
                people.setdefault(name, []).append(("departure", change[0], sentence))
                people.setdefault(name, []).append(("appointment", change[1], sentence))
            else:
                people.setdefault(name, []).append((etype, find_title(sentence, name_end), sentence))

    events = []
    for name, mentions in people.items():
        dep_titles = [t for e, t, _ in mentions if e == "departure" and t]
        app_titles = [t for e, t, _ in mentions if e == "appointment" and t]
        types = [e for e, _, _ in mentions]

        # "both" only when the person leaves one role AND takes a DIFFERENT one
        if dep_titles and app_titles and dep_titles[0].lower() != app_titles[0].lower():
            etype = "both"
            title = f"{dep_titles[0]} -> {app_titles[0]}"
        else:
            # otherwise use the event type mentioned most (ties go to the first mention)
            etype = max(dict.fromkeys(types), key=types.count)
            same = [t for e, t, _ in mentions if e == etype and t]
            any_title = [t for _, t, _ in mentions if t]
            title = (same or any_title or ["Not specified"])[0]

        events.append({
            "event_type": etype,
            "person_name": name,
            "title": title,
            "effective_date": find_effective_date([m[2] for m in mentions], report_date),
        })
    return events


# --------------------------------------------------------------------------
# Main run: steps 2-7 for all five companies
# --------------------------------------------------------------------------
def main():
    print(f"SEC EDGAR Item 5.02 scan | window: {CUTOFF} to {TODAY}")
    print(f"User-Agent: {USER_AGENT}\n")

    all_rows = []
    for co in COMPANIES:
        ticker, cik = co["ticker"], co["cik"]
        print(f"=== {co['company']} ({ticker}) ===")
        try:
            filings = get_502_filings(cik)
        except Exception as exc:
            print(f"{ticker}: ERROR reading submissions API - {exc}\n")
            continue

        if not filings:
            print(f"{ticker}: No executive events in past 12 months\n")
            continue

        company_events = 0
        for f in filings:
            try:
                text = download_8k_text(cik, f)
            except Exception as exc:
                print(f"{ticker} | {f['filingDate']} | ERROR downloading {f['accessionNumber']} - {exc}")
                continue

            section = isolate_item_502(text)
            report_date = f.get("reportDate") or f["filingDate"]
            events = extract_events(section, report_date)

            if not events:
                print(f"{ticker} | {f['filingDate']} | (Item 5.02 filing with no departure/appointment "
                      f"found - likely a compensation-only disclosure) | {f['accessionNumber']}")
                continue

            for ev in events:
                row = {
                    "company": co["company"],
                    "ticker": ticker,
                    "cik": cik,
                    "filing_date": f["filingDate"],
                    **ev,
                }
                all_rows.append(row)
                company_events += 1
                print(f"{ticker} | {f['filingDate']} | {ev['event_type']} | "
                      f"{ev['person_name']} | {ev['title']}")

        if company_events == 0:
            print(f"{ticker}: No executive events in past 12 months")
        print()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Saved {len(all_rows)} event row(s) to {os.path.abspath(OUTPUT_PATH)}")


if __name__ == "__main__":
    main()