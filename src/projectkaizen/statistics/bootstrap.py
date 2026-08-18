"""Bootstrap confidence intervals (percentile method).

This is the one place in ProjectKaizen that deliberately uses randomness —
resampling is what a bootstrap *is*. It is never hidden: every function
here requires an explicit `seed` (no default that silently reads system
entropy), so the same seed always reproduces the same interval — the
determinism principle applied to a domain where pure determinism isn't the
right tool would be dishonest; explicit, reproducible randomness is.
"""

from __future__ import annotations

import random
import statistics as stdlib_statistics

from ..exceptions import ValidationError
from ._validate import require_finite_values
from .models import ConfidenceInterval

DEFAULT_N_RESAMPLES = 2000


def _percentile(sorted_values: list[float], q: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = q * (len(sorted_values) - 1)
    lower_idx = int(idx)
    upper_idx = min(lower_idx + 1, len(sorted_values) - 1)
    frac = idx - lower_idx
    return sorted_values[lower_idx] + (sorted_values[upper_idx] - sorted_values[lower_idx]) * frac


def bootstrap_mean_ci(
    values: tuple[float, ...],
    *,
    seed: int,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    if len(values) < 2:
        raise ValidationError("bootstrap requires at least 2 values")
    require_finite_values(values, name="values")
    if not (0.0 < confidence_level < 1.0):
        raise ValidationError("confidence_level must be strictly between 0 and 1")
    rng = random.Random(seed)  # noqa: S311 - statistical resampling, not cryptographic use
    n = len(values)
    resample_means = []
    for _ in range(n_resamples):
        resample = [values[rng.randrange(n)] for _ in range(n)]
        resample_means.append(stdlib_statistics.fmean(resample))
    resample_means.sort()
    alpha = 1.0 - confidence_level
    lower = _percentile(resample_means, alpha / 2)
    upper = _percentile(resample_means, 1.0 - alpha / 2)
    return ConfidenceInterval(
        point_estimate=stdlib_statistics.fmean(values),
        lower=lower,
        upper=upper,
        confidence_level=confidence_level,
        method="bootstrap_percentile",
        seed=seed,
        n_resamples=n_resamples,
    )


def bootstrap_diff_ci(
    baseline: tuple[float, ...],
    candidate: tuple[float, ...],
    *,
    seed: int,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """CI for candidate_mean - baseline_mean."""
    if len(baseline) < 2 or len(candidate) < 2:
        raise ValidationError("bootstrap requires at least 2 values per sample")
    require_finite_values(baseline, name="baseline")
    require_finite_values(candidate, name="candidate")
    if not (0.0 < confidence_level < 1.0):
        raise ValidationError("confidence_level must be strictly between 0 and 1")
    rng = random.Random(seed)  # noqa: S311 - statistical resampling, not cryptographic use
    nb, nc = len(baseline), len(candidate)
    diffs = []
    for _ in range(n_resamples):
        b_resample = [baseline[rng.randrange(nb)] for _ in range(nb)]
        c_resample = [candidate[rng.randrange(nc)] for _ in range(nc)]
        diffs.append(stdlib_statistics.fmean(c_resample) - stdlib_statistics.fmean(b_resample))
    diffs.sort()
    alpha = 1.0 - confidence_level
    lower = _percentile(diffs, alpha / 2)
    upper = _percentile(diffs, 1.0 - alpha / 2)
    point = stdlib_statistics.fmean(candidate) - stdlib_statistics.fmean(baseline)
    return ConfidenceInterval(
        point_estimate=point,
        lower=lower,
        upper=upper,
        confidence_level=confidence_level,
        method="bootstrap_percentile_diff",
        seed=seed,
        n_resamples=n_resamples,
    )
