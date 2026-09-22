"""Evaluation against the CERT r6.2 Answer Set. Only call from evaluation notebooks --
never let these metrics leak into Layer 1/2 pipeline logic."""

from scipy.stats import hypergeom


def evaluate_against_answerset(flagged_set, malicious_users, label):
    TP = flagged_set & malicious_users
    FN = malicious_users - flagged_set
    FP = flagged_set - malicious_users
    p = len(TP) / len(flagged_set) if flagged_set else 0
    r = len(TP) / len(malicious_users)
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
    return {
        'Label': label, 'TP': len(TP), 'FN': len(FN), 'FP': len(FP),
        'Recall': round(r, 4), 'Precision': round(p, 6), 'F1': round(f1, 6),
        'TP_list': sorted(TP), 'FN_list': sorted(FN),
    }


def enrichment(tp, pop, n_answer, population_size):
    """Enrichment (Eq. 12): precision of the flagged set / population base rate,
    i.e. (TP/|S|) / (|A|/|U|). `pop` is |S|, the flagged-set size."""
    if pop == 0 or tp == 0:
        return 0.0
    return (tp / pop) / (n_answer / population_size)


def enrichment_pvalue(tp, pop, n_answer, population_size):
    """Hypergeometric one-sided p-value for observing >= tp hits."""
    return hypergeom.sf(tp - 1, population_size, n_answer, pop)
