# Reproducing the deterministic Table 4-11 numbers (branch `fix/g1-g4-unlimited-sorted`)

This branch removes the per-batch `LIMIT` from the G1/G2/G3/G4(code-G5) Cypher queries
(`src/awik/graph_inspection.py`, `docs/g1_g6_queries.cypher`) and switches candidate-list
construction in `notebooks/04_layer2_adaptive_baseline_graph.ipynb` from `list(some_set)` to
`sorted(some_set)`. See `docs/reproducibility.md`'s "Non-determinism that WAS present" section
for why, and `fig3_validation/round2/REPORT.md` + `round3/REPORT.md` for the measurements.

## One-line reproduce

```bash
export NEO4J_PASSWORD=yourpassword
cd notebooks && jupyter nbconvert --to notebook --execute --inplace \
  01_data_extraction.ipynb 02_layer1_justification.ipynb 03_layer1_pipeline.ipynb \
  04_layer2_adaptive_baseline_graph.ipynb 05_evaluation.ipynb
```

On this branch, `04_layer2_adaptive_baseline_graph.ipynb`'s output no longer depends on
`PYTHONHASHSEED` -- any two runs against the same Neo4j database produce identical account-ID
sets in every table, not just identical counts.

## Integrity checks

- `data/interim/01_df_master.csv` should be **283,780 rows, 76 (Year, Week) windows** if built
  from `r.timestamp.year` (calendar year, the code as shipped on `main`). If you have applied
  the ISO week-year correction described in the manuscript (Sect. 3.1/4.1) -- swapping the DFS
  query's `Year` accessor to `r.timestamp.weekYear` -- expect **283,519 rows, 75 windows**
  instead (`fig3_validation/round2/REPORT.md`, part A.1). This branch does not itself apply that
  swap; it is an orthogonal fix, exercised separately in `fig3_validation/round4`.
- Code checksums (SHA-256) at the point this branch was cut:

  | File | SHA-256 |
  |---|---|
  | `src/awik/graph_inspection.py` | `d1ffcc72f7247674724605d583066a6068cbfd8b46f12a03f863fdd181cd4c8d` |
  | `src/awik/layer1.py` | `5e4b618bbcbe397ce1ba65c21d82697ca6668a822ff51d6460a3504d4df09f74` |
  | `src/awik/adaptive_baseline.py` | `5d2a4b02bdafb41b6b9ed6cf7eac17cbb4d426ef52714a491b3176f1b2657992` |
  | `src/awik/config.py` | `70c035147578cd7bcb08b87218069113b0c306aba25899d40696a43951dbc746` |
  | `docs/g1_g6_queries.cypher` | `035e7215d8efdf780b14587b1d0ed6d4b3a0552f50fa2e62d53102eaf38bb21a` |

  Verify with `shasum -a 256 <file>` and compare.
- Environment this branch was validated under: Python 3.9.6, scikit-learn 1.6.1, scipy 1.13.1,
  numpy 2.0.2, pandas 2.3.3, neo4j Python driver 5.28.4, Neo4j server 2026.05.0. Full record:
  `fig3_validation/round4/data/environment.json`.

## What changed numerically

Removing the LIMIT changes reported match counts and population sizes -- it does not change
which mechanism (Layer 1 vs. relational graph) recovers which Answer Set account. Full
before/after numbers: `fig3_validation/round4/DIFF_vs_manuscript.md`.
