"""Effect size: is the difference big, independent of whether it's "real"."""

from __future__ import annotations

import math
import statistics as stdlib_statistics

from ..exceptions import ValidationError
from ._validate import require_finite_values
from .models import EffectSize


def cohens_d(baseline: tuple[float, ...], candidate: tuple[float, ...]) -> EffectSize:
    if len(baseline) < 2 or len(candidate) < 2:
        raise ValidationError("cohens_d requires at least 2 values per sample")
    require_finite_values(baseline, name="baseline")
    require_finite_values(candidate, name="candidate")

    baseline_mean = stdlib_statistics.fmean(baseline)
    candidate_mean = stdlib_statistics.fmean(candidate)
    absolute_difference = candidate_mean - baseline_mean

    n1, n2 = len(baseline), len(candidate)
    s1 = stdlib_statistics.stdev(baseline)
    s2 = stdlib_statistics.stdev(candidate)
    pooled_variance = ((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2)
    pooled_stdev = math.sqrt(pooled_variance)

    d = absolute_difference / pooled_stdev if pooled_stdev > 0 else 0.0
    relative_difference = absolute_difference / abs(baseline_mean) if baseline_mean != 0 else None

    return EffectSize(
        cohens_d=d,
        baseline_mean=baseline_mean,
        candidate_mean=candidate_mean,
        absolute_difference=absolute_difference,
        relative_difference=relative_difference,
    )
