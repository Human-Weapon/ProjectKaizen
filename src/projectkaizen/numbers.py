"""Strict numeric validation for public inputs.

Rejects bool (a subclass of int), NaN, ±Infinity. Missing measurements stay
``None`` — never coerced to 0. Explicit null is not the same as omitted.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from .exceptions import ValidationError


def _name(name: str) -> str:
    return name or "value"


def require_int(
    value: Any,
    *,
    name: str,
    allow_negative: bool = False,
    allow_zero: bool = True,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    label = _name(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            f"{label} must be an int (bool/NaN/float rejected); got {type(value).__name__}"
        )
    if not allow_negative and value < 0:
        raise ValidationError(f"{label} must not be negative; got {value}")
    if not allow_zero and value == 0:
        raise ValidationError(f"{label} must not be zero")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{label} must be >= {minimum}; got {value}")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{label} must be <= {maximum}; got {value}")
    return value


def require_number(
    value: Any,
    *,
    name: str,
    allow_negative: bool = False,
    allow_zero: bool = True,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    label = _name(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(
            f"{label} must be a finite number (bool/str rejected); got {type(value).__name__}"
        )
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        raise ValidationError(f"{label} must be a finite number; got {value!r}")
    if not allow_negative and number < 0:
        raise ValidationError(f"{label} must not be negative; got {number}")
    if not allow_zero and number == 0:
        raise ValidationError(f"{label} must not be zero")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{label} must be >= {minimum}; got {number}")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{label} must be <= {maximum}; got {number}")
    return number


def optional_int(value: Any, *, name: str, **kwargs: Any) -> int | None:
    if value is None:
        return None
    return require_int(value, name=name, **kwargs)


def optional_number(value: Any, *, name: str, **kwargs: Any) -> float | None:
    if value is None:
        return None
    return require_number(value, name=name, **kwargs)


def require_nonblank_str(value: Any, *, name: str) -> str:
    label = _name(name)
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a string; got {type(value).__name__}")
    text = value.strip()
    if not text:
        raise ValidationError(f"{label} must be a non-blank string")
    return text


def require_str(value: Any, *, name: str, allow_empty: bool = True) -> str:
    label = _name(name)
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a string; got {type(value).__name__}")
    if not allow_empty and value == "":
        raise ValidationError(f"{label} must not be empty")
    return value


def require_bool(value: Any, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(
            f"{name} must be a JSON boolean true/false; got {type(value).__name__}"
        )
    return value


def optional_bool(value: Any, *, name: str) -> bool | None:
    if value is None:
        return None
    return require_bool(value, name=name)


def reject_nonfinite_tree(value: Any, *, name: str = "value") -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise ValidationError(f"{name} must be finite; got {value!r}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            reject_nonfinite_tree(item, name=f"{name}.{key}")
        return value
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_nonfinite_tree(item, name=f"{name}[{index}]")
        return value
    return value


def deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError(f"mapping keys must be strings; got {type(key).__name__}")
            frozen[key] = deep_freeze(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(deep_freeze(v) for v in value)
    if isinstance(value, set):
        return frozenset(deep_freeze(v) for v in value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise ValidationError("NaN/Infinity rejected in nested data")
    return value


def reject_json_constant(token: str) -> None:
    raise ValidationError(f"non-finite JSON value rejected: {token}")


def relative_delta(baseline: float, candidate: float) -> float | None:
    if baseline == 0:
        return None
    return (candidate - baseline) / abs(baseline)


def require_str_tuple(value: Any, *, name: str) -> tuple[str, ...]:
    label = _name(name)
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError(f"{label} must be an array of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(f"{label} entries must be strings")
        out.append(item)
    return tuple(out)
