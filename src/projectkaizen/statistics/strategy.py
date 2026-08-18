"""StatisticalStrategy: the one entry point that combines descriptive
stats, a bootstrap confidence interval, a permutation test, and effect
size into a single plain-language conclusion.

Reliability is decided from the bootstrap CI excluding zero, not a raw
p-value against a fixed alpha=0.05 — a CI answers "how big could the real
difference plausibly be", which is what a stopping/acceptance decision
actually needs, and avoids the well-documented pitfalls of p-value-only
significance dogma. The permutation test is still computed and exposed
(useful corroborating evidence, especially for `--full`), just not used as
the sole reliability gate.

Effect size before significance: a reliable difference smaller than
`minimum_meaningful_delta` is `RELIABLE_BUT_TOO_SMALL`, not
`RELIABLE_AND_MEANINGFUL` — statistically real is necessary, not sufficient.
"""

from __future__ import annotations

from ..exceptions import ValidationError
from .bootstrap import bootstrap_diff_ci
from .descriptive import compute_descriptive_stats
from .effect_size import cohens_d
from .models import ReliabilityConclusion, StatisticalConclusion
from .permutation import permutation_test

DEFAULT_SEED = 0


def evaluate_difference(
    baseline: tuple[float, ...],
    candidate: tuple[float, ...],
    *,
    minimum_meaningful_delta: float,
    seed: int = DEFAULT_SEED,
    confidence_level: float = 0.95,
) -> StatisticalConclusion:
    if minimum_meaningful_delta < 0:
        raise ValidationError("minimum_meaningful_delta must be >= 0")

    if len(baseline) < 2 or len(candidate) < 2:
        return StatisticalConclusion(
            reliability=ReliabilityConclusion.INSUFFICIENT_DATA,
            plain_summary="There is not enough data yet to draw a reliable conclusion.",
            baseline_stats=compute_descriptive_stats(baseline) if baseline else None,
            candidate_stats=compute_descriptive_stats(candidate) if candidate else None,
            effect_size=None,
            confidence_interval=None,
            permutation_test=None,
            minimum_meaningful_delta=minimum_meaningful_delta,
            rationale="each sample needs at least 2 measurements for a bootstrap/permutation estimate",
        )

    baseline_stats = compute_descriptive_stats(baseline)
    candidate_stats = compute_descriptive_stats(candidate)
    effect = cohens_d(baseline, candidate)
    ci = bootstrap_diff_ci(baseline, candidate, seed=seed, confidence_level=confidence_level)
    perm = permutation_test(baseline, candidate, seed=seed)

    reliable = ci.excludes_zero
    meaningful = abs(effect.absolute_difference) >= minimum_meaningful_delta

    if not reliable:
        reliability = ReliabilityConclusion.NOT_RELIABLE
        summary = (
            "The available data does not show a reliable difference - it could just be normal run-to-run variation."
        )
        rationale = (
            f"{int(confidence_level * 100)}% CI for the difference [{ci.lower:.4g}, {ci.upper:.4g}] includes zero"
        )
    elif not meaningful:
        reliability = ReliabilityConclusion.RELIABLE_BUT_TOO_SMALL
        summary = "The measured difference is too small to justify changing this."
        rationale = (
            f"difference is reliable (CI [{ci.lower:.4g}, {ci.upper:.4g}] excludes zero) but "
            f"|{effect.absolute_difference:.4g}| < minimum meaningful delta {minimum_meaningful_delta:.4g}"
        )
    else:
        reliability = ReliabilityConclusion.RELIABLE_AND_MEANINGFUL
        direction = "increase" if effect.absolute_difference > 0 else "decrease"
        summary = f"This {direction} is larger than normal run-to-run variation, and it's big enough to matter."
        rationale = (
            f"difference is reliable (CI [{ci.lower:.4g}, {ci.upper:.4g}] excludes zero) and "
            f"|{effect.absolute_difference:.4g}| >= minimum meaningful delta {minimum_meaningful_delta:.4g}"
        )

    return StatisticalConclusion(
        reliability=reliability,
        plain_summary=summary,
        baseline_stats=baseline_stats,
        candidate_stats=candidate_stats,
        effect_size=effect,
        confidence_interval=ci,
        permutation_test=perm,
        minimum_meaningful_delta=minimum_meaningful_delta,
        rationale=rationale,
    )
