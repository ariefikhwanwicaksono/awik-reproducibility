"""Layer 2: surgical contextual graph inspection (G1, G2, G3, G5, G6).

G4 (analyst-maintained exfiltration watchlist) is permanently disabled -- it depended
on the VISITED_URL relation, removed from the pipeline (see features.py docstring).

Q_G1, Q_G2, Q_G3A, Q_G3B and the G4/code-G5 query built by build_q_g5() previously
carried a per-batch `LIMIT` (200/200/100/100/300). That limit bound in nearly every
batch at the population sizes this pipeline actually examines (e.g. G2 in the
routing-disabled condition returned the LIMIT-200 cap in 22/22 batches), so the
"matched" counts it produced were a truncated lower bound, not the true match count,
and the union (`graph_confirmed`) additionally became dependent on `PYTHONHASHSEED`
through batch composition. Both LIMIT clauses and that hash dependency are removed
here; callers must now pass explicitly sorted candidate lists (never a bare
`list(some_set)`) so results are reproducible independent of Python's set-iteration
order. See docs/REPRODUCE.md for the measurements this fix is based on.

Q_OWNER (backing the code-G6/paper-G5 query) determines PC ownership causally: for
each (user, ISO week) pair under test, majority ownership (>=50% of historical
logons) is computed only from logons strictly before that week's start -- never from
logons on or after it. This was previously computed once, globally, over the entire
dataset (a non-causal design, structurally similar to the adaptive-baseline leak
fixed elsewhere in this pipeline for R2-3); see docs/REPRODUCE.md for the sensitivity
test this change is based on and the numbers it changed.
"""

import pandas as pd

from .neo4j_client import run_batched_query

Q_G1 = """
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r1:LOGGED_ON_TO]->(pc:PC)
      <-[r2:LOGGED_ON_TO]-(owner:User)
WHERE owner.user_id <> uid
  AND (r1.timestamp.hour >= 18 OR r1.timestamp.hour <= 6)
WITH suspect, r1, pc, head(collect(owner)) AS primary_owner
RETURN suspect.user_id AS Suspect, pc.pc_id AS Target,
       primary_owner.user_id AS Evidence,
       'G1_AfterHours_Lateral' AS Pattern, r1.timestamp AS Timestamp
ORDER BY r1.timestamp
"""

Q_G2 = """
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r1:LOGGED_ON_TO]->(pc:PC)
      <-[r2:LOGGED_ON_TO]-(owner:User)
WHERE owner.user_id <> uid
WITH suspect, r1, pc, head(collect(owner)) AS owner_node
MATCH (suspect)-[r3:SENT_EMAIL]->(email_node)
WHERE r3.timestamp > r1.timestamp
  AND r3.timestamp < r1.timestamp + duration({hours: 24})
  AND r3.size > 50000 AND r3.activity = 'Send'
RETURN suspect.user_id AS Suspect, pc.pc_id AS Target,
       owner_node.user_id AS Evidence,
       'G2_Lateral_MassEmail' AS Pattern, r1.timestamp AS Timestamp
ORDER BY r1.timestamp
"""

Q_G3A = """
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r1:LOGGED_ON_TO]->(pc:PC)
      <-[r2:LOGGED_ON_TO]-(owner:User)
WHERE owner.user_id <> uid AND r1.timestamp.hour >= 7 AND r1.timestamp.hour <= 17
RETURN DISTINCT suspect.user_id AS Suspect, pc.pc_id AS Target_PC
"""

Q_G3B = """
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r:SENT_EMAIL]->(email_node)
WHERE r.size > 100000 AND r.activity = 'Send'
RETURN DISTINCT suspect.user_id AS Suspect, r.size AS Email_Size
"""

Q_OWNER = """
MATCH (u:User)-[r:LOGGED_ON_TO]->(pc:PC)
WHERE r.timestamp < localdatetime({date: date({year: $year, week: $week, dayOfWeek: 1})})
WITH pc, u, count(r) AS n
WITH pc, sum(n) AS total, collect({u:u.user_id, n:n}) AS L
UNWIND L AS x WITH pc, total, x ORDER BY x.n DESC
WITH pc, total, collect(x)[0] AS top
WHERE toFloat(top.n)/total >= 0.5
RETURN pc.pc_id AS PC, top.u AS owner
"""

Q_G6 = """
UNWIND $batch AS p
MATCH (u:User {user_id:p.uid})-[r:LOGGED_ON_TO]->(pc:PC)
WHERE r.timestamp.year=p.year AND r.timestamp.week=p.week
  AND (r.timestamp.hour>=18 OR r.timestamp.hour<=6)
RETURN DISTINCT p.uid AS Suspect, pc.pc_id AS PC,
       p.year AS Year, p.week AS Week, r.timestamp AS Timestamp
"""


def fetch_email_p99(conn):
    """Label-free size threshold for mass-email near-miss (G5)."""
    try:
        p99 = conn.query_to_dataframe(
            "MATCH ()-[r:SENT_EMAIL]->() WHERE r.activity='Send' "
            "RETURN percentileCont(r.size, 0.99) AS p99")
        return float(p99['p99'].iloc[0]) if not p99.empty else 0.0
    except Exception as e:
        print(f"  [WARNING] percentileCont failed ({str(e)[:40]}); gate is user-surge only.")
        return 0.0


def build_q_g5(email_p99):
    return ("""
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r:SENT_EMAIL]->(email_node)
WHERE r.activity = 'Send' AND r.size >= %d
RETURN suspect.user_id AS Suspect, r.size AS Email_Size,
       r.timestamp.year AS Year, r.timestamp.week AS Week,
       'G5_MassEmail_NearMiss' AS Pattern, r.timestamp AS Timestamp
ORDER BY r.size DESC
""" % int(email_p99))


def fetch_owner_of_by_week(conn, year_weeks):
    """Causal PC ownership, one query per distinct ISO (year, week) in year_weeks:
    each query's majority-owner determination uses only logons strictly before that
    week's start. Returns {(year, week): {pc_id: owner_user_id}}."""
    return {
        (year, week): dict(conn.query_to_dataframe(Q_OWNER, {"year": year, "week": week}).values)
        for year, week in sorted(set(year_weeks))
    }


def run_g1_g5(conn, candidates_graph, email_near_miss, q_g5, batch_size=50):
    """candidates_graph and email_near_miss must be sorted (not a bare `list(some_set)`):
    Q_G1/Q_G2/Q_G3A/Q_G3B no longer carry a per-batch LIMIT, so batch composition can no
    longer truncate results -- but callers should still pass a deterministic order so
    which batch a warning/error refers to is reproducible run to run."""
    df_g1 = run_batched_query(conn, Q_G1, candidates_graph, batch_size, "G1")
    df_g2 = run_batched_query(conn, Q_G2, candidates_graph, batch_size, "G2")
    df_g3a = run_batched_query(conn, Q_G3A, candidates_graph, 25, "G3a")
    df_g3b = run_batched_query(conn, Q_G3B, candidates_graph, 25, "G3b")
    df_g5 = run_batched_query(conn, q_g5, email_near_miss, 25, "G5") if email_near_miss else pd.DataFrame()
    return df_g1, df_g2, df_g3a, df_g3b, df_g5


def run_g6(conn, surge_pairs, owner_of_by_week, batch_size=200):
    """G6 draws from the full surge population (users_surged), not candidates_graph --
    it self-confirms the (user, week) pairs already flagged by the adaptive baseline.
    owner_of_by_week: {(year, week): {pc_id: owner_user_id}} from fetch_owner_of_by_week,
    so ownership for each row is looked up using only that row's own (Year, Week) --
    i.e. logons strictly before that week's start, never the week itself or later."""
    parts = []
    for i in range(0, len(surge_pairs), batch_size):
        b = conn.query_to_dataframe(Q_G6, {"batch": surge_pairs[i:i + batch_size]})
        if not b.empty:
            parts.append(b)
    df_raw = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if df_raw.empty:
        return pd.DataFrame()
    df_raw['owner'] = df_raw.apply(
        lambda row: owner_of_by_week.get((int(row['Year']), int(row['Week'])), {}).get(row['PC']),
        axis=1)
    df = df_raw[(df_raw['owner'].notna()) & (df_raw['owner'] != df_raw['Suspect'])].copy()
    if df.empty:
        return pd.DataFrame()
    df['Target'] = df['PC']
    df['Evidence'] = df['owner']
    df['Pattern'] = 'G6_Attacker_Lateral_AfterHours'
    return df[['Suspect', 'Target', 'Evidence', 'Pattern', 'Timestamp']]


def summarize(df_g1, df_g2, df_g3a, df_g3b, df_g5, df_g6):
    """Union of per-pattern suspects, plus a combined forensic evidence table."""
    g1 = set(df_g1['Suspect'].unique()) if not df_g1.empty else set()
    g2 = set(df_g2['Suspect'].unique()) if not df_g2.empty else set()
    lat_day = set(df_g3a['Suspect'].unique()) if not df_g3a.empty else set()
    lrg_mail = set(df_g3b['Suspect'].unique()) if not df_g3b.empty else set()
    g3 = lat_day & lrg_mail
    g5 = set(df_g5['Suspect'].unique()) if not df_g5.empty else set()
    g6 = set(df_g6['Suspect'].unique()) if not df_g6.empty else set()

    df_g3_vis = df_g3a[df_g3a['Suspect'].isin(g3)].assign(
        Target=df_g3a['Target_PC'] if 'Target_PC' in df_g3a.columns else '-',
        Evidence='lateral_largemail', Pattern='G3_Lateral_LargeEmail',
    ) if not df_g3a.empty else pd.DataFrame()

    df_forensic = pd.concat(
        [d for d in [df_g1, df_g2, df_g3_vis, df_g5, df_g6] if not d.empty],
        ignore_index=True) if any(not d.empty for d in [df_g1, df_g2, df_g3_vis, df_g5, df_g6]) \
        else pd.DataFrame()

    graph_confirmed = g1 | g2 | g3 | g5 | g6
    return {
        'g1': g1, 'g2': g2, 'g3': g3, 'g5': g5, 'g6': g6,
        'graph_confirmed': graph_confirmed, 'df_forensic': df_forensic, 'df_g3_vis': df_g3_vis,
    }
