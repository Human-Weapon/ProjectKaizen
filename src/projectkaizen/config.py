"""Strict configuration schema for ProjectKaizen.

Every entry point that produces a ``KaizenConfig`` (defaults, ``from_mapping``,
``load_file``) funnels through :meth:`KaizenConfig.from_mapping`, so there is
exactly one validation code path — constructor/loader parity is structural,
not a convention that could drift.

Unknown keys are rejected. ``bool`` is never accepted where ``int``/``float``
is expected (``bool`` is a subclass of ``int`` in Python and this is a
frequent source of silent bugs). NaN/Infinity are rejected. Sane bounds are
enforced.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .exceptions import ConfigurationError
from .models import OutputBudget

_KNOWN_KEYS = frozenset(
    {
        "max_attempts_per_improvement",
        "minimum_meaningful_delta",
        "default_relative_delta",
        "walker_max_files",
        "walker_max_depth",
        "walker_max_bytes_per_file",
        "walker_max_total_bytes",
        "verification_timeout_seconds",
        "verification_max_stdout_bytes",
        "verification_max_stderr_bytes",
        "history_max_entries",
        "output_budget",
        "diminishing_returns_window",
        "diminishing_returns_threshold_ratio",
    }
)

_OUTPUT_BUDGET_KNOWN_KEYS = frozenset(
    {
        "max_findings_shown",
        "max_improvements_shown",
        "max_evidence_items_per_finding",
        "max_history_items_shown",
        "max_lessons_shown",
    }
)


def _require_type(value: Any, expected: type, *, name: str) -> Any:
    if expected is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigurationError(f"{name} must be an int; got {type(value).__name__}")
    elif expected is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigurationError(f"{name} must be a number; got {type(value).__name__}")
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            raise ConfigurationError(f"{name} must be finite; got {value!r}")
    elif not isinstance(value, expected):
        raise ConfigurationError(f"{name} must be {expected.__name__}; got {type(value).__name__}")
    return value


def _positive_int(value: Any, *, name: str, minimum: int = 1, maximum: int | None = None) -> int:
    value = _require_type(value, int, name=name)
    if value < minimum:
        raise ConfigurationError(f"{name} must be >= {minimum}; got {value}")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"{name} must be <= {maximum}; got {value}")
    return value


def _positive_float(value: Any, *, name: str, minimum: float = 0.0, maximum: float | None = None) -> float:
    value = _require_type(value, float, name=name)
    if value < minimum:
        raise ConfigurationError(f"{name} must be >= {minimum}; got {value}")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"{name} must be <= {maximum}; got {value}")
    return value


def _parse_output_budget(raw: Any) -> OutputBudget:
    if raw is None:
        return OutputBudget()
    if not isinstance(raw, Mapping):
        raise ConfigurationError("output_budget must be an object")
    unknown = set(raw) - _OUTPUT_BUDGET_KNOWN_KEYS
    if unknown:
        raise ConfigurationError(f"output_budget has unknown keys: {sorted(unknown)}")
    kwargs = {}
    for key in _OUTPUT_BUDGET_KNOWN_KEYS:
        if key in raw:
            kwargs[key] = _positive_int(raw[key], name=f"output_budget.{key}", maximum=10_000)
    return OutputBudget(**kwargs)


def _parse_minimum_meaningful_delta(raw: Any) -> Mapping[str, float]:
    if raw is None:
        return MappingProxyType({})
    if not isinstance(raw, Mapping):
        raise ConfigurationError("minimum_meaningful_delta must be an object")
    out: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise ConfigurationError("minimum_meaningful_delta keys must be non-empty strings")
        out[key] = _positive_float(value, name=f"minimum_meaningful_delta.{key}", minimum=0.0)
    return MappingProxyType(out)


@dataclass(frozen=True, slots=True)
class KaizenConfig:
    max_attempts_per_improvement: int = 3
    minimum_meaningful_delta: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))
    default_relative_delta: float = 0.02
    walker_max_files: int = 20_000
    walker_max_depth: int = 64
    walker_max_bytes_per_file: int = 2_000_000
    walker_max_total_bytes: int = 200_000_000
    verification_timeout_seconds: float = 120.0
    verification_max_stdout_bytes: int = 1_048_576
    verification_max_stderr_bytes: int = 1_048_576
    history_max_entries: int = 500
    output_budget: OutputBudget = field(default_factory=OutputBudget)
    diminishing_returns_window: int = 3
    diminishing_returns_threshold_ratio: float = 0.3

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> KaizenConfig:
        if raw is None:
            raw = {}
        if not isinstance(raw, Mapping):
            raise ConfigurationError(f"config must be an object; got {type(raw).__name__}")
        unknown = set(raw) - _KNOWN_KEYS
        if unknown:
            raise ConfigurationError(f"config has unknown keys: {sorted(unknown)}")

        kwargs: dict[str, Any] = {}
        if "max_attempts_per_improvement" in raw:
            kwargs["max_attempts_per_improvement"] = _positive_int(
                raw["max_attempts_per_improvement"], name="max_attempts_per_improvement", maximum=1000
            )
        if "minimum_meaningful_delta" in raw:
            kwargs["minimum_meaningful_delta"] = _parse_minimum_meaningful_delta(raw["minimum_meaningful_delta"])
        if "default_relative_delta" in raw:
            kwargs["default_relative_delta"] = _positive_float(
                raw["default_relative_delta"], name="default_relative_delta", minimum=0.0, maximum=1.0
            )
        if "walker_max_files" in raw:
            kwargs["walker_max_files"] = _positive_int(
                raw["walker_max_files"], name="walker_max_files", maximum=10_000_000
            )
        if "walker_max_depth" in raw:
            kwargs["walker_max_depth"] = _positive_int(raw["walker_max_depth"], name="walker_max_depth", maximum=10_000)
        if "walker_max_bytes_per_file" in raw:
            kwargs["walker_max_bytes_per_file"] = _positive_int(
                raw["walker_max_bytes_per_file"], name="walker_max_bytes_per_file", maximum=10_000_000_000
            )
        if "walker_max_total_bytes" in raw:
            kwargs["walker_max_total_bytes"] = _positive_int(
                raw["walker_max_total_bytes"], name="walker_max_total_bytes", maximum=1_000_000_000_000
            )
        if "verification_timeout_seconds" in raw:
            kwargs["verification_timeout_seconds"] = _positive_float(
                raw["verification_timeout_seconds"],
                name="verification_timeout_seconds",
                minimum=0.1,
                maximum=86_400.0,
            )
        if "verification_max_stdout_bytes" in raw:
            kwargs["verification_max_stdout_bytes"] = _positive_int(
                raw["verification_max_stdout_bytes"],
                name="verification_max_stdout_bytes",
                minimum=0,
                maximum=1_000_000_000,
            )
        if "verification_max_stderr_bytes" in raw:
            kwargs["verification_max_stderr_bytes"] = _positive_int(
                raw["verification_max_stderr_bytes"],
                name="verification_max_stderr_bytes",
                minimum=0,
                maximum=1_000_000_000,
            )
        if "history_max_entries" in raw:
            kwargs["history_max_entries"] = _positive_int(
                raw["history_max_entries"], name="history_max_entries", maximum=1_000_000
            )
        if "output_budget" in raw:
            kwargs["output_budget"] = _parse_output_budget(raw["output_budget"])
        if "diminishing_returns_window" in raw:
            kwargs["diminishing_returns_window"] = _positive_int(
                raw["diminishing_returns_window"], name="diminishing_returns_window", minimum=2, maximum=100
            )
        if "diminishing_returns_threshold_ratio" in raw:
            kwargs["diminishing_returns_threshold_ratio"] = _positive_float(
                raw["diminishing_returns_threshold_ratio"],
                name="diminishing_returns_threshold_ratio",
                minimum=0.0,
                maximum=1.0,
            )
        return cls(**kwargs)

    @classmethod
    def load_file(cls, path: str | Path) -> KaizenConfig:
        text_path = Path(path)
        try:
            text = text_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(f"cannot read config file {text_path}: {exc}") from exc
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(f"config file {text_path} is not valid JSON: {exc}") from exc
        return cls.from_mapping(raw)

    def meaningful_delta_for(self, metric: str, baseline_value: float) -> float:
        """Absolute threshold below which a delta is not material for ``metric``."""
        if metric in self.minimum_meaningful_delta:
            return self.minimum_meaningful_delta[metric]
        return abs(baseline_value) * self.default_relative_delta
