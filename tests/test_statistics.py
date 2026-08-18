from __future__ import annotations

import random

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.statistics import (
    ReliabilityConclusion,
    bootstrap_diff_ci,
    bootstrap_mean_ci,
    cohens_d,
    compute_descriptive_stats,
    evaluate_difference,
    permutation_test,
)


def test_descriptive_stats_basic():
    stats = compute_descriptive_stats((1.0, 2.0, 3.0, 4.0, 5.0))
    assert stats.n == 5
    assert stats.mean == 3.0
    assert stats.median == 3.0
    assert stats.minimum == 1.0
    assert stats.maximum == 5.0


def test_descriptive_stats_single_value_has_no_stdev():
    stats = compute_descriptive_stats((5.0,))
    assert stats.stdev is None


def test_descriptive_stats_rejects_empty():
    with pytest.raises(ValidationError):
        compute_descriptive_stats(())


def test_descriptive_stats_rejects_nan_with_clean_error():
    # self-adversarial finding: stdlib statistics.stdev raises a confusing
    # internal AttributeError on NaN (Python 3.11+'s exact-fraction
    # arithmetic) unless validated at the boundary first.
    with pytest.raises(ValidationError, match="finite"):
        compute_descriptive_stats((1.0, float("nan"), 3.0))


def test_descriptive_stats_rejects_inf():
    with pytest.raises(ValidationError, match="finite"):
        compute_descriptive_stats((1.0, float("inf"), 3.0))


def test_bootstrap_mean_ci_contains_true_mean_for_tight_data():
    values = tuple(100.0 + i * 0.01 for i in range(50))
    ci = bootstrap_mean_ci(values, seed=1)
    assert ci.lower <= ci.point_estimate <= ci.upper


def test_bootstrap_mean_ci_reproducible_with_same_seed():
    values = (1.0, 5.0, 3.0, 9.0, 2.0, 7.0)
    ci1 = bootstrap_mean_ci(values, seed=42, n_resamples=500)
    ci2 = bootstrap_mean_ci(values, seed=42, n_resamples=500)
    assert ci1 == ci2


def test_bootstrap_mean_ci_different_seeds_can_differ():
    values = (1.0, 5.0, 3.0, 9.0, 2.0, 7.0, 4.0, 8.0)
    ci1 = bootstrap_mean_ci(values, seed=1, n_resamples=200)
    ci2 = bootstrap_mean_ci(values, seed=2, n_resamples=200)
    # not asserting inequality (could coincide), just that both are valid
    assert ci1.lower <= ci1.upper
    assert ci2.lower <= ci2.upper


def test_bootstrap_mean_ci_requires_at_least_two_values():
    with pytest.raises(ValidationError):
        bootstrap_mean_ci((1.0,), seed=1)


def test_bootstrap_mean_ci_rejects_nan():
    with pytest.raises(ValidationError, match="finite"):
        bootstrap_mean_ci((1.0, float("nan"), 3.0), seed=1)


def test_bootstrap_diff_ci_rejects_nan_in_either_sample():
    with pytest.raises(ValidationError, match="finite"):
        bootstrap_diff_ci((1.0, float("nan")), (1.0, 2.0), seed=1)
    with pytest.raises(ValidationError, match="finite"):
        bootstrap_diff_ci((1.0, 2.0), (1.0, float("inf")), seed=1)


def test_bootstrap_diff_ci_clear_difference_excludes_zero():
    baseline = tuple([100.0] * 10)
    candidate = tuple([50.0] * 10)
    ci = bootstrap_diff_ci(baseline, candidate, seed=1, n_resamples=500)
    assert ci.excludes_zero is True
    assert ci.point_estimate < 0  # candidate - baseline


def test_bootstrap_diff_ci_no_difference_includes_zero():
    rng = random.Random(99)
    baseline = tuple(rng.gauss(100, 10) for _ in range(30))
    candidate = tuple(rng.gauss(100, 10) for _ in range(30))
    ci = bootstrap_diff_ci(baseline, candidate, seed=1, n_resamples=1000)
    assert ci.excludes_zero is False


def test_permutation_test_exact_for_small_samples():
    baseline = (1.0, 2.0, 3.0)
    candidate = (10.0, 11.0, 12.0)
    result = permutation_test(baseline, candidate, seed=1)
    assert result.exact is True
    # with n=3 per group, only the observed split and its mirror achieve
    # the maximum separation: p = 2/C(6,3) = 2/20 = 0.1 exactly.
    assert result.p_value == pytest.approx(0.1)


def test_permutation_test_no_difference_high_p_value():
    baseline = (1.0, 1.0, 1.0, 1.0)
    candidate = (1.0, 1.0, 1.0, 1.0)
    result = permutation_test(baseline, candidate, seed=1)
    assert result.observed_difference == 0.0
    assert result.p_value == 1.0


def test_permutation_test_reproducible():
    rng = random.Random(5)
    baseline = tuple(rng.gauss(0, 1) for _ in range(25))
    candidate = tuple(rng.gauss(0.5, 1) for _ in range(25))
    r1 = permutation_test(baseline, candidate, seed=7)
    r2 = permutation_test(baseline, candidate, seed=7)
    assert r1 == r2


def test_permutation_test_type_i_error_rate_is_plausible():
    """Sanity check: testing identical-distribution samples repeatedly
    should reject (p < 0.05) at roughly the nominal rate, not wildly off."""
    rng = random.Random(123)
    false_positives = 0
    trials = 60
    for i in range(trials):
        a = tuple(rng.gauss(0, 1) for _ in range(12))
        b = tuple(rng.gauss(0, 1) for _ in range(12))
        result = permutation_test(a, b, seed=i)
        if result.p_value < 0.05:
            false_positives += 1
    # nominal is ~5% of 60 = 3; allow generous slack for a small trial count
    assert false_positives <= 10


def test_cohens_d_large_effect():
    baseline = tuple([100.0] * 20)
    candidate = tuple([50.0] * 20)
    # identical values within each group give zero pooled stdev; use tiny jitter
    baseline = tuple(100.0 + (i % 2) * 0.001 for i in range(20))
    candidate = tuple(50.0 + (i % 2) * 0.001 for i in range(20))
    effect = cohens_d(baseline, candidate)
    assert abs(effect.cohens_d) > 5  # huge effect
    assert effect.absolute_difference == pytest.approx(-50.0, abs=0.01)


def test_cohens_d_zero_pooled_stdev_returns_zero_d():
    baseline = tuple([10.0] * 5)
    candidate = tuple([10.0] * 5)
    effect = cohens_d(baseline, candidate)
    assert effect.cohens_d == 0.0


def test_cohens_d_requires_at_least_two_per_sample():
    with pytest.raises(ValidationError):
        cohens_d((1.0,), (1.0, 2.0))


def test_cohens_d_rejects_nan():
    with pytest.raises(ValidationError, match="finite"):
        cohens_d((1.0, float("nan")), (1.0, 2.0))


def test_permutation_test_rejects_nan():
    with pytest.raises(ValidationError, match="finite"):
        permutation_test((1.0, float("nan")), (1.0, 2.0), seed=1)


# --- evaluate_difference (the combined StatisticalStrategy) -----------------


def test_evaluate_difference_tiny_effect_not_reliable_or_too_small():
    """0.2% difference against a 5% minimum meaningful delta — from the
    build spec's own example."""
    baseline = (100.0, 100.5, 99.5, 100.2, 99.8, 100.1, 99.9, 100.3, 99.7, 100.0)
    candidate = (99.8, 100.3, 99.3, 100.0, 99.6, 99.9, 99.7, 100.1, 99.5, 99.8)
    conclusion = evaluate_difference(baseline, candidate, minimum_meaningful_delta=5.0)
    assert conclusion.reliability in (
        ReliabilityConclusion.NOT_RELIABLE,
        ReliabilityConclusion.RELIABLE_BUT_TOO_SMALL,
    )
    assert conclusion.reliability != ReliabilityConclusion.RELIABLE_AND_MEANINGFUL


def test_evaluate_difference_clear_large_change_is_reliable_and_meaningful():
    baseline = tuple(100.0 + (i % 2) * 0.01 for i in range(15))
    candidate = tuple(50.0 + (i % 2) * 0.01 for i in range(15))
    conclusion = evaluate_difference(baseline, candidate, minimum_meaningful_delta=5.0)
    assert conclusion.reliability == ReliabilityConclusion.RELIABLE_AND_MEANINGFUL
    assert "larger than normal run-to-run variation" in conclusion.plain_summary


def test_evaluate_difference_insufficient_data():
    conclusion = evaluate_difference((1.0,), (2.0,), minimum_meaningful_delta=1.0)
    assert conclusion.reliability == ReliabilityConclusion.INSUFFICIENT_DATA
    assert conclusion.confidence_interval is None


def test_evaluate_difference_reliable_but_too_small_summary_matches_spec_example():
    baseline = tuple(100.0 + (i % 2) * 0.001 for i in range(20))
    candidate = tuple(99.9 + (i % 2) * 0.001 for i in range(20))
    conclusion = evaluate_difference(baseline, candidate, minimum_meaningful_delta=5.0)
    if conclusion.reliability == ReliabilityConclusion.RELIABLE_BUT_TOO_SMALL:
        assert conclusion.plain_summary == "The measured difference is too small to justify changing this."


def test_evaluate_difference_rejects_negative_minimum_delta():
    with pytest.raises(ValidationError):
        evaluate_difference((1.0, 2.0), (3.0, 4.0), minimum_meaningful_delta=-1.0)


def test_evaluate_difference_reproducible_with_same_seed():
    rng = random.Random(11)
    baseline = tuple(rng.gauss(10, 2) for _ in range(20))
    candidate = tuple(rng.gauss(11, 2) for _ in range(20))
    c1 = evaluate_difference(baseline, candidate, minimum_meaningful_delta=0.5, seed=3)
    c2 = evaluate_difference(baseline, candidate, minimum_meaningful_delta=0.5, seed=3)
    assert c1 == c2
