"""Layer 1: two-stage spatial clustering (K-Means -> DBSCAN -> Mahalanobis), plus
single-algorithm baselines used in the ablation study."""

import numpy as np
import pandas as pd
from scipy.spatial.distance import mahalanobis
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from .config import DEFAULT_EPS, DEFAULT_K, DEFAULT_MAH_THRESH, DEFAULT_MINPTS


def run_awik_pipeline(df_master, features, weeks_df,
                       k=DEFAULT_K, eps=DEFAULT_EPS, min_samples=DEFAULT_MINPTS,
                       mah_thresh=DEFAULT_MAH_THRESH, pca_seed=42, km_seed=42):
    """K-Means (macro-role) -> DBSCAN (per-cluster) -> Mahalanobis^2 (per-cluster,
    empirical fixed threshold). Run per weekly window."""
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row['Year']), int(row['Week'])
        df_c = df_master[(df_master['Year'] == yr) & (df_master['Week'] == wk)] \
            .copy().reset_index(drop=True)
        if len(df_c) < 10:
            continue
        X = StandardScaler().fit_transform(df_c[features])
        Xp = PCA(n_components=2, random_state=pca_seed).fit_transform(X)
        df_c['PC1'], df_c['PC2'] = Xp[:, 0], Xp[:, 1]

        km = KMeans(n_clusters=k, random_state=km_seed, n_init=10)
        df_c['Macro_Role'] = km.fit_predict(Xp)
        df_c['DBSCAN_Label'] = 0
        df_c['Mahalanobis_Sq'] = 0.0
        df_c['AWIK_Flag'] = 0

        for cid in range(k):
            mask = df_c['Macro_Role'] == cid
            pts = Xp[mask.values]
            idx = df_c.index[mask]
            if len(pts) < min_samples:
                continue
            db = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(pts)
            df_c.loc[idx, 'DBSCAN_Label'] = db
            clean = pts[db != -1]
            if len(clean) < 3:
                continue
            cov = np.cov(clean, rowvar=False) + np.eye(2) * 1e-6  # Tikhonov reg.
            inv_cov = np.linalg.inv(cov)
            mean_c = np.mean(clean, axis=0)
            mah = np.array([mahalanobis(p, mean_c, inv_cov) ** 2 for p in pts])
            df_c.loc[idx, 'Mahalanobis_Sq'] = mah
            df_c.loc[idx, 'AWIK_Flag'] = np.where((mah > mah_thresh) | (db == -1), 1, 0)
        df_c['Year_Week'] = f'{yr}-W{wk:02d}'
        out.append(df_c)
    df_all = pd.concat(out, ignore_index=True)
    return df_all, df_all[df_all['AWIK_Flag'] == 1].copy()


def run_kmeans_only(df_master, features, weeks_df, k=DEFAULT_K, std_mult=2,
                     pca_seed=42, km_seed=42):
    """Ablation: K-Means alone. Flag = Euclidean distance to centroid > mean + std_mult*std."""
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row['Year']), int(row['Week'])
        df_c = df_master[(df_master['Year'] == yr) & (df_master['Week'] == wk)] \
            .copy().reset_index(drop=True)
        if len(df_c) < 10:
            continue
        X = StandardScaler().fit_transform(df_c[features])
        Xp = PCA(n_components=2, random_state=pca_seed).fit_transform(X)
        km = KMeans(n_clusters=k, random_state=km_seed, n_init=10)
        lb = km.fit_predict(Xp)
        c = km.cluster_centers_
        flag = np.zeros(len(df_c), dtype=int)
        for cid in range(k):
            mask = lb == cid
            pts = Xp[mask]
            if len(pts) < 3:
                continue
            d = np.linalg.norm(pts - c[cid], axis=1)
            thr = d.mean() + std_mult * d.std()
            idx = np.where(mask)[0]
            flag[idx[d > thr]] = 1
        df_c['EKS_Flag'] = flag
        df_c['Year_Week'] = f'{yr}-W{wk:02d}'
        out.append(df_c)
    d = pd.concat(out, ignore_index=True)
    return d, d[d['EKS_Flag'] == 1].copy()


def run_dbscan_only(df_master, features, weeks_df, eps=DEFAULT_EPS,
                     min_samples=DEFAULT_MINPTS, pca_seed=42):
    """Ablation: global DBSCAN alone, no K-Means pre-partition. Noise (-1) = anomaly."""
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row['Year']), int(row['Week'])
        df_c = df_master[(df_master['Year'] == yr) & (df_master['Week'] == wk)] \
            .copy().reset_index(drop=True)
        if len(df_c) < 10:
            continue
        X = StandardScaler().fit_transform(df_c[features])
        Xp = PCA(n_components=2, random_state=pca_seed).fit_transform(X)
        db = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(Xp)
        df_c['EKS_Flag'] = (db == -1).astype(int)
        df_c['Year_Week'] = f'{yr}-W{wk:02d}'
        out.append(df_c)
    d = pd.concat(out, ignore_index=True)
    return d, d[d['EKS_Flag'] == 1].copy()
