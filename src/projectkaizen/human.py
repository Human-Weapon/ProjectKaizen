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
"""

from __future__ import annotations

from .models import ComparisonVerdict, StoppingReason, ViabilityStatus
from .release.models import ChangeCategory, ReadinessOutcome, ReleaseFindingStatus

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
