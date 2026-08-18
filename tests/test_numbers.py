from __future__ import annotations

import math

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.numbers import (
    deep_freeze,
    optional_bool,
    optional_int,
    optional_number,
    reject_nonfinite_tree,
    relative_delta,
    require_bool,
    require_int,
    require_nonblank_str,
    require_number,
    require_str,
    require_str_tuple,
)


def test_require_int_accepts_plain_int():
    assert require_int(5, name="x") == 5


def test_require_int_rejects_bool():
    with pytest.raises(ValidationError):
        require_int(True, name="x")


def test_require_int_rejects_float():
    with pytest.raises(ValidationError):
        require_int(1.5, name="x")


def test_require_int_bounds():
    with pytest.raises(ValidationError):
        require_int(-1, name="x", allow_negative=False)
    with pytest.raises(ValidationError):
        require_int(0, name="x", allow_zero=False)
    with pytest.raises(ValidationError):
        require_int(1, name="x", minimum=2)
    with pytest.raises(ValidationError):
        require_int(5, name="x", maximum=4)
    assert require_int(-5, name="x", allow_negative=True) == -5


def test_require_number_rejects_bool_and_nan_inf():
    with pytest.raises(ValidationError):
        require_number(True, name="x")
    with pytest.raises(ValidationError):
        require_number(float("nan"), name="x")
    with pytest.raises(ValidationError):
        require_number(float("inf"), name="x")
    with pytest.raises(ValidationError):
        require_number("1.0", name="x")


def test_require_number_bounds():
    with pytest.raises(ValidationError):
        require_number(-1.0, name="x")
    with pytest.raises(ValidationError):
        require_number(0.0, name="x", allow_zero=False)
    with pytest.raises(ValidationError):
        require_number(1.0, name="x", minimum=2.0)
    with pytest.raises(ValidationError):
        require_number(5.0, name="x", maximum=4.0)


def test_optional_int_and_number_pass_through_none():
    assert optional_int(None, name="x") is None
    assert optional_number(None, name="x") is None
    assert optional_int(3, name="x") == 3
    assert optional_number(3.5, name="x") == 3.5


def test_require_nonblank_str():
    assert require_nonblank_str(" hi ", name="x") == "hi"
    with pytest.raises(ValidationError):
        require_nonblank_str("   ", name="x")
    with pytest.raises(ValidationError):
        require_nonblank_str(5, name="x")


def test_require_str_allow_empty():
    assert require_str("", name="x") == ""
    with pytest.raises(ValidationError):
        require_str("", name="x", allow_empty=False)
    with pytest.raises(ValidationError):
        require_str(5, name="x")


def test_require_bool_strict():
    assert require_bool(True, name="x") is True
    with pytest.raises(ValidationError):
        require_bool(1, name="x")


def test_optional_bool_passes_none():
    assert optional_bool(None, name="x") is None
    assert optional_bool(False, name="x") is False


def test_reject_nonfinite_tree():
    reject_nonfinite_tree({"a": [1, 2.0, True]})
    with pytest.raises(ValidationError):
        reject_nonfinite_tree({"a": float("nan")})
    with pytest.raises(ValidationError):
        reject_nonfinite_tree([1, [2, float("inf")]])


def test_deep_freeze_mapping_list_set():
    frozen = deep_freeze({"a": [1, 2], "b": {3, 4}})
    assert frozen["a"] == (1, 2)
    assert frozen["b"] == frozenset({3, 4})
    with pytest.raises(TypeError):
        frozen["a"] = 1  # MappingProxyType is read-only


def test_deep_freeze_rejects_nonstring_keys_and_nonfinite():
    with pytest.raises(ValidationError):
        deep_freeze({1: "a"})
    with pytest.raises(ValidationError):
        deep_freeze(float("nan"))


def test_relative_delta_zero_baseline_returns_none():
    assert relative_delta(0.0, 5.0) is None


def test_relative_delta_normal():
    assert relative_delta(100.0, 110.0) == pytest.approx(0.1)
    assert relative_delta(100.0, 90.0) == pytest.approx(-0.1)


def test_require_str_tuple():
    assert require_str_tuple(["a", "b"], name="x") == ("a", "b")
    with pytest.raises(ValidationError):
        require_str_tuple("ab", name="x")
    with pytest.raises(ValidationError):
        require_str_tuple([1, 2], name="x")


def test_math_isnan_isinf_sanity():
    # sanity check our own imports work as expected in this module
    assert math.isnan(float("nan"))
