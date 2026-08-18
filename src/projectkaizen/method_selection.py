"""Method selection: the governance layer above every optional analysis
engine ProjectKaizen has.

The question this module answers is never "which methodology should I
use" — it is "do I need to run anything else at all." Every engine listed
in `AnalysisEngine` (git hotspots, blast radius, the preservation gate,
root-cause strategies, statistical strategies, release readiness, the
large-repo decomposer) is a candidate *tool*, never a default path. None
of them are wired into ProjectKaizen's default CLI flow; this module is
where a caller (a future CLI feature, or an agent using ProjectKaizen as a
library) should decide whether to invoke one at all, and if so, which.

Core rule: **no analysis without decision value.** If existing evidence
already lets the caller make a safe, useful call, `select_method` says so
and nothing downstream should run. When more evidence is genuinely needed,
the cheapest tier that can plausibly answer the question wins — direct
evidence, then a deterministic rule/check, then a statistical method, then
a causal investigation (root_cause/), and only last a bounded experiment
(PDCA). Continuous-improvement methodology is not privileged over
statistics, or vice versa — both sit in the same ordering, chosen by tier
and cost, never by which one is more "official."
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .exceptions import ValidationError
from .numbers import require_nonblank_str, require_str_tuple


class AnalysisEngine(str, Enum):
    GIT_HOTSPOTS = "git_hotspots"
    BLAST_RADIUS = "blast_radius"
    PRESERVATION_GATE = "preservation_gate"
    ROOT_CAUSE_STRATEGY = "root_cause_strategy"
    STATISTICAL_STRATEGY = "statistical_strategy"
    RELEASE_READINESS = "release_readiness"
    REPOSITORY_DECOMPOSER = "repository_decomposer"


class AnalysisMethodTier(str, Enum):
    DIRECT_EVIDENCE = "direct_evidence"
    DETERMINISTIC_RULE = "deterministic_rule"
    STATISTICAL = "statistical"
    CAUSAL_INVESTIGATION = "causal_investigation"
    BOUNDED_EXPERIMENT = "bounded_experiment"


#: preference order — lower sorts first (cheaper / more preferred)
_TIER_ORDER: dict[AnalysisMethodTier, int] = {
    AnalysisMethodTier.DIRECT_EVIDENCE: 1,
    AnalysisMethodTier.DETERMINISTIC_RULE: 2,
    AnalysisMethodTier.STATISTICAL: 3,
    AnalysisMethodTier.CAUSAL_INVESTIGATION: 4,
    AnalysisMethodTier.BOUNDED_EXPERIMENT: 5,
}

#: the tier each engine most naturally belongs to, when a caller doesn't
#: want to think about tier assignment themselves
DEFAULT_ENGINE_TIER: dict[AnalysisEngine, AnalysisMethodTier] = {
    AnalysisEngine.GIT_HOTSPOTS: AnalysisMethodTier.DETERMINISTIC_RULE,
    AnalysisEngine.BLAST_RADIUS: AnalysisMethodTier.DETERMINISTIC_RULE,
    AnalysisEngine.PRESERVATION_GATE: AnalysisMethodTier.DETERMINISTIC_RULE,
    AnalysisEngine.RELEASE_READINESS: AnalysisMethodTier.DETERMINISTIC_RULE,
    AnalysisEngine.REPOSITORY_DECOMPOSER: AnalysisMethodTier.DETERMINISTIC_RULE,
    AnalysisEngine.STATISTICAL_STRATEGY: AnalysisMethodTier.STATISTICAL,
    AnalysisEngine.ROOT_CAUSE_STRATEGY: AnalysisMethodTier.CAUSAL_INVESTIGATION,
}


@dataclass(frozen=True, slots=True)
class AnalysisCost:
    """A rough, comparable cost estimate — not a precise prediction.

    ``estimated_cost`` is a documented, deterministic weighted sum, not a
    magic score: every component is visible on the object itself.
    """

    compute_relative: float = 0.0
    subprocess_calls: int = 0
    files_inspected: int = 0
    expected_runtime_seconds: float = 0.0
    token_cost_estimate: int | None = None
    requires_human_input: bool = False

    def __post_init__(self) -> None:
        if self.compute_relative < 0:
            raise ValidationError("analysis_cost.compute_relative must be >= 0")
        if self.subprocess_calls < 0:
            raise ValidationError("analysis_cost.subprocess_calls must be >= 0")
        if self.files_inspected < 0:
            raise ValidationError("analysis_cost.files_inspected must be >= 0")
        if self.expected_runtime_seconds < 0:
            raise ValidationError("analysis_cost.expected_runtime_seconds must be >= 0")
        if self.token_cost_estimate is not None and self.token_cost_estimate < 0:
            raise ValidationError("analysis_cost.token_cost_estimate must be >= 0 or None")

    @property
    def estimated_cost(self) -> float:
        cost = (
            self.compute_relative
            + 0.1 * self.subprocess_calls
            + 0.01 * self.files_inspected
            + self.expected_runtime_seconds
        )
        if self.token_cost_estimate:
            cost += 0.001 * self.token_cost_estimate
        if self.requires_human_input:
            cost += 5.0
        return cost


#: a free/near-free cost, for methods with no real overhead
ZERO_COST = AnalysisCost()


@dataclass(frozen=True, slots=True)
class DecisionSufficiency:
    """Is existing evidence already enough to decide?"""

    sufficient: bool
    rationale: str
    missing_for_decision: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.sufficient, bool):
            raise ValidationError("decision_sufficiency.sufficient must be a bool")
        object.__setattr__(
            self, "rationale", require_nonblank_str(self.rationale, name="decision_sufficiency.rationale")
        )
        object.__setattr__(
            self,
            "missing_for_decision",
            require_str_tuple(self.missing_for_decision, name="decision_sufficiency.missing_for_decision"),
        )


def sufficiency_from_hard_gate_violations(violations: tuple[str, ...]) -> DecisionSufficiency:
    """NO STATISTICS WHEN OBVIOUS: a failed required test, a missing file,
    a removed public contract, an incompatible schema, a broken build, or
    any other deterministic hard-gate violation already decides the
    outcome — no hypothesis test or root-cause investigation is needed to
    know a hard gate failed.
    """
    if violations:
        return DecisionSufficiency(
            sufficient=True,
            rationale=f"{len(violations)} deterministic hard-gate violation(s) already decide this outcome",
        )
    return DecisionSufficiency(
        sufficient=False,
        rationale="no deterministic hard-gate violation found",
        missing_for_decision=("hard_gate_check",),
    )


@dataclass(frozen=True, slots=True)
class MethodOption:
    engine: AnalysisEngine
    tier: AnalysisMethodTier
    cost: AnalysisCost = ZERO_COST
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.engine, AnalysisEngine):
            raise ValidationError("method_option.engine must be an AnalysisEngine")
        if not isinstance(self.tier, AnalysisMethodTier):
            raise ValidationError("method_option.tier must be an AnalysisMethodTier")
        if not isinstance(self.cost, AnalysisCost):
            raise ValidationError("method_option.cost must be an AnalysisCost")


@dataclass(frozen=True, slots=True)
class MethodSelection:
    should_analyze_further: bool
    chosen: MethodOption | None
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.should_analyze_further, bool):
            raise ValidationError("method_selection.should_analyze_further must be a bool")
        if self.chosen is not None and not isinstance(self.chosen, MethodOption):
            raise ValidationError("method_selection.chosen must be a MethodOption or None")
        # should_analyze_further=True with chosen=None is legitimate: "more
        # evidence is needed, but nothing was offered to get it." The
        # inverse is not: if no further analysis is needed, nothing should
        # have been selected to run.
        if not self.should_analyze_further and self.chosen is not None:
            raise ValidationError("method_selection: should_analyze_further=False must not carry a chosen method")
        object.__setattr__(self, "rationale", require_nonblank_str(self.rationale, name="method_selection.rationale"))


def select_method(*, sufficiency: DecisionSufficiency, candidates: tuple[MethodOption, ...] = ()) -> MethodSelection:
    """STOP EARLY: if existing evidence is already sufficient, no method is
    selected, full stop — not even the cheapest one. Otherwise picks the
    lowest-tier, lowest-cost candidate that was actually offered; this
    function never invents a method the caller didn't declare as available.
    """
    if sufficiency.sufficient:
        return MethodSelection(
            should_analyze_further=False,
            chosen=None,
            rationale=f"existing evidence is sufficient ({sufficiency.rationale}); no further analysis needed",
        )

    if not candidates:
        return MethodSelection(
            should_analyze_further=True,
            chosen=None,
            rationale=(
                f"more evidence is needed ({sufficiency.rationale}) but no analysis method was offered "
                f"as a candidate; missing: {list(sufficiency.missing_for_decision)}"
            ),
        )

    best = min(candidates, key=lambda option: (_TIER_ORDER[option.tier], option.cost.estimated_cost))
    return MethodSelection(
        should_analyze_further=True,
        chosen=best,
        rationale=(
            f"evidence insufficient ({sufficiency.rationale}); selected the cheapest sufficient method: "
            f"{best.engine.value} (tier={best.tier.value}, cost={best.cost.estimated_cost:.3g})"
        ),
    )
