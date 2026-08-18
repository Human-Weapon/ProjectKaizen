"""Permutation test for a two-sample mean difference.

Nonparametric by design: no assumption about the underlying distribution
(unlike a t-test), which avoids needing to implement and validate a
t-distribution CDF from scratch — a real correctness risk for a
hand-rolled implementation. Exact enumeration is used when the number of
distinct splits is small enough to be tractable; otherwise a seeded Monte
Carlo estimate (same reproducibility contract as bootstrap.py).
"""

from __future__ import annotations

import itertools
import math
import random
import statistics as stdlib_statistics

from ..exceptions import ValidationError
from ._validate import require_finite_values
from .models import PermutationTestResult

#: exact enumeration is used when C(n_total, n_baseline) is at most this
_EXACT_THRESHOLD = 20_000
DEFAULT_N_PERMUTATIONS = 10_000


def _mean_diff(baseline: tuple[float, ...], candidate: tuple[float, ...]) -> float:
    return stdlib_statistics.fmean(candidate) - stdlib_statistics.fmean(baseline)


def permutation_test(
    baseline: tuple[float, ...],
    candidate: tuple[float, ...],
    *,
    seed: int,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> PermutationTestResult:
    if len(baseline) < 2 or len(candidate) < 2:
        raise ValidationError("permutation test requires at least 2 values per sample")
    require_finite_values(baseline, name="baseline")
    require_finite_values(candidate, name="candidate")

    observed = _mean_diff(baseline, candidate)
    combined = list(baseline) + list(candidate)
    n_baseline = len(baseline)
    n_total = len(combined)
    n_splits = math.comb(n_total, n_baseline)

    if n_splits <= _EXACT_THRESHOLD:
        extreme_count = 0
        for baseline_idx in itertools.combinations(range(n_total), n_baseline):
            baseline_idx_set = set(baseline_idx)
            split_baseline = [combined[i] for i in range(n_total) if i in baseline_idx_set]
            split_candidate = [combined[i] for i in range(n_total) if i not in baseline_idx_set]
            diff = stdlib_statistics.fmean(split_candidate) - stdlib_statistics.fmean(split_baseline)
            if abs(diff) >= abs(observed) - 1e-12:
                extreme_count += 1
        p_value = extreme_count / n_splits
        return PermutationTestResult(
            observed_difference=observed, p_value=p_value, n_permutations=n_splits, seed=seed, exact=True
        )

    rng = random.Random(seed)  # noqa: S311 - statistical resampling, not cryptographic use
    extreme_count = 0
    working = list(combined)
    for _ in range(n_permutations):
        rng.shuffle(working)
        split_baseline = working[:n_baseline]
        split_candidate = working[n_baseline:]
        diff = stdlib_statistics.fmean(split_candidate) - stdlib_statistics.fmean(split_baseline)
        if abs(diff) >= abs(observed) - 1e-12:
            extreme_count += 1
    p_value = extreme_count / n_permutations
    return PermutationTestResult(
        observed_difference=observed, p_value=p_value, n_permutations=n_permutations, seed=seed, exact=False
    )
