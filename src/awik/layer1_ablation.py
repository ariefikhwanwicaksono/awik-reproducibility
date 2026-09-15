"""Architecture ablations for Layer 1: order/structure variants (B, C) and
same-algorithm-twice variants (D, E). All rejected in favor of the K-Means->DBSCAN
design (A) in layer1.py -- see notebooks/06_baselines_ablation.ipynb."""

import numpy as np
import pandas as pd
from scipy.spatial.distance import mahalanobis
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from .config import DEFAULT_EPS, DEFAULT_K, DEFAULT_MAH_THRESH, DEFAULT_MINPTS


def run_dbscan_then_kmeans(df_master, features, weeks_df, k=DEFAULT_K, eps=DEFAULT_EPS,
                            min_samples=DEFAULT_MINPTS, mah_thresh=DEFAULT_MAH_THRESH,
                            pca_seed=42, km_seed=42):
    """Variant B: global DBSCAN first, then K-Means+Mahalanobis on the non-noise core."""
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row['Year']), int(row['Week'])
        df_c = df_master[(df_master['Year'] == yr) & (df_master['Week'] == wk)] \
            .copy().reset_index(drop=True)
        if len(df_c) < 10:
            continue
        Xp = PCA(n_components=2, random_state=pca_seed).fit_transform(
            StandardScaler().fit_transform(df_c[features]))
        db = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(Xp)
        df_c['flag'] = 0
        df_c.loc[db == -1, 'flag'] = 1
        core = np.where(db != -1)[0]
        if len(core) >= k:
            kk = KMeans(n_clusters=k, random_state=km_seed, n_init=10).fit_predict(Xp[core])
            for cid in range(k):
                m = core[kk == cid]
                if len(m) < 3:
                    continue
                cov = np.cov(Xp[m], rowvar=False) + np.eye(2) * 1e-6
                inv = np.linalg.inv(cov)
                mu = Xp[m].mean(axis=0)
                mah = np.array([mahalanobis(Xp[i], mu, inv) ** 2 for i in m])
                df_c.loc[m[mah > mah_thresh], 'flag'] = 1
        df_c['EKS_Flag'] = df_c['flag']
        df_c['Year_Week'] = f'{yr}-W{wk:02d}'
        out.append(df_c)
    d = pd.concat(out, ignore_index=True)
    return d, d[d['EKS_Flag'] == 1].copy()


def run_voting_ensemble(df_master, features, weeks_df, k=DEFAULT_K, eps=DEFAULT_EPS,
                         min_samples=DEFAULT_MINPTS, mah_thresh=DEFAULT_MAH_THRESH,
                         std_mult=2, pca_seed=42, km_seed=42):
    """Variant C: true ensemble voting. 3 independent global scorers, flag if >=2 agree."""
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row['Year']), int(row['Week'])
        df_c = df_master[(df_master['Year'] == yr) & (df_master['Week'] == wk)] \
            .copy().reset_index(drop=True)
        if len(df_c) < 10:
            continue
        Xp = PCA(n_components=2, random_state=pca_seed).fit_transform(
            StandardScaler().fit_transform(df_c[features]))
        n = len(df_c)
        km = KMeans(n_clusters=k, random_state=km_seed, n_init=10)
        lb = km.fit_predict(Xp)
        v1 = np.zeros(n, int)
        for cid in range(k):
            mask = lb == cid
            pts = Xp[mask]
            if len(pts) < 3:
                continue
            dd = np.linalg.norm(pts - km.cluster_centers_[cid], axis=1)
            idx = np.where(mask)[0]
            v1[idx[dd > dd.mean() + std_mult * dd.std()]] = 1
        v2 = (DBSCAN(eps=eps, min_samples=min_samples).fit_predict(Xp) == -1).astype(int)
        cov = np.cov(Xp, rowvar=False) + np.eye(2) * 1e-6
        inv = np.linalg.inv(cov)
        mu = Xp.mean(axis=0)
        m = np.array([mahalanobis(p, mu, inv) ** 2 for p in Xp])
        v3 = (m > mah_thresh).astype(int)
        df_c['EKS_Flag'] = ((v1 + v2 + v3) >= 2).astype(int)
        df_c['Year_Week'] = f'{yr}-W{wk:02d}'
        out.append(df_c)
    d = pd.concat(out, ignore_index=True)
    return d, d[d['EKS_Flag'] == 1].copy()


def run_kmeans_then_kmeans(df_master, features, weeks_df, k=DEFAULT_K, sub_k=2,
                            std_mult=2, pca_seed=42, km_seed=42):
    """Variant D: K-Means twice. Stage 1 partitions k=4; stage 2 re-clusters within
    each partition and flags points far from their sub-cluster centroid."""
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row['Year']), int(row['Week'])
        df_c = df_master[(df_master['Year'] == yr) & (df_master['Week'] == wk)] \
            .copy().reset_index(drop=True)
        if len(df_c) < 10:
            continue
        Xp = PCA(n_components=2, random_state=pca_seed).fit_transform(
            StandardScaler().fit_transform(df_c[features]))
        km1 = KMeans(n_clusters=k, random_state=km_seed, n_init=10)
        lb1 = km1.fit_predict(Xp)
        flag = np.zeros(len(df_c), dtype=int)
        for cid in range(k):
            idx_c = np.where(lb1 == cid)[0]
            pts = Xp[idx_c]
            if len(pts) < sub_k * 3:
                continue
            km2 = KMeans(n_clusters=sub_k, random_state=km_seed, n_init=10)
            lb2 = km2.fit_predict(pts)
            c2 = km2.cluster_centers_
            for sid in range(sub_k):
                mask2 = lb2 == sid
                sub_pts = pts[mask2]
                if len(sub_pts) < 3:
                    continue
                d = np.linalg.norm(sub_pts - c2[sid], axis=1)
                thr = d.mean() + std_mult * d.std()
                local_idx = np.where(mask2)[0]
                flag[idx_c[local_idx[d > thr]]] = 1
        df_c['EKS_Flag'] = flag
        df_c['Year_Week'] = f'{yr}-W{wk:02d}'
        out.append(df_c)
    d = pd.concat(out, ignore_index=True)
    return d, d[d['EKS_Flag'] == 1].copy()


def run_dbscan_then_dbscan(df_master, features, weeks_df, eps=DEFAULT_EPS,
                            min_samples=DEFAULT_MINPTS, eps2_ratio=0.5, pca_seed=42):
    """Variant E: DBSCAN twice. Stage 1 global (noise = flagged); stage 2 re-runs
    DBSCAN inside each non-noise cluster with a tighter eps (eps2 = eps*eps2_ratio)."""
    eps2 = eps * eps2_ratio
    out = []
    for _, row in weeks_df.iterrows():
        yr, wk = int(row['Year']), int(row['Week'])
        df_c = df_master[(df_master['Year'] == yr) & (df_master['Week'] == wk)] \
            .copy().reset_index(drop=True)
        if len(df_c) < 10:
            continue
        Xp = PCA(n_components=2, random_state=pca_seed).fit_transform(
            StandardScaler().fit_transform(df_c[features]))
        db1 = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(Xp)
        flag = (db1 == -1).astype(int)
        for cid in set(db1):
            if cid == -1:
                continue
            idx_c = np.where(db1 == cid)[0]
            pts = Xp[idx_c]
            if len(pts) < min_samples:
                continue
            db2 = DBSCAN(eps=eps2, min_samples=min_samples).fit_predict(pts)
            flag[idx_c[db2 == -1]] = 1
        df_c['EKS_Flag'] = flag
        df_c['Year_Week'] = f'{yr}-W{wk:02d}'
        out.append(df_c)
    d = pd.concat(out, ignore_index=True)
    return d, d[d['EKS_Flag'] == 1].copy()
