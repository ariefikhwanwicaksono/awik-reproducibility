"""Global constants: Answer Set, clustering parameters, batch size.

Parameter derivations (k, eps, minPts, Mahalanobis threshold) are label-free
and documented in notebooks/02_layer1_justification.ipynb and the accompanying manuscript.
"""

ANSWER_SET = {
    'ACM2278': {
        'scenario': 1, 'role': 'ATTACKER',
        'description': 'After-hours logon + USB + upload to wikileaks.org',
        'active_weeks': [(2010, 33), (2010, 34)],
    },
    'CMP2946': {
        'scenario': 2, 'role': 'ATTACKER',
        'description': 'Job search + USB exfiltration to competitor',
        'active_weeks': [(2011, w) for w in range(5, 14)],
    },
    'PLJ1771': {
        'scenario': 3, 'role': 'ATTACKER',
        'description': 'Lateral movement via keylogger -- primary attacker',
        'active_weeks': [(2010, 32)],
    },
    'HIS1706': {
        'scenario': 3, 'role': 'HIJACKED_ACCOUNT',
        'description': 'Supervisor account hijacked by PLJ1771 for mass email',
        'active_weeks': [(2010, 32)],
    },
    'CDE1846': {
        'scenario': 4, 'role': 'ATTACKER',
        'description': 'Low-and-slow -- logs into others\' machines, emails sensitive files',
        'active_weeks': [(2011, w) for w in range(8, 18)],
    },
    'MBG3183': {
        'scenario': 5, 'role': 'ATTACKER',
        'description': 'Uploads documents to Dropbox after termination',
        'active_weeks': [(2010, 41)],
    },
}
MALICIOUS_USERS = set(ANSWER_SET.keys())

# k for K-Means (Layer 1). Local-max stable across 12/15 sampled weeks (ISO week-year
# indexing, 75 total windows -- see features.py's docstring for why 75, not 76).
DEFAULT_K = 4
# DBSCAN eps. Median within-cluster k-distance knee, label-free (15 sampled weeks,
# IQR [0.3554, 0.4308]).
DEFAULT_EPS = 0.3672
# DBSCAN min_samples = 2 * PCA dims (Sander et al. 1998).
DEFAULT_MINPTS = 4

# Mahalanobis^2 flagging threshold. Empirical, fixed: median of the 99th-percentile
# within-cluster Mahalanobis^2 across 57 cluster-weeks, label-free (IQR [28.26, 98.28]).
# NOT the theoretical chi2.ppf(0.99, df=2)=9.21 -- rejected because Shapiro-Wilk
# rejects PC1 normality in 94.7% of cluster-weeks. See the accompanying manuscript.
DEFAULT_MAH_THRESH = 37.44

# Neo4j batch size (avoids the ~716MB per-transaction OOM limit).
BATCH_SIZE = 50
