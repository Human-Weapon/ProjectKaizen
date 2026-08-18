"""Statistical evidence methods — a peer to root_cause/, not a fallback.

Implements only what has real product value and can be validated
correctly: descriptive stats, a bootstrap confidence interval, a
permutation test, and Cohen's d effect size, combined by
`evaluate_difference` into one plain-language conclusion. Deliberately
does not implement every technique named as a *possibility* in the build
spec (CUSUM/EWMA, change-point detection, causal inference, sequential
analysis) — each of those needs real design and validation work, not a
half-correct implementation nobody checked.
"""

from __future__ import annotations

from .bootstrap import bootstrap_diff_ci, bootstrap_mean_ci
from .descriptive import compute_descriptive_stats
from .effect_size import cohens_d
from .models import (
    ConfidenceInterval,
    DescriptiveStats,
    EffectSize,
    PermutationTestResult,
    ReliabilityConclusion,
    StatisticalConclusion,
)
from .permutation import permutation_test
from .strategy import evaluate_difference

__all__ = [
    "ConfidenceInterval",
    "DescriptiveStats",
    "EffectSize",
    "PermutationTestResult",
    "ReliabilityConclusion",
    "StatisticalConclusion",
    "bootstrap_diff_ci",
    "bootstrap_mean_ci",
    "cohens_d",
    "compute_descriptive_stats",
    "evaluate_difference",
    "permutation_test",
]
