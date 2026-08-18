"""Domain models for statistical evidence.

Continuous-improvement methodology (root_cause/) and statistical methods
(this package) are peers, not a hierarchy — see module docstring in
`method_selection.py`. Nothing here privileges one over the other; both
are tools `method_selection.select_method` can choose between.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..exceptions import ValidationError
from ..numbers import require_nonblank_str, require_number


class ReliabilityConclusion(str, Enum):
    """Whether a measured difference is both statistically distinguishable
    from noise AND large enough to be worth acting on — two separate
    questions, both required (spec: "effect size before significance")."""

    RELIABLE_AND_MEANINGFUL = "reliable_and_meaningful"
    RELIABLE_BUT_TOO_SMALL = "reliable_but_too_small"
    NOT_RELIABLE = "not_reliable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class DescriptiveStats:
    n: int
    mean: float
    median: float
    stdev: float | None
    mad: float
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if not isinstance(self.n, int) or isinstance(self.n, bool) or self.n < 1:
            raise ValidationError("descriptive_stats.n must be a positive int")
        for name in ("mean", "median", "mad", "minimum", "maximum"):
            require_number(getattr(self, name), name=f"descriptive_stats.{name}", allow_negative=True)
        if self.stdev is not None:
            require_number(self.stdev, name="descriptive_stats.stdev", minimum=0.0)


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    point_estimate: float
    lower: float
    upper: float
    confidence_level: float
    method: str
    seed: int
    n_resamples: int

    def __post_init__(self) -> None:
        require_number(self.point_estimate, name="ci.point_estimate", allow_negative=True)
        require_number(self.lower, name="ci.lower", allow_negative=True)
        require_number(self.upper, name="ci.upper", allow_negative=True)
        if self.lower > self.upper:
            raise ValidationError("ci.lower must be <= ci.upper")
        require_number(self.confidence_level, name="ci.confidence_level", minimum=0.0, maximum=1.0)
        object.__setattr__(self, "method", require_nonblank_str(self.method, name="ci.method"))
        if self.n_resamples < 1:
            raise ValidationError("ci.n_resamples must be >= 1")

    @property
    def excludes_zero(self) -> bool:
        return self.lower > 0.0 or self.upper < 0.0


@dataclass(frozen=True, slots=True)
class PermutationTestResult:
    observed_difference: float
    p_value: float
    n_permutations: int
    seed: int
    exact: bool

    def __post_init__(self) -> None:
        require_number(self.observed_difference, name="permutation.observed_difference", allow_negative=True)
        require_number(self.p_value, name="permutation.p_value", minimum=0.0, maximum=1.0)
        if self.n_permutations < 1:
            raise ValidationError("permutation.n_permutations must be >= 1")


@dataclass(frozen=True, slots=True)
class EffectSize:
    cohens_d: float
    baseline_mean: float
    candidate_mean: float
    absolute_difference: float
    relative_difference: float | None

    def __post_init__(self) -> None:
        require_number(self.cohens_d, name="effect_size.cohens_d", allow_negative=True)
        require_number(self.baseline_mean, name="effect_size.baseline_mean", allow_negative=True)
        require_number(self.candidate_mean, name="effect_size.candidate_mean", allow_negative=True)
        require_number(self.absolute_difference, name="effect_size.absolute_difference", allow_negative=True)


@dataclass(frozen=True, slots=True)
class StatisticalConclusion:
    reliability: ReliabilityConclusion
    plain_summary: str
    baseline_stats: DescriptiveStats | None
    candidate_stats: DescriptiveStats | None
    effect_size: EffectSize | None
    confidence_interval: ConfidenceInterval | None
    permutation_test: PermutationTestResult | None
    minimum_meaningful_delta: float
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.reliability, ReliabilityConclusion):
            raise ValidationError("statistical_conclusion.reliability must be a ReliabilityConclusion")
        object.__setattr__(
            self,
            "plain_summary",
            require_nonblank_str(self.plain_summary, name="statistical_conclusion.plain_summary"),
        )
        object.__setattr__(
            self, "rationale", require_nonblank_str(self.rationale, name="statistical_conclusion.rationale")
        )
