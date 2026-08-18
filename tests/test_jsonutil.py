from __future__ import annotations

from enum import Enum

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.jsonutil import to_jsonable


class Color(str, Enum):
    RED = "red"


def test_primitives_pass_through():
    assert to_jsonable(None) is None
    assert to_jsonable("x") == "x"
    assert to_jsonable(5) == 5
    assert to_jsonable(True) is True


def test_enum_converts_to_value():
    assert to_jsonable(Color.RED) == "red"


def test_float_nan_inf_rejected():
    with pytest.raises(ValidationError):
        to_jsonable(float("nan"))
    with pytest.raises(ValidationError):
        to_jsonable(float("inf"))


def test_float_finite_ok():
    assert to_jsonable(1.5) == 1.5


def test_mapping_nonstring_key_rejected():
    with pytest.raises(ValidationError):
        to_jsonable({1: "a"})


def test_mapping_collision_after_conversion():
    # both keys are already strings and distinct; no collision expected
    assert to_jsonable({"1": "a", "2": "b"}) == {"1": "a", "2": "b"}


def test_sequence_converts_to_list():
    assert to_jsonable((1, 2, 3)) == [1, 2, 3]
    assert to_jsonable([1, "a", None]) == [1, "a", None]


def test_nested_structure():
    payload = {"a": [1, {"b": 2.5}], "c": None}
    assert to_jsonable(payload) == {"a": [1, {"b": 2.5}], "c": None}


def test_unsupported_type_rejected():
    class Unsupported:
        pass

    with pytest.raises(ValidationError):
        to_jsonable(Unsupported())


def test_bytes_not_treated_as_sequence_of_ints():
    with pytest.raises(ValidationError):
        to_jsonable(b"abc")
