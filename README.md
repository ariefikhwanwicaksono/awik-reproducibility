# AWIK -- Adaptive Weighted Insider Knowledge

Insider-threat detection on the CERT r6.2 dataset: two-stage spatial clustering
(Layer 1: K-Means -> DBSCAN -> Mahalanobis, all parameters derived label-free)
routed into surgical contextual graph inspection (Layer 2) by a causal adaptive
baseline. Evaluated against CERT r6.2's 6-actor Answer Set.

This repository accompanies a manuscript under review at the International
Journal of Intelligent Engineering and Systems. The code is released for
reproducibility of the reported results. Please contact the authors before reuse
or redistribution, and cite the paper once it is published.

## Structure

```
src/awik/          Reusable pipeline code (Layer 1, Layer 2, baselines, evaluation)
notebooks/         Numbered notebooks, run in order (01 -> 08)
data/raw/          CERT r6.2 raw logs + answer-key files (gitignored, see docs/dataset.md)
data/interim/      Checkpoints bridging notebooks (gitignored)
results/figures/   Generated figures (gitignored)
results/tables/    Generated tables (gitignored)
docs/              Methodology, decision history, dataset setup, Neo4j load script
```

## Notebooks

| # | Notebook | Produces |
|---|---|---|
| 01 | `data_extraction` | Weekly per-user feature matrix (`df_master`) via Neo4j DFS |
| 02 | `layer1_justification` | k / eps / minPts / Mahalanobis-threshold validation (diagnostic only) |
| 03 | `layer1_pipeline` | Layer 1 run + AWIK Score ranking |
| 04 | `layer2_adaptive_baseline_graph` | Causal surge detection, targeting, G1-G6 graph inspection, routing ablation (raw) |
| 05 | `evaluation` | Final suspect tiers, formal evaluation, per-account audit tables, precision/FPR/PR-AUC at fixed investigation budgets |
| 06 | `baselines_ablation` | Comparison baselines (Isolation Forest/LOF, Graph Autoencoder, NSGA-II-tuned IF), destination-novelty feature ablation, Layer-1 architecture ablation |
| 07 | `robustness_evasion` | Sensitivity sweep, multi-seed check, covariance-aligned evasion diagnostic |
| 08 | `paper_figures` | Final summary + remaining figures |

Each notebook loads the previous notebooks' checkpoints from `data/interim/`
(see `src/awik/io.py`) rather than assuming a single shared kernel session, so
any notebook can be rerun on its own once its inputs exist.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Requires a running Neo4j instance loaded with the CERT r6.2 graph schema
(`User`, `PC`, `URL` nodes; `LOGGED_ON_TO`, `SENT_EMAIL`, `ACCESSED_FILE`,
`CONNECTED_DEVICE`, `VISITED_URL` relationships) at `bolt://localhost:7687`.
Connection credentials are set at the top of notebooks 01, 04, 06, and 08;
the password is read from the `NEO4J_PASSWORD` environment variable
(`export NEO4J_PASSWORD=yourpassword` before launching Jupyter), not hardcoded.

The CERT r6.2 dataset and the answer-key files are not included (license
forbids redistribution, and at ~93GB raw it's far past what git/GitHub can
hold anyway). See [`docs/dataset.md`](docs/dataset.md) for where to obtain
both and the local folder layout this repo expects, and
[`docs/neo4j_load.cypher`](docs/neo4j_load.cypher) for the `LOAD CSV`
statements that build the graph.

## Where things live

| Component | File / path | Notes |
|---|---|---|
| Preprocessing: CERT r6.2 logs -> account-week observations | `docs/neo4j_load.cypher` (raw CSV -> graph) + `src/awik/features.py` (`DFS_QUERY`, `build_master_features`), run by `notebooks/01_data_extraction.ipynb` | Produces `data/interim/01_df_master.csv`; verified at 283,780 rows on the full r6.2 dataset. |
| Weekly-window construction | `src/awik/features.py` (`DFS_QUERY`, `r.timestamp.week AS Week`) | Week = Neo4j's native ISO-calendar `.week` accessor on each event timestamp. No custom start/end cutoff; the observed 76 windows are whichever (Year, Week) pairs occur in the data. |
| Feature generation | `src/awik/features.py` | `ALL_FEATURES` (15 features: 5 OCEAN + 5 level + 5 causal deltas), `compute_delta` (4-week rolling deviation, causal by construction) |
| PCA/scaling pipeline | `src/awik/layer1.py` (canonical), also inlined in `src/awik/layer1_ablation.py`, `src/awik/baseline_unsupervised.py` | `StandardScaler -> PCA(n_components=2, random_state=42)`, consistent everywhere. Repeated inline by design rather than factored into one shared function, since each caller varies which clustering step follows. |
| Clustering configurations | `src/awik/layer1.py` (design A + variants EKS-2/EKS-3), `src/awik/layer1_ablation.py` (variants B/C/D/E), `src/awik/baseline_unsupervised.py` (IF/LOF) | 13 configurations in total across these files. |
| Label-free parameter selection (k, eps, minPts) | `notebooks/02_layer1_justification.ipynb` | Reproduces `EPS_STAGE1=0.372`, close to the `DEFAULT_EPS=0.39` used in the main pipeline. |
| Random seeds | `docs/reproducibility.md` | Full inventory: every file, every seeded call, every value (uniformly 42, except the deliberate `SEEDS=[0,1,7,21,42,100,123]` sweep in notebook 07). |
| Adaptive-routing implementation | `src/awik/adaptive_baseline.py` | `compute_surge_signals` (causal, expanding/trailing-only stats) + `target_users` (persistence/co-occurrence/burst) |
| G1-G5 Cypher queries, standalone | `docs/g1_g6_queries.cypher` | All 5 active patterns, extracted verbatim, runnable outside Python. Code uses the labels G1, G2, G3, G5, G6 (G4 is permanently disabled -- see `features.py`'s docstring); the manuscript renumbers to close that gap (code G5 -> paper G4, code G6 -> paper G5) -- full mapping in this file's own header comment. |
| Statistical enrichment + hypergeometric test | `src/awik/evaluation.py` (`enrichment`, `enrichment_pvalue`) | Uses `scipy.stats.hypergeom.sf`. |

## Notes

Every Layer 1 parameter (`src/awik/config.py`) is derived label-free -- the
Answer Set (`ANSWER_SET`) is only ever used for evaluation, never for tuning,
with one deliberate exception: the NSGA-II-tuned Isolation Forest baseline in
notebook 06 is supervised by design, included for comparison against a
category of methods that legitimately does use labels.

## Data attribution

The CERT r6.2 dataset is Copyright 2011 ExactData, LLC, All Rights Reserved, and
is used under its End User Agreement. This repository contains no CERT data
except the six Answer Set account identifiers in `src/awik/config.py`, which are
reproduced only to the minimal extent needed to describe the reported evaluation.
