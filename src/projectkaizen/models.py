"""Frozen domain models for ProjectKaizen.

All models are immutable (frozen dataclasses, tuples, MappingProxyType).
Enums are deterministic and explicit. Nothing here performs I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from .exceptions import ValidationError
from .numbers import require_nonblank_str, require_number, require_str_tuple


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


_SEVERITY_ORDER: Mapping[Severity, int] = MappingProxyType(
    {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
)


def severity_rank(value: Severity) -> int:
    return _SEVERITY_ORDER[value]


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


_CONFIDENCE_WEIGHT: Mapping[Confidence, float] = MappingProxyType(
    {Confidence.HIGH: 1.0, Confidence.MEDIUM: 0.6, Confidence.LOW: 0.3}
)


def confidence_weight(value: Confidence) -> float:
    return _CONFIDENCE_WEIGHT[value]


class RootCauseStatus(str, Enum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    POSSIBLE = "possible"


class ImprovementStatus(str, Enum):
    """Explicit lifecycle. Transitions are validated in graph/decide."""

    DISCOVERED = "discovered"
    UNDER_ANALYSIS = "under_analysis"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    VIABILITY_REVIEW = "viability_review"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NOT_WORTH_IT = "not_worth_it"
    DEFERRED = "deferred"
    INCONCLUSIVE = "inconclusive"
    SUPERSEDED = "superseded"


# Adjacency list of allowed forward transitions. Terminal states have no
# outgoing edges in this table except SUPERSEDED, which is reachable from
# any other state (including terminal ones) whenever new evidence makes the
# improvement obsolete — see validate_transition, per spec section 18.
_ALLOWED_TRANSITIONS: Mapping[ImprovementStatus, tuple[ImprovementStatus, ...]] = MappingProxyType(
    {
        ImprovementStatus.DISCOVERED: (ImprovementStatus.UNDER_ANALYSIS,),
        ImprovementStatus.UNDER_ANALYSIS: (
            ImprovementStatus.ROOT_CAUSE_IDENTIFIED,
            ImprovementStatus.INCONCLUSIVE,
        ),
        ImprovementStatus.ROOT_CAUSE_IDENTIFIED: (ImprovementStatus.VIABILITY_REVIEW,),
        ImprovementStatus.VIABILITY_REVIEW: (
            ImprovementStatus.READY,
            ImprovementStatus.NOT_WORTH_IT,
            ImprovementStatus.DEFERRED,
            ImprovementStatus.INCONCLUSIVE,
        ),
        ImprovementStatus.READY: (ImprovementStatus.IN_PROGRESS,),
        ImprovementStatus.IN_PROGRESS: (ImprovementStatus.VERIFYING,),
        ImprovementStatus.VERIFYING: (
            ImprovementStatus.ACCEPTED,
            ImprovementStatus.REJECTED,
            ImprovementStatus.INCONCLUSIVE,
        ),
        ImprovementStatus.ACCEPTED: (),
        ImprovementStatus.REJECTED: (),
        ImprovementStatus.NOT_WORTH_IT: (),
        ImprovementStatus.DEFERRED: (ImprovementStatus.UNDER_ANALYSIS,),
        ImprovementStatus.INCONCLUSIVE: (ImprovementStatus.UNDER_ANALYSIS,),
        ImprovementStatus.SUPERSEDED: (),
    }
)


def validate_transition(current: ImprovementStatus, target: ImprovementStatus) -> None:
    if target == ImprovementStatus.SUPERSEDED and current != ImprovementStatus.SUPERSEDED:
        return
    allowed = _ALLOWED_TRANSITIONS[current]
    if target not in allowed:
        raise ValidationError(
            f"illegal improvement transition {current.value} -> {target.value}; allowed: {[s.value for s in allowed]}"
        )


class ViabilityStatus(str, Enum):
    VIABLE = "viable"
    MARGINAL = "marginal"
    NOT_WORTH_IT = "not_worth_it"
    DEFER = "defer"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ComparisonVerdict(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    INCONCLUSIVE = "inconclusive"


class AnalysisStatus(str, Enum):
    COMPLETE = "complete"
    ANALYSIS_INCOMPLETE = "analysis_incomplete"
    FAILED = "failed"


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise ValidationError("expected a mapping")
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class Evidence:
    """A single piece of supporting evidence for a finding or outcome."""

    id: str
    kind: str
    description: str
    source: str
    data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="evidence.id"))
        object.__setattr__(self, "kind", require_nonblank_str(self.kind, name="evidence.kind"))
        object.__setattr__(self, "description", require_nonblank_str(self.description, name="evidence.description"))
        object.__setattr__(self, "source", require_nonblank_str(self.source, name="evidence.source"))
        object.__setattr__(self, "data", _freeze_mapping(self.data))


@dataclass(frozen=True, slots=True)
class ProjectArea:
    id: str
    name: str
    description: str = ""
    paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="project_area.id"))
        object.__setattr__(self, "name", require_nonblank_str(self.name, name="project_area.name"))
        object.__setattr__(self, "paths", require_str_tuple(self.paths, name="project_area.paths"))


@dataclass(frozen=True, slots=True)
class Finding:
    """Structured evidence of a potential improvement opportunity."""

    id: str
    project_area_id: str
    title: str
    description: str
    evidence: tuple[Evidence, ...]
    severity: Severity
    confidence: Confidence
    affected_paths: tuple[str, ...] = ()
    estimated_effort: str = "unknown"
    expected_impact: str = "unknown"
    implementation_risk: str = "unknown"
    dependencies: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    source: str = "unknown"
    status: str = "open"

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="finding.id"))
        object.__setattr__(
            self, "project_area_id", require_nonblank_str(self.project_area_id, name="finding.project_area_id")
        )
        object.__setattr__(self, "title", require_nonblank_str(self.title, name="finding.title"))
        object.__setattr__(self, "description", require_nonblank_str(self.description, name="finding.description"))
        if not isinstance(self.evidence, tuple):
            raise ValidationError("finding.evidence must be a tuple")
        if not isinstance(self.severity, Severity):
            raise ValidationError("finding.severity must be a Severity")
        if not isinstance(self.confidence, Confidence):
            raise ValidationError("finding.confidence must be a Confidence")
        object.__setattr__(
            self, "affected_paths", require_str_tuple(self.affected_paths, name="finding.affected_paths")
        )
        object.__setattr__(self, "dependencies", require_str_tuple(self.dependencies, name="finding.dependencies"))
        object.__setattr__(self, "tags", require_str_tuple(self.tags, name="finding.tags"))
        object.__setattr__(self, "source", require_nonblank_str(self.source, name="finding.source"))
        object.__setattr__(self, "status", require_nonblank_str(self.status, name="finding.status"))


@dataclass(frozen=True, slots=True)
class RootCause:
    id: str
    finding_id: str
    description: str
    status: RootCauseStatus
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="root_cause.id"))
        object.__setattr__(self, "finding_id", require_nonblank_str(self.finding_id, name="root_cause.finding_id"))
        object.__setattr__(self, "description", require_nonblank_str(self.description, name="root_cause.description"))
        if not isinstance(self.status, RootCauseStatus):
            raise ValidationError("root_cause.status must be a RootCauseStatus")
        if not isinstance(self.evidence, tuple):
            raise ValidationError("root_cause.evidence must be a tuple")


@dataclass(frozen=True, slots=True)
class VerificationPlan:
    """Explicit, argv-based verification steps. Never shell=True."""

    id: str
    description: str
    commands: tuple[tuple[str, ...], ...]
    success_criteria: str
    regression_criteria: str = ""
    rollback_guidance: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="verification_plan.id"))
        object.__setattr__(
            self, "description", require_nonblank_str(self.description, name="verification_plan.description")
        )
        if not isinstance(self.commands, tuple):
            raise ValidationError("verification_plan.commands must be a tuple of argv tuples")
        for argv in self.commands:
            if not isinstance(argv, tuple) or not argv or not all(isinstance(a, str) and a for a in argv):
                raise ValidationError("each verification command must be a non-empty tuple of non-empty strings")
        object.__setattr__(
            self,
            "success_criteria",
            require_nonblank_str(self.success_criteria, name="verification_plan.success_criteria"),
        )


@dataclass(frozen=True, slots=True)
class VerificationResult:
    plan_id: str
    passed: bool
    exit_code: int | None
    duration_seconds: float
    stdout_excerpt: str = ""
    stderr_excerpt: str = ""
    timed_out: bool = False
    truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_nonblank_str(self.plan_id, name="verification_result.plan_id"))
        if not isinstance(self.passed, bool):
            raise ValidationError("verification_result.passed must be a bool")
        object.__setattr__(
            self,
            "duration_seconds",
            require_number(self.duration_seconds, name="verification_result.duration_seconds", minimum=0.0),
        )


@dataclass(frozen=True, slots=True)
class ImprovementViability:
    """Gate result. A finding is never automatically READY."""

    status: ViabilityStatus
    rationale: str
    expected_benefit: float | None = None
    effort_score: float | None = None
    risk_score: float | None = None
    confidence: Confidence = Confidence.LOW
    reversible: bool = True
    verification_cost: str = "unknown"
    blocking_dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, ViabilityStatus):
            raise ValidationError("viability.status must be a ViabilityStatus")
        object.__setattr__(self, "rationale", require_nonblank_str(self.rationale, name="viability.rationale"))
        object.__setattr__(
            self,
            "blocking_dependencies",
            require_str_tuple(self.blocking_dependencies, name="viability.blocking_dependencies"),
        )


@dataclass(frozen=True, slots=True)
class Improvement:
    id: str
    finding_id: str
    root_cause_id: str
    title: str
    description: str
    scope: tuple[str, ...]
    risks: tuple[str, ...]
    verification_plan: VerificationPlan
    success_criteria: str
    regression_criteria: str
    rollback_guidance: str
    estimated_effort: str
    status: ImprovementStatus = ImprovementStatus.DISCOVERED
    viability: ImprovementViability | None = None
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="improvement.id"))
        object.__setattr__(self, "finding_id", require_nonblank_str(self.finding_id, name="improvement.finding_id"))
        object.__setattr__(
            self, "root_cause_id", require_nonblank_str(self.root_cause_id, name="improvement.root_cause_id")
        )
        object.__setattr__(self, "title", require_nonblank_str(self.title, name="improvement.title"))
        object.__setattr__(self, "scope", require_str_tuple(self.scope, name="improvement.scope"))
        object.__setattr__(self, "risks", require_str_tuple(self.risks, name="improvement.risks"))
        if not isinstance(self.verification_plan, VerificationPlan):
            raise ValidationError("improvement.verification_plan must be a VerificationPlan")
        object.__setattr__(self, "depends_on", require_str_tuple(self.depends_on, name="improvement.depends_on"))
        if not isinstance(self.status, ImprovementStatus):
            raise ValidationError("improvement.status must be an ImprovementStatus")


@dataclass(frozen=True, slots=True)
class Baseline:
    id: str
    metrics: Mapping[str, float]
    captured_from: str
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="baseline.id"))
        if not isinstance(self.metrics, Mapping) or not self.metrics:
            raise ValidationError("baseline.metrics must be a non-empty mapping")
        checked: dict[str, float] = {}
        for key, value in self.metrics.items():
            if not isinstance(key, str) or not key:
                raise ValidationError("baseline.metrics keys must be non-empty strings")
            checked[key] = require_number(value, name=f"baseline.metrics.{key}")
        object.__setattr__(self, "metrics", MappingProxyType(checked))
        object.__setattr__(
            self, "captured_from", require_nonblank_str(self.captured_from, name="baseline.captured_from")
        )


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str
    baseline_id: str
    improvement_id: str
    metrics: Mapping[str, float]
    captured_from: str
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="candidate.id"))
        object.__setattr__(self, "baseline_id", require_nonblank_str(self.baseline_id, name="candidate.baseline_id"))
        object.__setattr__(
            self, "improvement_id", require_nonblank_str(self.improvement_id, name="candidate.improvement_id")
        )
        if not isinstance(self.metrics, Mapping) or not self.metrics:
            raise ValidationError("candidate.metrics must be a non-empty mapping")
        checked: dict[str, float] = {}
        for key, value in self.metrics.items():
            if not isinstance(key, str) or not key:
                raise ValidationError("candidate.metrics keys must be non-empty strings")
            checked[key] = require_number(value, name=f"candidate.metrics.{key}")
        object.__setattr__(self, "metrics", MappingProxyType(checked))
        object.__setattr__(
            self, "captured_from", require_nonblank_str(self.captured_from, name="candidate.captured_from")
        )


@dataclass(frozen=True, slots=True)
class MetricDelta:
    metric: str
    baseline_value: float
    candidate_value: float
    absolute_delta: float
    relative_delta: float | None
    meaningful: bool
    threshold: float


@dataclass(frozen=True, slots=True)
class Comparison:
    id: str
    baseline_id: str
    candidate_id: str
    verdict: ComparisonVerdict
    rationale: str
    deltas: tuple[MetricDelta, ...]
    hard_gate_violations: tuple[str, ...] = ()
    rollback_guidance: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="comparison.id"))
        if not isinstance(self.verdict, ComparisonVerdict):
            raise ValidationError("comparison.verdict must be a ComparisonVerdict")
        object.__setattr__(self, "rationale", require_nonblank_str(self.rationale, name="comparison.rationale"))
        if not isinstance(self.deltas, tuple):
            raise ValidationError("comparison.deltas must be a tuple")
        object.__setattr__(
            self,
            "hard_gate_violations",
            require_str_tuple(self.hard_gate_violations, name="comparison.hard_gate_violations"),
        )


@dataclass(frozen=True, slots=True)
class ImprovementOutcome:
    id: str
    improvement_id: str
    comparison_id: str | None
    accepted: bool
    summary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="outcome.id"))
        object.__setattr__(
            self, "improvement_id", require_nonblank_str(self.improvement_id, name="outcome.improvement_id")
        )
        if not isinstance(self.accepted, bool):
            raise ValidationError("outcome.accepted must be a bool")
        object.__setattr__(self, "summary", require_nonblank_str(self.summary, name="outcome.summary"))


@dataclass(frozen=True, slots=True)
class Lesson:
    id: str
    improvement_id: str
    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="lesson.id"))
        object.__setattr__(
            self, "improvement_id", require_nonblank_str(self.improvement_id, name="lesson.improvement_id")
        )
        object.__setattr__(self, "text", require_nonblank_str(self.text, name="lesson.text"))


class StoppingReason(str, Enum):
    NO_RELEVANT_FINDINGS = "no_relevant_findings"
    REMAINING_NOT_WORTH_IT = "remaining_not_worth_it"
    MARGINAL_ONLY = "marginal_only"
    ATTEMPT_BUDGET_EXHAUSTED = "attempt_budget_exhausted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    RISK_EXCEEDS_GAIN = "risk_exceeds_gain"
    EXTERNAL_DEPENDENCY_REQUIRED = "external_dependency_required"
    TARGETS_ALREADY_MET = "targets_already_met"
    DIMINISHING_RETURNS = "diminishing_returns"


@dataclass(frozen=True, slots=True)
class StoppingDecision:
    stable: bool
    reasons: tuple[StoppingReason, ...]
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.stable, bool):
            raise ValidationError("stopping_decision.stable must be a bool")
        if not isinstance(self.reasons, tuple):
            raise ValidationError("stopping_decision.reasons must be a tuple")
        if self.stable and not self.reasons:
            raise ValidationError("stopping_decision.reasons required when stable=True")
        object.__setattr__(self, "rationale", require_nonblank_str(self.rationale, name="stopping_decision.rationale"))


@dataclass(frozen=True, slots=True)
class AttemptBudget:
    improvement_id: str
    max_attempts: int
    attempts_used: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "improvement_id", require_nonblank_str(self.improvement_id, name="attempt_budget.improvement_id")
        )
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool) or self.max_attempts < 1:
            raise ValidationError("attempt_budget.max_attempts must be a positive int")
        if not isinstance(self.attempts_used, int) or isinstance(self.attempts_used, bool) or self.attempts_used < 0:
            raise ValidationError("attempt_budget.attempts_used must be a non-negative int")

    @property
    def exhausted(self) -> bool:
        return self.attempts_used >= self.max_attempts

    @property
    def remaining(self) -> int:
        return max(0, self.max_attempts - self.attempts_used)

    def with_attempt(self) -> AttemptBudget:
        return AttemptBudget(
            improvement_id=self.improvement_id,
            max_attempts=self.max_attempts,
            attempts_used=self.attempts_used + 1,
        )


@dataclass(frozen=True, slots=True)
class OutputBudget:
    max_findings_shown: int = 5
    max_improvements_shown: int = 5
    max_evidence_items_per_finding: int = 3
    max_history_items_shown: int = 5
    max_lessons_shown: int = 5

    def __post_init__(self) -> None:
        for field_name in (
            "max_findings_shown",
            "max_improvements_shown",
            "max_evidence_items_per_finding",
            "max_history_items_shown",
            "max_lessons_shown",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValidationError(f"output_budget.{field_name} must be a positive int")


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    analyzer: str
    status: AnalysisStatus
    findings: tuple[Finding, ...]
    incomplete_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "analyzer", require_nonblank_str(self.analyzer, name="analysis_result.analyzer"))
        if not isinstance(self.status, AnalysisStatus):
            raise ValidationError("analysis_result.status must be an AnalysisStatus")
        if not isinstance(self.findings, tuple):
            raise ValidationError("analysis_result.findings must be a tuple")
        object.__setattr__(
            self,
            "incomplete_reasons",
            require_str_tuple(self.incomplete_reasons, name="analysis_result.incomplete_reasons"),
        )
        if self.status == AnalysisStatus.ANALYSIS_INCOMPLETE and not self.incomplete_reasons:
            raise ValidationError("ANALYSIS_INCOMPLETE requires at least one incomplete_reasons entry")
