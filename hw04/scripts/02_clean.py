"""
HW4 Part C - Cleaning program for the Wildcat Capital tables.

Run from inside the hw04 folder:
    python scripts/02_clean.py

Reads the 8 raw files in data/raw (never modified) and writes:
    data/clean/<same 8 file names>          clean tables, same columns (+ a few 0/1 flag columns)
    data/audit/cleaning_log.csv             table, issue, action, rows affected, note
    data/audit/value_changes.csv            every single value that was changed (old -> new)
    data/audit/quarantine_*.csv             every row that was removed, with the reason

CLEANING ORDER (and why) - follows decision_log.md
    Step 1  1f security_id "45.0" -> "45"     Format fixes first, so every later check compares
    Step 2  1d return_ytd "9.28%" -> 0.0928   real values instead of text that only looks different.
    Step 3  1e state names -> 2-letter codes  Standardize before anything groups or matches on state.
    Step 4  1a quarantine duplicate clients   Before the fill in step 5, so we don't fill a row we drop,
                                              and before step 6, so orphans are judged against the
                                              final client list.
    Step 5  1g fill blank risk_profile        Needs the de-duplicated client list + snapshots to verify.
    Step 6  1b quarantine orphan transactions Needs the final client list from step 4.
    Step 7  1c negative shares -> positive    After orphans are removed, so counts cover kept rows only.
    Step 8  2a, 2b flag columns               Last, so flags describe the final rows.
    Step 9  reconcile + save                  Prove raw rows = clean rows + quarantined rows.

Every step prints rows affected and a before/after check, and uses assert so the script STOPS
if a fix did not do what decision_log.md says it should.
"""

from pathlib import Path

import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = HW_DIR / "data" / "raw"
CLEAN_DIR = HW_DIR / "data" / "clean"
AUDIT_DIR = HW_DIR / "data" / "audit"
TABLE_FILES = [
    "dim_advisor.csv", "dim_client.csv", "dim_date.csv", "dim_security.csv", "dim_benchmark.csv",
    "fact_fees.csv", "fact_portfolio_snapshot.csv", "fact_transactions.csv",
]
PRIMARY_KEYS = {
    "dim_advisor": "advisor_id", "dim_client": "client_id", "dim_date": "date_id",
    "dim_security": "security_id", "dim_benchmark": "benchmark_id",
    "fact_fees": "fee_id", "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id",
}

# Counts found by the Part A audit (reports/dq_summary_raw.csv) and cited in decision_log.md.
# Each step asserts it changed exactly this many rows (or the documented smaller number).
AUDIT = {"security_id_decimal": 197175, "return_pct": 300, "state_names": 78, "dup_clients": 25,
         "risk_blank": 76, "orphan_txns": 200, "neg_shares": 836, "aum_floor": 420, "return_outliers": 2157}

cleaning_log = []     # one row per step
value_changes = []    # one row per changed value
quarantined = {}      # table -> number of rows quarantined
QUARANTINED_KEYS = {} # table -> set of primary keys quarantined


def num(s):
    return pd.to_numeric(s, errors="coerce")


def log_step(table, issue, action, rows, note=""):
    cleaning_log.append({"table": table, "issue": issue, "action": action,
                         "rows_affected": int(rows), "note": note})


def record_changes(table, df, mask, col, old, new):
    """Save old -> new for every changed value, keyed by the table's primary key."""
    key = PRIMARY_KEYS[table]
    value_changes.append(pd.DataFrame({
        "table": table, "key_column": key, "key": df.loc[mask, key].values,
        "column": col, "old_value": old[mask].values, "new_value": new[mask].values,
    }))


def quarantine(table, rows, name, reason, extra=None):
    """Write the ORIGINAL raw version of removed rows to their own file with the reason."""
    key = PRIMARY_KEYS[table]
    out = RAW[table][RAW[table][key].isin(set(rows[key]))].copy()
    if extra is not None:
        out = out.merge(extra, on=key, how="left")
    out.insert(0, "quarantine_reason", reason)
    out.to_csv(AUDIT_DIR / f"quarantine_{name}.csv", index=False)
    quarantined[table] = quarantined.get(table, 0) + len(out)
    QUARANTINED_KEYS.setdefault(table, set()).update(out[key])


def header(text):
    print("\n" + "=" * 90 + f"\n{text}\n" + "=" * 90)


# ------------------------------------------------------------------------------------------------
# Load (as text, so nothing is silently converted)
# ------------------------------------------------------------------------------------------------
CLEAN_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

T = {f[:-4]: pd.read_csv(RAW_DIR / f, dtype=str, keep_default_na=False) for f in TABLE_FILES}
RAW = {t: df.copy() for t, df in T.items()}     # untouched copy, used for quarantine files and the final reconcile
RAW_ROWS = {t: len(df) for t, df in T.items()}
header("Loaded raw tables")
for t, n in RAW_ROWS.items():
    print(f"  {t:28} {n:>9,} rows")

client = T["dim_client"]
snap = T["fact_portfolio_snapshot"]
tx = T["fact_transactions"]
sec = T["dim_security"]


# ------------------------------------------------------------------------------------------------
# Step 1 - 1f: security_id "45.0" -> "45"
# ------------------------------------------------------------------------------------------------
header("Step 1 (1f) fact_transactions.security_id: decimal text -> integer text")
sid = tx.security_id
has_dot = sid.str.contains(r"\.", regex=True)
print(f"  before: {has_dot.sum():,} values contain a '.'   e.g. {sid[has_dot].iloc[0]!r}")
# verify before changing: every value must be a whole number, and must exist in dim_security
assert has_dot.sum() == AUDIT["security_id_decimal"], "count differs from the Part A audit"
assert sid[has_dot].str.fullmatch(r"\d+\.0+").all(), "some security_id values are not whole numbers"
new_sid = sid.where(~has_dot, sid.str.replace(r"\.0+$", "", regex=True))
record_changes("fact_transactions", tx, has_dot, "security_id", sid, new_sid)
tx["security_id"] = new_sid
nonblank = tx.security_id != ""
orphans = ~tx.loc[nonblank, "security_id"].isin(set(sec.security_id))
print(f"  after:  {tx.security_id.str.contains(r'[.]', regex=True).sum()} values contain a '.'; "
      f"{orphans.sum()} non-blank ids missing from dim_security")
assert not tx.security_id.str.contains(r"\.", regex=True).any()
assert orphans.sum() == 0, "a converted security_id does not exist in dim_security"
log_step("fact_transactions", "1f security_id stored as decimal text", "convert", has_dot.sum(),
         "'45.0' -> '45'; all now match dim_security as text")


# ------------------------------------------------------------------------------------------------
# Step 2 - 1d: return_ytd "9.28%" -> 0.0928, verified against the alpha identity
# ------------------------------------------------------------------------------------------------
header("Step 2 (1d) fact_portfolio_snapshot.return_ytd: percent text -> decimal")
r = snap.return_ytd
pct = r.str.strip().str.endswith("%")
print(f"  before: {pct.sum()} values end in '%'   e.g. {r[pct].iloc[0]!r}")
assert pct.sum() == AUDIT["return_pct"], "count differs from the Part A audit"
converted = num(r[pct].str.strip().str.rstrip("%")) / 100
assert converted.notna().all(), "a percent value could not be converted"
# reconcile: return - benchmark should equal alpha (to the precision of a 2-decimal percent)
gap = (converted - num(snap.loc[pct, "benchmark_return_ytd"]) - num(snap.loc[pct, "active_alpha_ytd"])).abs()
print(f"  check:  return - benchmark - alpha, largest gap = {gap.max():.6f} (limit 0.00006)")
assert (gap <= 0.00006).all(), "converted return does not reconcile with alpha"
new_r = r.copy()
new_r[pct] = converted.map(lambda v: f"{v:.4f}")   # a 2-decimal percent has 4 decimals of real precision
record_changes("fact_portfolio_snapshot", snap, pct, "return_ytd", r, new_r)
snap["return_ytd"] = new_r
still_bad = num(snap.return_ytd).isna().sum()
print(f"  after:  {snap.return_ytd.str.endswith('%').sum()} values end in '%'; {still_bad} values fail to parse")
assert still_bad == 0
log_step("fact_portfolio_snapshot", "1d return_ytd stored as percent text", "convert", pct.sum(),
         f"divided by 100; all {pct.sum()} reconcile to return - benchmark = alpha (max gap {gap.max():.6f})")


# ------------------------------------------------------------------------------------------------
# Step 3 - 1e: state names -> USPS codes
# ------------------------------------------------------------------------------------------------
header("Step 3 (1e) dim_client.state: full names -> 2-letter codes")
STATE_MAP = {"Pennsylvania": "PA", "Florida": "FL", "New York": "NY", "New Jersey": "NJ",
             "California": "CA", "Illinois": "IL", "Texas": "TX"}
US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
                "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
st = client.state
long_name = ~st.isin(US_STATES)
print(f"  before: {long_name.sum()} non-code values: {st[long_name].value_counts().to_dict()}")
assert long_name.sum() == AUDIT["state_names"], "count differs from the Part A audit"
assert st[long_name].isin(STATE_MAP).all(), "a state name is missing from STATE_MAP"
new_st = st.replace(STATE_MAP)
record_changes("dim_client", client, long_name, "state", st, new_st)
client["state"] = new_st
print(f"  after:  {(~client.state.isin(US_STATES)).sum()} non-code values; {client.state.nunique()} distinct states")
assert client.state.isin(US_STATES).all()
log_step("dim_client", "1e state written as full name", "standardize", long_name.sum(),
         "7-entry name -> USPS code map")


# ------------------------------------------------------------------------------------------------
# Step 4 - 1a: quarantine duplicate clients
# ------------------------------------------------------------------------------------------------
header("Step 4 (1a) dim_client: quarantine near-duplicate clients")
MATCH = ["first_name", "age", "city", "zip_code", "client_since", "advisor_id", "initial_aum"]
c = client.assign(_id=num(client.client_id))
pairs = c.merge(c, on=MATCH, suffixes=("", "_orig"))
pairs = pairs[pairs._id > pairs._id_orig]              # keep the lower ID as the original
dup_ids = set(pairs.client_id)
print(f"  found:  {len(dup_ids)} duplicates matching an earlier client on {MATCH}")
print("  e.g.    " + "; ".join(f"{a} '{b}' = {o} '{p}'" for a, b, o, p in
                              pairs[["client_id", "last_name", "client_id_orig", "last_name_orig"]].head(3).values))
# verify: last names really are near-identical (one letter added or dropped)
one_letter = pairs.apply(lambda x: abs(len(x.last_name) - len(x.last_name_orig)) == 1 and
                         (x.last_name.startswith(x.last_name_orig) or x.last_name_orig.startswith(x.last_name)), axis=1)
print(f"  check:  {one_letter.sum()} of {len(pairs)} differ only by one letter at the end of the last name")
assert one_letter.all()
OTHER = [col for col in client.columns if col not in MATCH + ["client_id", "last_name"]]
same_other = pairs.apply(lambda x: all(x[col] == x[col + "_orig"] for col in OTHER), axis=1)
print(f"  check:  {same_other.sum()} of {len(pairs)} also match on every other field {OTHER}")
assert same_other.all(), "a duplicate differs from its original on another field"
assert len(dup_ids) == AUDIT["dup_clients"] and pairs.client_id.is_unique, "count differs from the Part A audit"
# verify: no fact row uses a duplicate ID, so quarantining loses no activity
used = set(T["fact_fees"].client_id) | set(snap.client_id) | set(tx.client_id)
print(f"  check:  {len(dup_ids & used)} duplicate IDs appear in any fact table")
assert not (dup_ids & used)
dup_rows = client[client.client_id.isin(dup_ids)].merge(
    pairs[["client_id", "client_id_orig"]].rename(columns={"client_id_orig": "duplicate_of_client_id"}), on="client_id")
quarantine("dim_client", dup_rows, "dim_client_duplicates", "1a near-duplicate of an existing client",
           extra=dup_rows[["client_id", "duplicate_of_client_id"]])
before = len(client)
client = client[~client.client_id.isin(dup_ids)].copy()
print(f"  after:  dim_client {before:,} -> {len(client):,} rows; client_id unique = {client.client_id.is_unique}")
assert len(client) == before - len(dup_ids) and client.client_id.is_unique
log_step("dim_client", "1a near-duplicate clients", "quarantine", len(dup_ids),
         "match on every field except a one-letter last-name difference, no fact rows; see quarantine_dim_client_duplicates.csv")


# ------------------------------------------------------------------------------------------------
# Step 5 - 1g: fill blank risk_profile from the benchmark mapping
# ------------------------------------------------------------------------------------------------
header("Step 5 (1g) dim_client.risk_profile: fill blanks, verified against snapshot benchmark")
blank = client.risk_profile.str.strip() == ""
blank_in_dups = (RAW["dim_client"].client_id.isin(dup_ids) & (RAW["dim_client"].risk_profile.str.strip() == "")).sum()
print(f"  before: {blank.sum()} blank risk_profile values ({AUDIT['risk_blank']} in the audit, "
      f"{blank_in_dups} of them on a duplicate quarantined in step 4)")
assert blank.sum() + blank_in_dups == AUDIT["risk_blank"], "count does not reconcile with the Part A audit"
bench = snap.groupby("client_id").benchmark_id.agg(lambda s: "/".join(sorted(set(s))))
assert snap.groupby("client_id").benchmark_id.nunique().max() == 1, "a client has more than one benchmark"
known = client[~blank].assign(bm=lambda d: d.client_id.map(bench))
profiles_per_bm = known.groupby("bm").risk_profile.agg(lambda s: sorted(set(s)))
print(f"  map:    benchmark -> risk profiles among known clients: {profiles_per_bm.to_dict()}")
blank_bm = client.loc[blank, "client_id"].map(bench)
print(f"  check:  blank-profile clients by benchmark: {blank_bm.value_counts(dropna=False).to_dict()}")
assert blank_bm.notna().all(), "a blank-profile client has no snapshot to verify against"
assert blank_bm.isin(profiles_per_bm.index).all(), "a blank-profile client's benchmark has no known profile"
fill = blank_bm.map(lambda b: profiles_per_bm[b][0] if len(profiles_per_bm[b]) == 1 else None)
assert fill.notna().all(), "benchmark does not identify exactly one risk profile"
print(f"  fill:   {fill.value_counts().to_dict()}  (taken from the mapping above)")
client["risk_profile_imputed"] = blank.astype(int).astype(str)
old = client.risk_profile.copy()
client.loc[blank, "risk_profile"] = fill
record_changes("dim_client", client, blank, "risk_profile", old, client.risk_profile)
print(f"  after:  {(client.risk_profile.str.strip() == '').sum()} blanks; risk_profile_imputed = 1 on "
      f"{(client.risk_profile_imputed == '1').sum()} rows")
assert (client.risk_profile.str.strip() != "").all()
log_step("dim_client", "1g blank risk_profile", "fill", blank.sum(),
         f"filled from benchmark mapping {fill.value_counts().to_dict()}; {blank_in_dups} more blank was on a quarantined duplicate; flag risk_profile_imputed")


# ------------------------------------------------------------------------------------------------
# Step 6 - 1b: quarantine transactions whose client does not exist
# ------------------------------------------------------------------------------------------------
header("Step 6 (1b) fact_transactions: quarantine rows with no matching client")
orphan = ~tx.client_id.isin(set(client.client_id))
ids = num(tx.loc[orphan, "client_id"])
print(f"  found:  {orphan.sum()} rows, {tx.loc[orphan, 'client_id'].nunique()} distinct client_ids "
      f"(range {ids.min():.0f}-{ids.max():.0f}), total amount ${num(tx.loc[orphan, 'amount']).sum():,.2f}")
print(f"          by type: {tx.loc[orphan, 'txn_type'].value_counts().to_dict()}")
assert orphan.sum() == AUDIT["orphan_txns"], "count differs from the Part A audit"
quarantine("fact_transactions", tx[orphan], "fact_transactions_orphans", "1b client_id not in dim_client")
before = len(tx)
tx = tx[~orphan].copy()
print(f"  after:  fact_transactions {before:,} -> {len(tx):,} rows; orphans left = "
      f"{(~tx.client_id.isin(set(client.client_id))).sum()}")
assert tx.client_id.isin(set(client.client_id)).all()
log_step("fact_transactions", "1b client_id not in dim_client", "quarantine", orphan.sum(),
         "see quarantine_fact_transactions_orphans.csv")


# ------------------------------------------------------------------------------------------------
# Step 7 - 1c: negative shares on Buy rows -> positive, verified with amount = shares x price
# ------------------------------------------------------------------------------------------------
header("Step 7 (1c) fact_transactions.shares: negative Buy shares -> positive")
sh, pr, am = num(tx.shares), num(tx.price), num(tx.amount)
neg = sh < 0
raw_tx = RAW["fact_transactions"]
neg_in_orphans = (raw_tx.txn_id.isin(QUARANTINED_KEYS["fact_transactions"]) & (num(raw_tx.shares) < 0)).sum()
print(f"  before: {neg.sum()} negative shares ({AUDIT['neg_shares']} in the audit, {neg_in_orphans} of them "
      f"on an orphan row quarantined in step 6); types: {tx.loc[neg, 'txn_type'].value_counts().to_dict()}")
assert neg.sum() + neg_in_orphans == AUDIT["neg_shares"], "count does not reconcile with the Part A audit"
gap = (am[neg] - sh[neg].abs() * pr[neg]).abs()
print(f"  check:  amount vs |shares| x price, largest gap = ${gap.max():.4f} (limit $0.05)")
assert (tx.loc[neg, "txn_type"] == "Buy").all()
assert (gap <= 0.05).all(), "amount does not reconcile to |shares| x price"
old = tx.shares.copy()
tx.loc[neg, "shares"] = tx.loc[neg, "shares"].str.lstrip("-")   # exact text change, no rounding
record_changes("fact_transactions", tx, neg, "shares", old, tx.shares)
sh = num(tx.shares)
trade = tx.txn_type.isin(["Buy", "Sell"])
trade_gap = (num(tx.amount) - sh * num(tx.price)).abs()[trade]
print(f"  after:  {(sh < 0).sum()} negative shares; Buy/Sell rows where amount != shares x price: "
      f"{(trade_gap > 0.05).sum()}")
assert (sh < 0).sum() == 0 and (trade_gap <= 0.05).all()
log_step("fact_transactions", "1c negative shares on Buy", "convert", neg.sum(),
         f"absolute value; all reconcile to amount = shares x price; {neg_in_orphans} more was on a quarantined orphan")


# ------------------------------------------------------------------------------------------------
# Step 8 - 2a, 2b: flag columns (values are NOT changed)
# ------------------------------------------------------------------------------------------------
header("Step 8 (2a, 2b) fact_portfolio_snapshot: add flag columns")
values_before = snap[["aum", "return_ytd"]].copy()
aum = num(snap.aum)
snap["aum_floor_flag"] = (aum == 1000).astype(int).astype(str)
n_floor = (snap.aum_floor_flag == "1").sum()
print(f"  2a aum_floor_flag = 1 on {n_floor} rows ({snap.loc[snap.aum_floor_flag == '1', 'client_id'].nunique()} clients)")
assert n_floor == AUDIT["aum_floor"], "count differs from the Part A audit"
assert aum.min() == 1000, "1000 is no longer the column minimum"
log_step("fact_portfolio_snapshot", "2a aum exactly 1000 (floor/placeholder)", "flag", n_floor, "aum_floor_flag; value unchanged")

ret = num(snap.return_ytd)
snap["return_outlier_flag"] = ((ret < -0.6) | (ret > 1.0)).astype(int).astype(str)
n_out = (snap.return_outlier_flag == "1").sum()
print(f"  2b return_outlier_flag = 1 on {n_out} rows (outside -60% / +100% YTD)")
alpha_gap = (ret - num(snap.benchmark_return_ytd) - num(snap.active_alpha_ytd)).abs()
flag_gap = alpha_gap[snap.return_outlier_flag == "1"].max()
print(f"     check: alpha identity on flagged rows, largest gap = {flag_gap:.6f} (limit 0.0001)")
assert n_out == AUDIT["return_outliers"], "count differs from the Part A audit"
assert flag_gap <= 0.0001, "flagged returns do not reconcile with benchmark and alpha"
assert snap[["aum", "return_ytd"]].equals(values_before), "flagging changed a value"
print("     check: aum and return_ytd values unchanged by flagging")
log_step("fact_portfolio_snapshot", "2b extreme return_ytd", "flag", n_out, "return_outlier_flag; value unchanged")

# tables with no changes still get a log line, so the log covers all 8
for t in ["dim_advisor", "dim_date", "dim_security", "dim_benchmark", "fact_fees"]:
    log_step(t, "no defects requiring change", "leave as is", 0, "see decision_log.md section 3/4")


# ------------------------------------------------------------------------------------------------
# Step 9 - reconcile row counts and save everything
# ------------------------------------------------------------------------------------------------
header("Step 9 Reconcile: raw rows = clean rows + quarantined rows")
T["dim_client"], T["fact_portfolio_snapshot"], T["fact_transactions"] = client, snap, tx
for t, df in T.items():
    q = quarantined.get(t, 0)
    ok = RAW_ROWS[t] == len(df) + q
    print(f"  {t:28} raw {RAW_ROWS[t]:>9,} = clean {len(df):>9,} + quarantined {q:>4}   {'OK' if ok else 'MISMATCH'}")
    assert ok, f"row count does not reconcile for {t}"

# key-level check: clean keys and quarantined keys don't overlap, and together are exactly the raw keys
for t in QUARANTINED_KEYS:
    key = PRIMARY_KEYS[t]
    clean_keys, q_keys, raw_keys = set(T[t][key]), QUARANTINED_KEYS[t], set(RAW[t][key])
    assert not (clean_keys & q_keys), f"{t}: a row is both kept and quarantined"
    assert clean_keys | q_keys == raw_keys and T[t][key].is_unique, f"{t}: keys do not reconcile"
    print(f"  {t:28} keys: clean and quarantined are disjoint and together equal the raw keys   OK")

# referential integrity on the clean tables: every fact key must exist in its dimension
FKS = [("fact_fees", "client_id", "dim_client"), ("fact_portfolio_snapshot", "client_id", "dim_client"),
       ("fact_transactions", "client_id", "dim_client"), ("fact_transactions", "security_id", "dim_security"),
       ("dim_client", "advisor_id", "dim_advisor")]
for child, col, parent in FKS:
    vals = T[child][col][T[child][col] != ""]
    missing = (~vals.isin(set(T[parent][PRIMARY_KEYS[parent]]))).sum()
    print(f"  RI {child}.{col} -> {parent}: {missing} orphans")
    assert missing == 0

for t, df in T.items():
    df.to_csv(CLEAN_DIR / f"{t}.csv", index=False)
pd.DataFrame(cleaning_log).to_csv(AUDIT_DIR / "cleaning_log.csv", index=False)
changes = pd.concat(value_changes, ignore_index=True)
# only keep changes to rows that reach the clean tables (quarantined rows are saved in their raw form)
dropped = changes.apply(lambda x: x["key"] in QUARANTINED_KEYS.get(x["table"], set()), axis=1)
changes = changes[~dropped]
changes.to_csv(AUDIT_DIR / "value_changes.csv", index=False)

header("Done")
print(f"  {len(T)} clean tables -> {CLEAN_DIR}")
print(f"  cleaning_log.csv: {len(cleaning_log)} rows   value_changes.csv: {len(changes):,} rows   "
      f"quarantine files: {len(list(AUDIT_DIR.glob('quarantine_*.csv')))}")
print("  value changes by column:", changes.groupby(['table', 'column']).size().to_dict())
