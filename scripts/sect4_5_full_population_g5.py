"""Section 4.5: G5(paper)/G6(code) applied to the full population, without surge
gating -- "G5 matches N accounts (X%)" applied across every (user, week) pair in
the full account-week universe, not just the surge-flagged population G5 normally
draws from. Uses the current, causal Q_OWNER (see docs/REPRODUCE.md).

Needs only notebook 01's checkpoint (data/interim/01_df_master.csv) and a live
Neo4j instance -- independent of notebooks 02-08, so it can be run any time after
notebook 01 completes.

Usage:
    export NEO4J_PASSWORD=yourpassword
    python scripts/sect4_5_full_population_g5.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import pandas as pd

from awik.config import ANSWER_SET
from awik import graph_inspection as gi
from awik.neo4j_client import Neo4jConnection

t0 = time.time()
master_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'interim', '01_df_master.csv')
df_master = pd.read_csv(master_path)
n_users = df_master['User_ID'].nunique()

all_pairs = (
    df_master[['User_ID', 'Year', 'Week']].drop_duplicates()
    .apply(lambda r: {'uid': r['User_ID'], 'year': int(r['Year']), 'week': int(r['Week'])}, axis=1)
    .tolist()
)
year_weeks = sorted({(p['year'], p['week']) for p in all_pairs})
print(f"Full population, no surge gating: {len(all_pairs):,} (user, week) pairs, "
      f"{len(year_weeks)} distinct ISO weeks, {n_users} users")

conn = Neo4jConnection("bolt://localhost:7687", "neo4j", os.environ["NEO4J_PASSWORD"])
owner_of_by_week = gi.fetch_owner_of_by_week(conn, year_weeks)
print(f"Causal ownership computed, {time.time() - t0:.0f}s elapsed")

df_g6_full = gi.run_g6(conn, all_pairs, owner_of_by_week, batch_size=200)
conn.close()

matched = set(df_g6_full['Suspect'].unique()) if not df_g6_full.empty else set()
n = len(matched)
pct = n / n_users * 100

print("\n=== RESULT ===")
print(f"G5(paper)/G6(code), full population, no surge gating, causal ownership:")
print(f"  matched accounts: {n} / {n_users} ({pct:.2f}%)")
print(f"  Answer Set accounts matched: {sorted(matched & set(ANSWER_SET))}")
print(f"Total time: {time.time() - t0:.0f}s")

out_path = os.path.join(os.path.dirname(__file__), '..', 'results', 'tables',
                         'AWIK_G5_FullPopulation_NoGating.csv')
pd.DataFrame({'Suspect': sorted(matched)}).to_csv(out_path, index=False)
print(f"Saved -> {out_path}")
