"""Plain-language translations for the CLI's default (concise, non-JSON)
text output.

ProjectKaizen's internal contracts (ViabilityStatus, StoppingReason,
ComparisonVerdict, ReleaseFindingStatus, ChangeCategory, ...) are precise
and technical on purpose — they are what `--json` and `--full` expose, and
what the rest of this codebase reasons over. But a user who has never
studied continuous-improvement methodology should never need to learn
"marginal ceiling" or "diminishing returns" to read `projectkaizen status`.
This module is the one place that gap gets closed: every function here
takes a typed internal value and returns a plain English sentence, never
the reverse. Nothing upstream of the CLI's text-rendering branch should
need to know this module exists.

Translations for engines the default CLI commands don't currently surface
(fresh-evidence, blast radius, preservation, attempt-policy, root-cause
strategy names) import their enum types lazily, inside each function, not
at module scope. `cli.py` imports this module unconditionally for the
translations it *does* use every run (viability/stopping/verdict/
readiness/finding-status/change-category) — without the lazy imports here,
that single top-level import would transitively load every optional
engine's module for every command, which is exactly the "unused engine
execution" this codebase's own build spec prohibits. See
tests/test_engines_stay_conditional.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import ComparisonVerdict, StoppingReason, ViabilityStatus
from .release.models import ChangeCategory, ReadinessOutcome, ReleaseFindingStatus

if TYPE_CHECKING:
    from .attempt_policy import AttemptGuidance
    from .blast_radius import BlastRadiusCategory
    from .gates.fresh_evidence import EvidenceFreshness
    from .gates.preservation import PreservationDecision
    from .root_cause.base import RootCauseStrategyName

_VIABILITY_PLAIN: dict[ViabilityStatus, str] = {
    ViabilityStatus.VIABLE: "worth doing",
    ViabilityStatus.MARGINAL: "would only help a little",
    ViabilityStatus.NOT_WORTH_IT: "not worth doing right now",
    ViabilityStatus.DEFER: "blocked on something else first",
    ViabilityStatus.INSUFFICIENT_EVIDENCE: "not enough evidence yet to act on safely",
}


def plain_viability(status: ViabilityStatus) -> str:
    return _VIABILITY_PLAIN[status]


_STOPPING_REASON_PLAIN: dict[StoppingReason, str] = {
    StoppingReason.NO_RELEVANT_FINDINGS: "no issues were found",
    StoppingReason.TARGETS_ALREADY_MET: "the targets are already met",
    StoppingReason.ATTEMPT_BUDGET_EXHAUSTED: "several fixes have already been tried without success",
    StoppingReason.DIMINISHING_RETURNS: "further work is unlikely to be worth the extra effort",
    StoppingReason.RISK_EXCEEDS_GAIN: "the risk of continuing outweighs the expected benefit",
    StoppingReason.REMAINING_NOT_WORTH_IT: "what's left isn't worth doing",
    StoppingReason.MARGINAL_ONLY: "what's left would only help a little",
    StoppingReason.EXTERNAL_DEPENDENCY_REQUIRED: "progress needs something outside this project first",
    StoppingReason.INSUFFICIENT_EVIDENCE: "there isn't enough evidence yet to act on safely",
}


def plain_stopping_reason(reason: StoppingReason) -> str:
    return _STOPPING_REASON_PLAIN[reason]


def plain_stopping_reasons(reasons: tuple[StoppingReason, ...]) -> str:
    if not reasons:
        return ""
    return "; ".join(plain_stopping_reason(r) for r in reasons)


_VERDICT_PLAIN: dict[ComparisonVerdict, str] = {
    ComparisonVerdict.ACCEPT: "This change is an improvement and can be kept.",
    ComparisonVerdict.REJECT: "This change should not be kept as-is.",
    ComparisonVerdict.DEFER: "Not enough signal yet — verification needs to finish first.",
    ComparisonVerdict.INCONCLUSIVE: "No meaningful difference was measured either way.",
}


def plain_verdict(verdict: ComparisonVerdict) -> str:
    return _VERDICT_PLAIN[verdict]


_READINESS_OUTCOME_PLAIN: dict[ReadinessOutcome, str] = {
    ReadinessOutcome.BLOCKED: "This must be fixed before release.",
    ReadinessOutcome.NEEDS_CONFIRMATION: "A few things need a human to confirm before release.",
    ReadinessOutcome.NO_BLOCKER_FOUND: (
        "No blocking issues were found by these checks. This does not mean the release is "
        "guaranteed safe — only that nothing in this scope raised a concern."
    ),
}


def plain_readiness_outcome(outcome: ReadinessOutcome) -> str:
    return _READINESS_OUTCOME_PLAIN[outcome]


_FINDING_STATUS_PLAIN: dict[ReleaseFindingStatus, str] = {
    ReleaseFindingStatus.BLOCKED: "must fix",
    ReleaseFindingStatus.NEEDS_CONFIRMATION: "confirm before release",
    ReleaseFindingStatus.UNABLE_TO_VERIFY: "could not be checked automatically",
    ReleaseFindingStatus.NO_BLOCKER_FOUND: "no issue found",
}


def plain_finding_status(status: ReleaseFindingStatus) -> str:
    return _FINDING_STATUS_PLAIN[status]


_CHANGE_CATEGORY_PLAIN: dict[ChangeCategory, str] = {
    ChangeCategory.PUBLIC_API: "public API",
    ChangeCategory.CONFIG: "configuration",
    ChangeCategory.ENV_VARS: "environment variables",
    ChangeCategory.PERSISTED_SCHEMA: "saved data format",
    ChangeCategory.PACKAGE_METADATA: "package metadata",
    ChangeCategory.PYTHON_SUPPORT: "supported Python versions",
    ChangeCategory.DEPENDENCIES: "dependencies",
    ChangeCategory.CLI_CONTRACT: "command-line interface",
    ChangeCategory.ERROR_BEHAVIOR: "error handling",
    ChangeCategory.CONCURRENCY_LIFECYCLE: "process lifecycle",
    ChangeCategory.ARTIFACTS: "build/CI setup",
    ChangeCategory.MIGRATIONS: "data migration",
    ChangeCategory.COMPATIBILITY: "compatibility",
    ChangeCategory.OTHER: "other",
}


def plain_change_category(category: ChangeCategory) -> str:
    return _CHANGE_CATEGORY_PLAIN[category]


def plain_freshness(freshness: EvidenceFreshness) -> str:
    from .gates.fresh_evidence import EvidenceFreshness as _EvidenceFreshness

    table: dict[_EvidenceFreshness, str] = {
        _EvidenceFreshness.FRESH: "The test results are for this exact change and can be trusted.",
        _EvidenceFreshness.STALE: (
            "The available test results belong to an earlier version. Run the verification again "
            "before accepting this change."
        ),
        _EvidenceFreshness.UNBOUND: (
            "There's no way to confirm what these test results were actually run against. "
            "Run the verification again before accepting this change."
        ),
        _EvidenceFreshness.INSUFFICIENT: (
            "Someone reported testing this by hand, but that can't be automatically confirmed. "
            "Run the verification again before accepting this change."
        ),
    }
    return table[freshness]


def plain_blast_radius(category: BlastRadiusCategory, *, consumer_count: int) -> str:
    from .blast_radius import BlastRadiusCategory as _BlastRadiusCategory

    if category == _BlastRadiusCategory.LOCAL:
        return "This change is self-contained and doesn't appear to affect anything else."
    if category == _BlastRadiusCategory.BOUNDED:
        return f"This change affects {consumer_count} other file(s) — a focused check should be enough."
    if category == _BlastRadiusCategory.CROSS_MODULE:
        return f"This change affects {consumer_count} other files, so it needs broader regression testing."
    if category == _BlastRadiusCategory.CROSS_SYSTEM:
        return (
            "This change touches a public interface or saved-data format, "
            "so anything depending on it could be affected."
        )
    return "It isn't clear yet what this change affects - more investigation is needed before judging its impact."


def plain_preservation(decision: PreservationDecision) -> str:
    from .gates.preservation import PreservationDecision as _PreservationDecision

    table: dict[_PreservationDecision, str] = {
        _PreservationDecision.SAFE_TO_CHANGE: "Nothing found depends on this, so it looks safe to change or remove.",
        _PreservationDecision.REQUIRES_MORE_CONTEXT: (
            "Not enough is known yet about who depends on this to change it safely."
        ),
        _PreservationDecision.INTENT_STILL_VALID: (
            "Don't remove this yet. There's a documented reason it exists, and nothing suggests that "
            "reason no longer applies."
        ),
        _PreservationDecision.DO_NOT_REMOVE: (
            "Do not remove this. It protects a compatibility, platform, or performance requirement."
        ),
    }
    return table[decision]


def plain_attempt_guidance(guidance: AttemptGuidance) -> str:
    from .attempt_policy import AttemptGuidance as _AttemptGuidance

    table: dict[_AttemptGuidance, str] = {
        _AttemptGuidance.CONTINUE: "Take another look at the evidence before trying again.",
        _AttemptGuidance.REDUCE_CONFIDENCE: (
            "Two attempts have failed - treat the suspected cause as less certain and re-check it."
        ),
        _AttemptGuidance.ARCHITECTURE_REVIEW_REQUIRED: (
            "Several fixes have failed under the same assumption. Re-check the design before trying another patch."
        ),
        _AttemptGuidance.REOPENED: "New information justifies another attempt.",
    }
    return table[guidance]


def plain_root_cause_label(_strategy: RootCauseStrategyName) -> str:
    """Every root-cause strategy — Five Whys, Fishbone, A3, whichever was
    used — reads the same to a user who never asked to know the
    methodology name: "Likely cause"."""
    return "Likely cause"
