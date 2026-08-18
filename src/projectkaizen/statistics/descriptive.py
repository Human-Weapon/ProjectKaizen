"""Robust descriptive statistics. stdlib `statistics` module only."""

from __future__ import annotations

import statistics as stdlib_statistics

from ..exceptions import ValidationError
from ._validate import require_finite_values
from .models import DescriptiveStats


def compute_descriptive_stats(values: tuple[float, ...]) -> DescriptiveStats:
    if not values:
        raise ValidationError("values must not be empty")
    require_finite_values(values, name="values")
    n = len(values)
    mean = stdlib_statistics.fmean(values)
    median = stdlib_statistics.median(values)
    stdev = stdlib_statistics.stdev(values) if n >= 2 else None
    mad = stdlib_statistics.median([abs(v - median) for v in values])
    return DescriptiveStats(
        n=n, mean=mean, median=median, stdev=stdev, mad=mad, minimum=min(values), maximum=max(values)
    )
