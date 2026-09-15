"""Layer 2 trigger: causal (expanding, trailing-only) per-user adaptive baseline,
surge detection, and persistence/co-occurrence/burst targeting.

Causal fix for reviewer R2-3: v3 used full-history stats (temporal leakage). This
version uses expanding().shift(1) per user, so a user's baseline only ever reflects
weeks strictly before the one being scored. Consequence (not a bug): a user's first
observed week can never trigger a surge, since there is no prior baseline yet.
"""

import math

import numpy as np
import pandas as pd

MIN_OBS = 8  # gates the email channel only (kept from the original, not new)


def compute_surge_signals(df_master, min_obs=MIN_OBS):
    df_sorted = df_master.sort_values(['User_ID', 'Year', 'Week']).reset_index(drop=True)
    g = df_sorted.groupby('User_ID', sort=False)

    for col, pfx in [('delta_afterhour', 'dah'), ('delta_usb', 'dusb'),
                      ('delta_email_size', 'dmail')]:
        df_sorted[f'{pfx}_mean_c'] = g[col].expanding().mean().shift(1).reset_index(level=0, drop=True)
        df_sorted[f'{pfx}_std_c'] = g[col].expanding().std().shift(1).reset_index(level=0, drop=True)
    df_sorted['n_obs_c'] = g.cumcount()
    df_sorted['email_scale_c'] = g['email_mean_size'].expanding().mean().shift(1).reset_index(level=0, drop=True)
    for pfx in ['dah', 'dusb', 'dmail']:
        df_sorted[f'{pfx}_std_c'] = df_sorted[f'{pfx}_std_c'].fillna(0)

    lon_ah = df_sorted['delta_afterhour'] > (df_sorted['dah_mean_c'].fillna(np.inf) +
                                              2 * df_sorted['dah_std_c'].clip(lower=0.1))
    lon_usb = df_sorted['delta_usb'] > (df_sorted['dusb_mean_c'].fillna(np.inf) +
                                         2 * df_sorted['dusb_std_c'].clip(lower=0.1))
    enough = df_sorted['n_obs_c'] >= min_obs
    floor_em = (0.5 * df_sorted['email_scale_c'].fillna(0)).clip(lower=1.0)
    lon_email = enough & (df_sorted['delta_email_size'] >
                           (df_sorted['dmail_mean_c'].fillna(np.inf) +
                            2 * df_sorted['dmail_std_c'].clip(lower=floor_em)))

    df_sorted['lon_ah'] = lon_ah.astype(int)
    df_sorted['lon_usb'] = lon_usb.astype(int)
    df_sorted['lon_email'] = lon_email.astype(int)

    any_surge = lon_ah | lon_usb | lon_email
    df_surges = df_sorted.loc[any_surge, ['User_ID', 'Year', 'Week',
                                             'lon_ah', 'lon_usb', 'lon_email']].copy()
    df_surges['Year_Week'] = (df_surges['Year'].astype(int).astype(str) + '-W' +
                                 df_surges['Week'].astype(int).astype(str).str.zfill(2))
    return df_sorted, df_surges


def target_users(df_surges, n_weeks):
    """Persistence / co-occurrence / burst targeting (unchanged from v3 -- already
    per-week/self-referential, no temporal leakage)."""
    surge_cols = ['lon_ah', 'lon_usb', 'lon_email']
    if not df_surges.empty:
        df_surges = df_surges.copy()
        df_surges['n_cooccur'] = df_surges[surge_cols].sum(axis=1)
        per_user = df_surges.groupby('User_ID').agg(
            surge_weeks=('Year_Week', 'nunique'),
            cooccur_weeks=('n_cooccur', lambda x: int((x >= 2).sum())),
            max_cooccur=('n_cooccur', 'max'),
        )
    else:
        per_user = pd.DataFrame(columns=['surge_weeks', 'cooccur_weeks', 'max_cooccur'])

    p_any = 1 - (1 - 0.0228) ** len(surge_cols)
    exp_chance = n_weeks * p_any
    k_persist = max(3, int(math.ceil(2 * exp_chance)))
    k_cooccur = 2
    k_burst = 3

    cand_persist = set(per_user.index[per_user['surge_weeks'] >= k_persist]) if len(per_user) else set()
    cand_cooccur = set(per_user.index[per_user['cooccur_weeks'] >= k_cooccur]) if len(per_user) else set()
    cand_burst = set(per_user.index[per_user['max_cooccur'] >= k_burst]) if len(per_user) else set()
    users_targeted = cand_persist | cand_cooccur | cand_burst
    users_surged = set(per_user.index) if len(per_user) else set()

    return {
        'k_persist': k_persist, 'k_cooccur': k_cooccur, 'k_burst': k_burst,
        'per_user': per_user, 'users_targeted': users_targeted, 'users_surged': users_surged,
    }
