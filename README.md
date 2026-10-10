# AWIK -- Adaptive Windowed Insider Knowledge

Insider-threat detection on the CERT r6.2 dataset: two-stage spatial clustering
(Layer 1: K-Means -> DBSCAN -> Mahalanobis, all parameters derived label-free)
routed into surgical contextual graph inspection (Layer 2) by a causal adaptive
baseline. Evaluated against CERT r6.2's 6-actor Answer Set.

This repository accompanies ongoing doctoral research on insider-threat
detection, currently the subject of a manuscript under peer review. It is
released solely so reviewers and readers can verify the reported results --
no license is granted for any other use. In particular, this code, its
derivatives, or the specific parameter values/architectural choices in this
repository may not be used in, or form the basis of, another publication on
insider-threat detection or a similar topic without the authors' prior
written permission. Contact the authors before any reuse or redistribution,
and cite the paper once it is published.

This pipeline runs under a single deterministic protocol: ISO week-year time
indexing (`.weekYear`, 75 windows, 283,519 account-weeks -- not the earlier
calendar-year indexing's 76/283,780), label-free re-derived Layer 1 parameters
(`eps=0.3672`, `tau=37.44`), and Layer 2 graph queries (G1-G4) that run without a
per-batch result cap and are therefore exactly reproducible regardless of
`PYTHONHASHSEED`. See [`docs/REPRODUCE.md`](docs/REPRODUCE.md) for the one-line
reproduce command and exactly what changed and why.

## Structure

```
src/awik/          Reusable pipeline code (Layer 1, Layer 2, baselines, evaluation)
notebooks/         Numbered notebooks, run in order (01 -> 08)
scripts/           Standalone verification scripts (e.g. Section 4.5's full-population
                   G5 check), runnable independently of the full notebook sequence
data/raw/          CERT r6.2 raw logs + answer-key files (gitignored, see docs/dataset.md)
data/interim/      Checkpoints bridging notebooks (gitignored)
results/figures/   Generated figures (gitignored)
results/tables/    Generated tables (gitignored)
docs/              Dataset setup, Neo4j load script, G1-G5 Cypher queries, random-seed inventory
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
| Preprocessing: CERT r6.2 logs -> account-week observations | `docs/neo4j_load.cypher` (raw CSV -> graph) + `src/awik/features.py` (`DFS_QUERY`, `build_master_features`), run by `notebooks/01_data_extraction.ipynb` | Produces `data/interim/01_df_master.csv`; verified at 283,519 rows on the full r6.2 dataset (ISO week-year indexing -- see next row). |
| Weekly-window construction | `src/awik/features.py` (`DFS_QUERY`, `r.timestamp.weekYear AS Year`, `r.timestamp.week AS Week`) | Year+Week together form Neo4j's ISO week-year, not calendar year + ISO week number -- the two disagree at each year boundary, which used to produce two malformed labels (`2010-53`, `2011-52`) that collapse into one real ISO window each once `.weekYear` is used. 76 calendar-labelled windows become 75 ISO ones. |
| Feature generation | `src/awik/features.py` | `ALL_FEATURES` (15 features: 5 OCEAN + 5 level + 5 causal deltas), `compute_delta` (4-week rolling deviation, causal by construction) |
| PCA/scaling pipeline | `src/awik/layer1.py` (canonical), also inlined in `src/awik/layer1_ablation.py`, `src/awik/baseline_unsupervised.py` | `StandardScaler -> PCA(n_components=2, random_state=42)`, consistent everywhere. Repeated inline by design rather than factored into one shared function, since each caller varies which clustering step follows. |
| Clustering configurations | `src/awik/layer1.py` (design A + variants EKS-2/EKS-3), `src/awik/layer1_ablation.py` (variants B/C/D/E), `src/awik/baseline_unsupervised.py` (IF/LOF) | 13 configurations in total across these files. |
| Label-free parameter selection (k, eps, minPts) | `notebooks/02_layer1_justification.ipynb` | Reproduces `EPS_STAGE1=0.3658` (a separate, independently-derived value used only by the DB->DB architecture ablation), close to the `DEFAULT_EPS=0.3672` used in the main pipeline. |
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
