# Reproducibility: random seeds

Every stochastic component in this repo is seeded. This is a consolidated inventory
(file, seed value, what it controls) -- no seed value listed here was changed while
compiling this list; it's a documentation pass only.

## `src/awik/layer1.py`

| Function | `pca_seed` | `km_seed` | Controls |
|---|---|---|---|
| `run_awik_pipeline` (Layer 1: K-Means->DBSCAN->Mahalanobis) | 42 | 42 | PCA projection to 2D; K-Means macro-role partition |
| `run_kmeans_only` (ablation EKS-2) | 42 | 42 | Same |
| `run_dbscan_only` (ablation EKS-3) | 42 | n/a (no K-Means) | PCA projection only |

## `src/awik/layer1_ablation.py`

| Function | `pca_seed` | `km_seed` | Controls |
|---|---|---|---|
| `run_dbscan_then_kmeans` (variant B) | 42 | 42 | PCA; K-Means on DBSCAN-core points |
| `run_voting_ensemble` (variant C) | 42 | 42 | PCA; K-Means voter |
| `run_kmeans_then_kmeans` (variant D) | 42 | 42 | PCA; both K-Means stages share `km_seed` |
| `run_dbscan_then_dbscan` (variant E) | 42 | n/a | PCA projection only |

## `src/awik/baseline_unsupervised.py`

| Function | Seed param | Value | Controls |
|---|---|---|---|
| `run_unsupervised_baseline` (R2-1a: IF/LOF, contamination=0.05 fixed) | `random_state` | 42 | Isolation Forest only (LOF has no seed -- deterministic given data + params) |
| `run_isolation_forest` (EKS-4, contamination='auto') | `pca_seed`, `if_seed` | 42, 42 | PCA; Isolation Forest |
| `run_lof` (EKS-5, contamination='auto') | `pca_seed` | 42 | PCA only (LOF deterministic) |

## Notebook-only seeds (not in `src/`)

| Location | Seed | Controls |
|---|---|---|
| `notebooks/02_layer1_justification.ipynb`, every diagnostic cell (k-optimal, PCA structure, stability check, DBSCAN param justification, cluster-vs-role validation, normality diagnostics, threshold empirical-vs-Yeo-Johnson, eps stage-1/2 derivation) | `random_state=42` | Every `PCA(...)`/`KMeans(...)` call in this notebook, no exceptions |
| `notebooks/06_baselines_ablation.ipynb`, R2-1b (Graph Autoencoder) | `torch.manual_seed(42)` | GCN encoder weight init + training stochasticity |
| `notebooks/06_baselines_ablation.ipynb`, R2-1c (Isolation Forest + NSGA-II) | `random_state=42` (IsolationForest inside the NSGA-II objective), `seed=42` (`pymoo.optimize.minimize`) | IF hyperparameter search reproducibility |
| `notebooks/07_robustness_evasion.ipynb`, sensitivity sweep | `random_state=42` (fixed, not swept -- only `eps` varies) | PCA/K-Means inside the eps sweep |
| `notebooks/07_robustness_evasion.ipynb`, multi-seed robustness cell | `SEEDS = [0, 1, 7, 21, 42, 100, 123]` | Explicitly sweeps `km_seed` through `run_awik_pipeline`/`run_kmeans_only` to test whether Layer 1 recall depends on the K-Means seed (result: std=0.000 across all seeds -- deterministic) |
| `notebooks/07_robustness_evasion.ipynb`, `notebooks/08_paper_figures.ipynb` | `nx.spring_layout(..., seed=42)` | Cosmetic only -- graph node layout for figures, does not affect any detection/evaluation result |

## Not seeded (and why that's fine)

- `src/awik/adaptive_baseline.py` -- fully deterministic (expanding-window statistics,
  no randomness).
- `src/awik/graph_inspection.py`, `src/awik/evaluation.py`, `src/awik/neo4j_client.py`,
  `src/awik/stats_utils.py`, `src/awik/features.py` -- no stochastic operations.
- DBSCAN itself has no seed parameter (deterministic given input and `eps`/`min_samples`).

## Non-determinism that WAS present, and is fixed on this branch

`src/awik/graph_inspection.py` has no RNG, but until this branch its G1/G2/G3/G4(code-G5)
queries each carried a per-batch `LIMIT` (200/200/100/100/300), and callers passed candidate
lists built from `list(some_set)`. Python randomizes string-hash seeding per process
(`PYTHONHASHSEED`), which changes `set` iteration order and therefore which accounts land in
which batch; when a batch's true match count exceeds its `LIMIT`, the accounts cut off depend
on that batch composition. Measured effect on CERT r6.2 (`fig3_validation/round2/REPORT.md`,
`round3/REPORT.md`): the routing-active graph-confirmed population varied 304-307 across
`PYTHONHASHSEED` values with the LIMIT in place, and G1/G2 batches hit their LIMIT in
essentially 100% of batches examined -- i.e. the reported match counts for those two queries
were a truncated lower bound, not the true count. This branch removes the `LIMIT` clauses and
requires callers to pass `sorted()` candidate lists, which empirically restores exact,
seed-independent reproducibility (`round3/REPORT.md` section 2: identical account-ID sets
across 5 seeds + sorted input, both before and after this fix's population sizes).

## Net effect

Every `PCA`/`KMeans` call across the entire repo uses seed **42**, with zero
exceptions found in this audit (2026-09-07). The one deliberate seed *sweep*
(`notebooks/07_robustness_evasion.ipynb`, `SEEDS`) exists specifically to test
robustness to that choice, and confirms the result is seed-invariant.
