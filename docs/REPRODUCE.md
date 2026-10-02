# Reproducing the Table 4-11 numbers (protocol P*)

`main` implements a single deterministic protocol, referred to throughout this repo
and the accompanying manuscript as **P***:

1. **ISO week-year time indexing.** `src/awik/features.py`'s DFS query reads
   `r.timestamp.weekYear AS Year` (not `.year`), so `Year`+`Week` together form one
   consistent ISO week-year rather than calendar year paired with an ISO week number.
   The two disagree at each year boundary, which used to produce two malformed labels
   (`2010-53`, `2011-52`); under `.weekYear` these collapse into one real ISO window
   each. Result: **283,519 rows, 75 windows** (previously 283,780 / 76).
2. **Label-free re-derived Layer 1 parameters.** `src/awik/config.py`'s `DEFAULT_EPS`
   (0.3672, was 0.39) and `DEFAULT_MAH_THRESH` (37.44, was 31.75) are re-derived from
   the ISO-corrected data by the same label-free procedure in
   `notebooks/02_layer1_justification.ipynb` (median within-cluster k-distance knee
   over 15 sampled weeks; median of per-cluster-week 99th-percentile Mahalanobis²).
   `DEFAULT_K=4` is unchanged.
3. **G1-G4 run without a per-batch result cap.** `src/awik/graph_inspection.py`'s
   Q_G1/Q_G2/Q_G3A/Q_G3B and the code-G5/paper-G4 query no longer carry a `LIMIT`
   clause, and callers pass `sorted()` candidate lists, not a bare `list(some_set)`.

## Why this protocol exists

An internal audit found that the per-batch `LIMIT` (previously 200/200/100/100/300)
bound in nearly every batch at this pipeline's population sizes -- e.g. G2 in the
routing-disabled condition hit its cap in 22/22 batches examined -- so reported match
counts were a truncated lower bound, not the true count. Because Python randomizes
string-hash seeding per process (`PYTHONHASHSEED`), this also made which accounts got
cut off, and therefore the graph-confirmed population, non-reproducible run to run
(304-307 accounts observed across seeds on the pre-fix code). Removing the cap and
sorting candidate lists restores exact, seed-independent reproducibility: repeated
runs against the same Neo4j database now return byte-identical account-ID sets in
every table, not just identical counts.

## One-line reproduce

```bash
export NEO4J_PASSWORD=yourpassword
cd notebooks && jupyter nbconvert --to notebook --execute --inplace \
  01_data_extraction.ipynb 02_layer1_justification.ipynb 03_layer1_pipeline.ipynb \
  04_layer2_adaptive_baseline_graph.ipynb 05_evaluation.ipynb
```

If `data/interim/01_df_master.csv` or `dfs_checkpoint.csv` already exist from a run
predating this protocol, delete them first -- notebook 01 loads a cached checkpoint
rather than re-querying Neo4j, and a stale (calendar-year-labelled) checkpoint will
silently carry the old 283,780/76-window data forward into every later notebook.

## Integrity check

`data/interim/01_df_master.csv` should be **283,519 rows, 75 (Year, Week) windows**.
If you see 283,780 rows / 76 windows instead, the checkpoint predates this protocol
(see above) or `features.py`'s DFS query has been reverted to `.year`.

Code checksums (SHA-256) at the point this protocol was merged into `main`:

| File | SHA-256 |
|---|---|
| `src/awik/graph_inspection.py` | `d1ffcc72f7247674724605d583066a6068cbfd8b46f12a03f863fdd181cd4c8d` |
| `src/awik/features.py` | `05289321ab0d59a755ad0c41e9e82fec28cae8a647b9ab14705e313266744f0d` |
| `src/awik/config.py` | `b9f7d5e66fff470a9ddd387c1b5b1ade4dfedfb11bd6b1fb87f4163551a3677e` |
| `src/awik/layer1.py` | `5e4b618bbcbe397ce1ba65c21d82697ca6668a822ff51d6460a3504d4df09f74` |
| `src/awik/adaptive_baseline.py` | `5d2a4b02bdafb41b6b9ed6cf7eac17cbb4d426ef52714a491b3176f1b2657992` |
| `docs/g1_g6_queries.cypher` | `035e7215d8efdf780b14587b1d0ed6d4b3a0552f50fa2e62d53102eaf38bb21a` |

Verify with `shasum -a 256 <file>` and compare.

Environment this protocol was validated under: Python 3.9.6, scikit-learn 1.6.1,
scipy 1.13.1, numpy 2.0.2, pandas 2.3.3, neo4j Python driver 5.28.4, Neo4j server
2026.05.0.

## End-to-end verification

Notebooks 01-05 were run in full, in order, via the exact command above, against
a live Neo4j instance loaded with the complete CERT r6.2 graph. Output: 283,519
rows / 75 windows (notebook 01); 1,056 users flagged at Layer 1, Mahalanobis
threshold 37.44 (notebook 03); graph-confirmed population 293, full-system
recall 4/6 -- CDE1846, CMP2946, MBG3183, PLJ1771 (notebook 05); routing
confirmed load-bearing (CDE1846 and PLJ1771 are lost if adaptive-baseline
routing is disabled). All match the manuscript's Tables 4-11. This closes the
gap between the scratch-script validation the protocol was originally derived
from and actual notebook execution (checkpoint loading, cell ordering, Neo4j
round-trips included).

## What changed numerically, and what didn't

The full-system recall (4/6, CDE1846/CMP2946/MBG3183/PLJ1771) and the identity of
which mechanism (Layer 1 vs. relational graph) recovers which Answer Set account are
**unchanged** from the pre-protocol numbers. Population sizes, several baseline
comparisons (notably IF+NSGA-II), and some ablation-table rows did change -- see the
manuscript's Tables 4-11 for the current, P*-consistent values, which are what this
protocol reproduces.

## Known, tested, and left as-is

- **Config C (DBSCAN standalone) in the architecture ablation**: its recall under P*
  (0.33) differs from an earlier reported value (0.17) entirely because of the `eps`
  value itself (0.3672 vs. the old 0.39) -- confirmed by rerunning that one
  configuration at `eps=0.39` with every other P* change held fixed, which exactly
  reproduces the 0.17/1-true-positive result. Not a data or protocol artifact.
- **G5(paper)/code-G6's PC-ownership determination** (`Q_OWNER` in
  `graph_inspection.py`) computes majority ownership over the *entire* dataset, with
  no cutoff relative to the week being tested -- a non-causal design, structurally
  similar to the adaptive-baseline leak fixed elsewhere in this pipeline. Tested
  against all 165 of G5's matched accounts with a causally-restricted (prior-weeks-
  only) alternative: 161/165 accounts are unaffected, and the 4 that do change are
  not Answer Set accounts -- CDE1846 and PLJ1771 specifically are unaffected in every
  tested week. Left as a known, quantified limitation rather than patched, since
  patching would need its own re-validation pass; revisit before treating `Q_OWNER`
  as causal in any future extension of this pipeline.
- **Sampling-offset sensitivity**: the label-free parameter derivation samples every
  5th week starting from index 0; the other 4 possible starting offsets (1-4) give
  slightly different `eps`/`tau` and, in 2 of those 4 cases, a full-system recall of
  3/6 instead of 4/6 (Layer 1 then misses CMP2946, which no graph query recovers on
  its own). Offset 0 is not an outlier in either direction within that range. Reported
  as a property of the derivation procedure, not corrected for.
