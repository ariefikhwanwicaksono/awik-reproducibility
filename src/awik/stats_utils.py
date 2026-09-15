"""Small numerical helpers reused across parameter-justification notebooks."""

import numpy as np


def knee_of_curve(y_sorted_asc):
    """Knee point = max perpendicular distance from the chord joining curve endpoints."""
    n = len(y_sorted_asc)
    if n < 3:
        return None, None
    x = np.arange(n, dtype=float)
    x = (x - x.min()) / (x.max() - x.min() + 1e-12)
    y = y_sorted_asc.astype(float)
    yn = (y - y.min()) / (y.max() - y.min() + 1e-12)
    x1, y1, x2, y2 = 0.0, yn[0], 1.0, yn[-1]
    num = np.abs((y2 - y1) * x - (x2 - x1) * yn + x2 * y1 - y2 * x1)
    den = np.hypot(y2 - y1, x2 - x1) + 1e-12
    idx = int(np.argmax(num / den))
    return idx, float(y[idx])


def sampled_weeks(weeks_df, step=5):
    """Systematic (not cherry-picked) sample of every `step`-th week."""
    return weeks_df.iloc[list(range(0, len(weeks_df), step))].reset_index(drop=True)
