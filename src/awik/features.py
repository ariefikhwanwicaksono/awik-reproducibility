"""Deep Feature Synthesis (DFS) over Neo4j -> weekly per-user feature matrix.

VISITED_URL / n_new_url_domain is intentionally excluded (see Section 4.9 of the
paper on synthetic-scenario correlation risk). Restored as an ablation in
notebooks/06_baselines_ablation.ipynb (destination-novelty, Section 4.6).

Week indexing uses Neo4j's ISO week-year (`.weekYear`), not calendar year (`.year`).
Combining calendar year with an ISO week number mislabels the last days of a calendar
year that ISO already assigns to the following year's week 1 (and the symmetric case at
a year's start), producing two malformed windows (2010-53, 2011-52) that collapse into
one real ISO window each once `.weekYear` is used -- 76 calendar-labelled windows become
75 ISO ones, and 283,780 calendar-labelled rows become 283,519 (2,922 rows affected via
the delta features' trailing window at the two year boundaries). See the accompanying
manuscript, Eq. (7) and Sect. 4.1.
"""

import os
import time

import pandas as pd

PSYCH_FEATURES = ['Openness', 'Conscientiousness', 'Extraversion', 'Agreeableness', 'Neuroticism']
TECH_FEATURES = [
    'n_afterhourlogon', 'delta_afterhour',
    'email_mean_size', 'delta_email_size',
    'file_to_usb_bytes', 'delta_file_usb',
    'file_n_delete', 'delta_file_delete',
    'n_usb_connect', 'delta_usb',
]
ALL_FEATURES = PSYCH_FEATURES + TECH_FEATURES

DFS_QUERY = """
UNWIND $batch AS uid
MATCH (u:User {user_id: uid})-[r]->(target)
WHERE type(r) IN ['LOGGED_ON_TO','SENT_EMAIL','ACCESSED_FILE','CONNECTED_DEVICE']
WITH u, type(r) AS activity_type, r
RETURN
    u.user_id AS User_ID, u.role AS Role, u.department AS Department,
    u.O AS Openness, u.C AS Conscientiousness, u.E AS Extraversion,
    u.A AS Agreeableness, u.N AS Neuroticism,
    r.timestamp.weekYear AS Year, r.timestamp.week AS Week,
    COUNT(CASE WHEN activity_type='LOGGED_ON_TO'
               AND (r.timestamp.hour>=18 OR r.timestamp.hour<=6)
               THEN 1 END) AS n_afterhourlogon,
    AVG(CASE WHEN activity_type='SENT_EMAIL' THEN r.size END) AS email_mean_size,
    SUM(CASE WHEN activity_type='ACCESSED_FILE'
             AND r.to_removable_media=true THEN 1 ELSE 0 END) AS file_to_usb_bytes,
    SUM(CASE WHEN activity_type='ACCESSED_FILE'
             AND r.activity='File Delete' THEN 1 ELSE 0 END) AS file_n_delete,
    COUNT(CASE WHEN activity_type='CONNECTED_DEVICE' THEN 1 END) AS n_usb_connect
"""


def compute_delta(s):
    """Causal deviation from the trailing 4-week rolling mean."""
    return (s - s.shift(1).rolling(4, min_periods=1).mean()).fillna(0)


def build_master_features(conn, batch_size, checkpoint_path='../data/interim/dfs_checkpoint.csv'):
    """Runs (or loads cached) DFS extraction, then adds self-referential deltas."""
    start = time.time()
    if os.path.exists(checkpoint_path):
        df_master = pd.read_csv(checkpoint_path)
        print(f"=> Loaded from checkpoint: {len(df_master):,} rows "
              f"(delete {checkpoint_path} to re-query)")
    else:
        all_users = [r['user_id'] for r in
                     conn.query_to_dataframe("MATCH (u:User) RETURN u.user_id AS user_id")
                     .to_dict('records')]
        print(f"  Total users: {len(all_users):,} | batch={batch_size}")
        parts, n = [], (len(all_users) + batch_size - 1) // batch_size
        for i in range(n):
            batch = all_users[i * batch_size:(i + 1) * batch_size]
            df_b = conn.query_to_dataframe(DFS_QUERY, {"batch": batch})
            if not df_b.empty:
                parts.append(df_b)
            if (i + 1) % 10 == 0 or (i + 1) == n:
                print(f"  DFS batch {i+1}/{n} | {time.time()-start:.0f}s", flush=True)
        df_master = pd.concat(parts, ignore_index=True).fillna(0)
        os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
        df_master.to_csv(checkpoint_path, index=False)
        print(f"  Checkpoint saved -> {checkpoint_path}")

    df_master = df_master.sort_values(['User_ID', 'Year', 'Week']).reset_index(drop=True)
    for col, dcol in [('n_afterhourlogon', 'delta_afterhour'),
                       ('n_usb_connect', 'delta_usb'),
                       ('email_mean_size', 'delta_email_size'),
                       ('file_to_usb_bytes', 'delta_file_usb'),
                       ('file_n_delete', 'delta_file_delete')]:
        df_master[dcol] = df_master.groupby('User_ID')[col].transform(compute_delta)

    weeks_df = (df_master[['Year', 'Week']].drop_duplicates()
                    .sort_values(['Year', 'Week']).reset_index(drop=True))

    print(f"=> DFS done: {len(df_master):,} rows | "
          f"{df_master['User_ID'].nunique():,} users | {time.time()-start:.0f}s")
    return df_master, weeks_df
