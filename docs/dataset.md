# Dataset: obtaining and loading CERT r6.2

Neither the raw activity logs nor the answer-key files are included in this repo --
`data/raw/` is gitignored, and the license (ExactData, "All Rights Reserved" --
`license-exactdata.txt` in the raw distribution) does not permit redistribution
regardless of size. Nothing here should ever be committed to git.

## 1. Obtain the data

Official source: CMU CERT Insider Threat Test Dataset, release r6.2, from the
[CMU KiltHub collection](https://kilthub.cmu.edu/articles/dataset/Insider_Threat_Test_Dataset/12841247).
The r6.2 release is roughly 93GB, almost entirely `http.csv` (~90GB) and
`email.csv` (~8GB) -- far past what GitHub or Git LFS can practically hold
(GitHub hard-blocks any single file over 100MB; LFS free tier is 1GB/month).
There is no way around this other than not versioning the data at all, which is
also what the license requires.

## 2. Local layout expected by this repo

```
data/raw/
├── cert_r6.2/
│   ├── logon.csv
│   ├── device.csv
│   ├── file.csv
│   ├── email.csv
│   ├── http.csv
│   ├── psychometric.csv
│   ├── decoy_file.csv
│   ├── LDAP/
│   ├── readme.txt
│   └── license-exactdata.txt
└── answer/
    ├── insiders.csv          # master ground-truth file
    ├── scenarios.txt
    ├── readme.txt
    ├── license.txt
    ├── r6.2-1.csv ... r6.2-5.csv   # per-scenario incident observables
    └── r6.1-*, r5.*, r4.*, r3.*, r2.csv   # earlier releases, kept for reference
```

## 3. Loading into Neo4j

The pipeline (`src/awik/*`, all notebooks) assumes Neo4j is already populated --
none of the notebooks do the CSV -> graph load themselves. `docs/neo4j_load.cypher`
has the `LOAD CSV` statements for the five activity domains
(`LOGGED_ON_TO`, `CONNECTED_DEVICE`, `ACCESSED_FILE`, `SENT_EMAIL`, `VISITED_URL`)
plus the psychometric (OCEAN) profile merge onto `User` nodes.

Steps:
1. Copy the CSVs into Neo4j's `import/` directory (`LOAD CSV ... FROM "file:///..."`
   resolves relative to it).
2. `User` nodes must exist *before* running the five activity-load blocks --
   they `MATCH` rather than `MERGE` a user. The psychometric block does `MERGE`,
   so load order matters: run `psychometric.csv` first, or create `User` nodes
   from another source before running the rest.
3. **Gap, not yet resolved here:** `src/awik/features.py`'s DFS query reads
   `u.role` and `u.department` per user, but nothing in `neo4j_load.cypher` sets
   those properties -- they must come from the `LDAP/` directory in the raw
   dataset (per-month employee records), which has no corresponding `LOAD CSV`
   block in the script as found. On the AWIK development machine's live Neo4j
   instance, `role`/`department` ARE already present on `User` nodes (verified
   2026-09-01: e.g. `NFP2441` has `role='ITAdmin'`, `department='5 - Security'`)
   -- so this step was done, just not by anything captured in this repo. Write
   (or recover) that loading step before running notebook 01 on a fresh Neo4j
   instance; don't assume it already exists.

## 5. Derived checkpoints (`data/interim/`)

Notebooks 01-08 write intermediate CSV/JSON checkpoints to `data/interim/`
(`src/awik/io.py`) so each notebook can be rerun independently instead of
assuming one shared kernel session. Several of these -- `01_df_master.csv`
(the full weekly feature matrix) and `dfs_checkpoint.csv` in particular -- are
large, non-trivial derivatives of the licensed CERT r6.2 data. `data/interim/`
is entirely gitignored for the same licensing reason as `data/raw/` (see
`.gitignore`'s comment there); nothing in it should ever be force-added to git.
If a checkpoint is missing, regenerate it by rerunning the notebook that
produces it (README has the full notebook -> checkpoint table) -- don't try to
obtain or share these files any other way.

## 4. Answer-key data (`data/raw/answer/`)

`insiders.csv` is the master list of true positives (release, scenario number,
per-incident observable file, username, start/end time) -- see its `readme.txt`
for the exact schema. Per-incident detail files are *not* well-formed CSV: rows
are variable-length with the data type interleaved as the first column. AWIK's
own `ANSWER_SET` (`src/awik/config.py`) is a hand-curated 6-actor subset of this
for r6.2 specifically, not derived programmatically from these files at pipeline
run time -- these are kept for reference and independent verification, not
because the code reads them directly.
