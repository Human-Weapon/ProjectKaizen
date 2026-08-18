from __future__ import annotations

import json

import pytest

from projectkaizen.config import KaizenConfig
from projectkaizen.exceptions import ConfigurationError


def test_defaults():
    cfg = KaizenConfig.from_mapping(None)
    assert cfg.max_attempts_per_improvement == 3
    assert cfg.output_budget.max_findings_shown == 5


def test_from_mapping_rejects_non_mapping():
    with pytest.raises(ConfigurationError):
        KaizenConfig.from_mapping([1, 2, 3])


def test_unknown_top_level_key_rejected():
    with pytest.raises(ConfigurationError):
        KaizenConfig.from_mapping({"bogus": 1})


@pytest.mark.parametrize(
    "payload",
    [
        {"max_attempts_per_improvement": True},
        {"max_attempts_per_improvement": 1.5},
        {"max_attempts_per_improvement": -1},
        {"max_attempts_per_improvement": 0},
        {"default_relative_delta": float("nan")},
        {"default_relative_delta": float("inf")},
        {"default_relative_delta": "0.1"},
        {"walker_max_files": True},
        {"walker_max_depth": -1},
        {"verification_timeout_seconds": 0},
        {"history_max_entries": 0},
        {"diminishing_returns_window": 1},
        {"output_budget": []},
        {"output_budget": {"bogus": 1}},
        {"output_budget": {"max_findings_shown": True}},
        {"minimum_meaningful_delta": []},
        {"minimum_meaningful_delta": {"x": -1.0}},
    ],
)
def test_invalid_payloads_rejected(payload):
    with pytest.raises(ConfigurationError):
        KaizenConfig.from_mapping(payload)


def test_valid_full_payload_accepted():
    cfg = KaizenConfig.from_mapping(
        {
            "max_attempts_per_improvement": 5,
            "minimum_meaningful_delta": {"latency_ms": 5.0},
            "default_relative_delta": 0.05,
            "walker_max_files": 100,
            "walker_max_depth": 10,
            "walker_max_bytes_per_file": 1000,
            "walker_max_total_bytes": 10000,
            "verification_timeout_seconds": 30.0,
            "verification_max_stdout_bytes": 100,
            "verification_max_stderr_bytes": 100,
            "history_max_entries": 50,
            "output_budget": {"max_findings_shown": 10},
            "diminishing_returns_window": 4,
            "diminishing_returns_threshold_ratio": 0.5,
        }
    )
    assert cfg.max_attempts_per_improvement == 5
    assert cfg.minimum_meaningful_delta["latency_ms"] == 5.0
    assert cfg.output_budget.max_findings_shown == 10


def test_load_file_roundtrip(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"max_attempts_per_improvement": 7}), encoding="utf-8")
    cfg = KaizenConfig.load_file(path)
    assert cfg.max_attempts_per_improvement == 7


def test_load_file_missing_raises():
    with pytest.raises(ConfigurationError):
        KaizenConfig.load_file("does-not-exist.json")


def test_load_file_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        KaizenConfig.load_file(path)


def test_meaningful_delta_for_uses_override_when_present():
    cfg = KaizenConfig.from_mapping({"minimum_meaningful_delta": {"latency_ms": 5.0}})
    assert cfg.meaningful_delta_for("latency_ms", 100.0) == 5.0


def test_meaningful_delta_for_falls_back_to_relative():
    cfg = KaizenConfig.from_mapping({"default_relative_delta": 0.02})
    assert cfg.meaningful_delta_for("unknown_metric", 100.0) == pytest.approx(2.0)


def test_constructor_and_loader_parity(tmp_path):
    payload = {"max_attempts_per_improvement": 9}
    from_mapping_cfg = KaizenConfig.from_mapping(payload)
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    from_file_cfg = KaizenConfig.load_file(path)
    assert from_mapping_cfg == from_file_cfg
