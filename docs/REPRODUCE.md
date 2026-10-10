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

## Causal PC ownership (G5(paper)/code-G6)

`Q_OWNER` in `graph_inspection.py` previously computed majority PC ownership
(>=50% of historical logons) once, globally, over the *entire* dataset, with no
cutoff relative to the week being tested -- a non-causal design, structurally
similar to the adaptive-baseline leak fixed elsewhere in this pipeline for
R2-3. A causally-restricted (prior-weeks-only) alternative was tested against
all 165 of G5's matched accounts: 161/165 accounts were unaffected, and the 4
that changed were not Answer Set accounts (CDE1846 and PLJ1771 specifically
were unaffected in every tested week). Following Reviewer 2's request (R2-3),
**the causal rule is now the default**, not a sensitivity check: `Q_OWNER`
takes `$year`/`$week` parameters and is queried once per distinct ISO week
present in the surge population (`fetch_owner_of_by_week`), using only logons
strictly before that week's start.

Verified by running notebooks 04-05 end-to-end against a live Neo4j instance
loaded with the complete CERT r6.2 graph (4,000 User nodes, confirmed before
running):

- `|G5(paper)|` matches: 165 -> **178** (7.5x enrichment, p=0.026) -- not a
  simple reduction, see below
- `|Gc|` (graph-confirmed, union G1-G5, "Layer 2" in Table 5): 293 -> **300**
  (4.4x, p=0.069)
- Full system `|L1 u Gc|`: 1,176 -> **1,182** (2.3x, p=0.067)
- Full-system recall: unchanged at 4/6 (CMP2946, MBG3183 via Layer 1;
  PLJ1771, CDE1846 via G5)
- Precision 4/1,182 = 0.34%; FPR 29.5%; specificity 70.5%; number-needed-to-
  investigate 295.5; Layer 2 precision 2/300 = 0.67% (Layer 1 unchanged at
  2/1,056 = 0.19%)
- Table 6 (flagged population by mechanism), the three rows that move:
  Spatial+Graph 41 -> **42**, Spatial-only 883 -> **882**, Graph-only 99 ->
  **105** (routing pool 160 and the other four rows are unaffected); see the
  account-level reconciliation below for why the net totals move by less
  than the raw G5 change.
- This causal fix only touches `src/awik/graph_inspection.py`'s G5(paper)/
  code-G6 path on the CERT r6.2 pipeline; the separate r5.2 comparison (not
  part of this repo -- computed outside it entirely) is structurally
  unaffected, since it never calls this code.

A prior sensitivity check (`fig3_validation/round8/item11_causal_owner_all165.py`)
only re-verified whether the original 165 G5 matches survive a causal
re-check -- structurally a one-directional filter that can only remove
accounts, never discover new ones, since it starts from the non-causal
result and filters it. A true end-to-end regeneration (this fix) can also
surface accounts that never matched non-causally at all. Diffing the two
match sets directly: 163/165 of the original matches survive (only
`MTS0465` and `TZY3133` drop, not the 4 the narrower test implied), and 15
new accounts appear (`BAL2366, BHE1709, DNV1964, FPV3755, HET0359, HLC1172,
ISR1364, JBB0847, JON0788, NNF3968, RDA3381, REB0123, SGC2111, SLM1119,
YHB2355`). All 15 new accounts' earliest G6 evidence event falls between
2010-01-11 and 2010-01-22 -- the first ~3 ISO weeks of the dataset, where a
causal, prior-weeks-only ownership estimate has almost no history to work
from and a PC used by just two people trivially crosses the 50% majority
threshold. This is an inherent cold-start property of a strictly causal
estimator, not a bug (the type-mismatch bug that caused an initial all-zero
result, `datetime` vs. `localdatetime` on a timezone-naive property, was
caught and fixed before this result was produced).

## Full parameter reference

Everything needed to regenerate this protocol's numbers from a fresh clone, in
one place (all label-free except where noted; derivations are in
`notebooks/02_layer1_justification.ipynb` and `src/awik/config.py`):

| Component | Value | Source |
|---|---|---|
| PCA | 2 components, `random_state=42` | `src/awik/layer1.py` |
| K-Means (Layer 1 macro-role partition) | `k=4`, `random_state=42` | `config.DEFAULT_K` |
| DBSCAN (Layer 1 within-cluster) | `eps=0.3672`, `minPts=4` (`=2*PCA dims`, Sander et al. 1998) | `config.DEFAULT_EPS`, `config.DEFAULT_MINPTS` |
| Mahalanobis² flagging threshold | `tau=37.44` (empirical; chi2.ppf(0.99, df=2)=9.21 rejected -- Shapiro-Wilk rejects PC1 normality in 94.7% of cluster-weeks) | `config.DEFAULT_MAH_THRESH` |
| Adaptive baseline (surge detection) | causal/expanding window, strictly prior weeks only (`.expanding().shift(1)`); a channel surges when `delta > expanding_mean + 2*expanding_std`, across 3 channels (after-hours logon, USB, email size); email channel additionally gated on >=8 prior observations | `src/awik/adaptive_baseline.py:compute_surge_signals` |
| Targeting (routing-pool inclusion rule) | union of persistence (surged in >= `k_persist` distinct weeks, `k_persist` derived per-dataset from a Bonferroni-style expected-false-positive count, not a fixed constant), co-occurrence (>=2 of the 3 channels surge together in >= `k_cooccur=2` weeks), and burst (all 3 channels surge together in >= `k_burst=3`... i.e. `max_cooccur>=3`, meaning in at least one week) | `src/awik/adaptive_baseline.py:target_users` |
| Routing pool size | empirical output, not a tunable input: **160/4,000 (4.0%)** under P* | notebook 04 |
| G1-G5 Cypher queries | `docs/g1_g6_queries.cypher` (verbatim from `src/awik/graph_inspection.py`); no per-batch `LIMIT`; PC ownership (G5(paper)/code-G6) is causal, see above | `src/awik/graph_inspection.py` |
| Seeds | `42` everywhere a seed is used (`PCA`, `KMeans`), no exceptions; one deliberate sweep (`SEEDS=[0,1,7,21,42,100,123]`) tests sensitivity to this choice | `docs/reproducibility.md` |

## Section 4.5: G5 applied to the full population, without surge gating

`scripts/sect4_5_full_population_g5.py` reproduces the manuscript's "G5 matches
N accounts (X%)" figure applied across every (user, week) pair in the full
account-week universe (283,519 pairs, all 4,000 users, all 75 weeks), not just
the surge-gated population G5 normally draws from. It only needs notebook 01's
checkpoint (`data/interim/01_df_master.csv`) and a live Neo4j instance, so it
can be run independently of notebooks 02-08:

```bash
export NEO4J_PASSWORD=yourpassword
python scripts/sect4_5_full_population_g5.py
```

Under causal ownership: **203/4,000 accounts (5.08%)**, up from the non-causal
baseline of 183/4,000 (4.58%) -- the same cold-start-driven increase described
above, at the full-population scale. Answer Set true positives unchanged (2/6:
CDE1846, PLJ1771).

## Known, tested, and left as-is

- **Config C (DBSCAN standalone) in the architecture ablation**: its recall under P*
  (0.33) differs from an earlier reported value (0.17) entirely because of the `eps`
  value itself (0.3672 vs. the old 0.39) -- confirmed by rerunning that one
  configuration at `eps=0.39` with every other P* change held fixed, which exactly
  reproduces the 0.17/1-true-positive result. Not a data or protocol artifact.
- **Sampling-offset sensitivity**: the label-free parameter derivation samples every
  5th week starting from index 0; the other 4 possible starting offsets (1-4) give
  slightly different `eps`/`tau` and, in 2 of those 4 cases, a full-system recall of
  3/6 instead of 4/6 (Layer 1 then misses CMP2946, which no graph query recovers on
  its own). Offset 0 is not an outlier in either direction within that range. Reported
  as a property of the derivation procedure, not corrected for.
