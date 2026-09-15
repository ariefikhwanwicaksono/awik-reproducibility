"""Standard unsupervised anomaly-detection baselines (R2-1, Cell 10e), evaluated
under the same per-week / union-to-account protocol as Layer 1."""

import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler


def run_unsupervised_baseline(df_master, features, weeks_df, method="iforest",
                               contamination=0.05, random_state=42):
    """R2-1a: Isolation Forest / LOF at a fixed contamination (not tuned to the
    Answer Set), for an apples-to-apples comparison against Layer 1's flagging rate."""
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row["Year"]), int(row["Week"])
        df_w = df_master[(df_master["Year"] == yr) & (df_master["Week"] == wk)].copy()
        if len(df_w) < 10:
            continue
        X = StandardScaler().fit_transform(df_w[features])
        if method == "iforest":
            model = IsolationForest(contamination=contamination, random_state=random_state)
        elif method == "lof":
            model = LocalOutlierFactor(contamination=contamination, novelty=False)
        else:
            raise ValueError(method)
        pred = model.fit_predict(X)  # -1 = anomaly
        df_w["Flag"] = (pred == -1).astype(int)
        df_w["Year_Week"] = f"{yr}-W{wk:02d}"
        out.append(df_w)
    d = pd.concat(out, ignore_index=True)
    return d, set(d.loc[d["Flag"] == 1, "User_ID"].unique())


def run_isolation_forest(df_master, features, weeks_df, pca_seed=42, if_seed=42):
    """Cell 10e (EKS-4): Isolation Forest, contamination='auto' (Liu et al. 2008)."""
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row['Year']), int(row['Week'])
        df_c = df_master[(df_master['Year'] == yr) & (df_master['Week'] == wk)] \
            .copy().reset_index(drop=True)
        if len(df_c) < 10:
            continue
        Xp = PCA(n_components=2, random_state=pca_seed).fit_transform(
            StandardScaler().fit_transform(df_c[features]))
        iso = IsolationForest(contamination='auto', random_state=if_seed, n_estimators=200)
        df_c['EKS_Flag'] = (iso.fit_predict(Xp) == -1).astype(int)
        df_c['Year_Week'] = f'{yr}-W{wk:02d}'
        out.append(df_c)
    d = pd.concat(out, ignore_index=True)
    return d, d[d['EKS_Flag'] == 1].copy()


def run_lof(df_master, features, weeks_df, pca_seed=42, n_neighbors=20):
    """Cell 10e (EKS-5): Local Outlier Factor, contamination='auto'."""
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row['Year']), int(row['Week'])
        df_c = df_master[(df_master['Year'] == yr) & (df_master['Week'] == wk)] \
            .copy().reset_index(drop=True)
        if len(df_c) < 10:
            continue
        Xp = PCA(n_components=2, random_state=pca_seed).fit_transform(
            StandardScaler().fit_transform(df_c[features]))
        n_neigh = min(n_neighbors, len(df_c) - 1)
        if n_neigh < 2:
            df_c['EKS_Flag'] = 0
        else:
            lof = LocalOutlierFactor(n_neighbors=n_neigh, contamination='auto')
            df_c['EKS_Flag'] = (lof.fit_predict(Xp) == -1).astype(int)
        df_c['Year_Week'] = f'{yr}-W{wk:02d}'
        out.append(df_c)
    d = pd.concat(out, ignore_index=True)
    return d, d[d['EKS_Flag'] == 1].copy()
