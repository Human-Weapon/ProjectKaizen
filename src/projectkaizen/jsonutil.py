"""Convert frozen domain values to JSON-native transport structures."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any

from .exceptions import ValidationError


def to_jsonable(value: Any, *, name: str = "value") -> Any:
    """Recursively convert immutable domain data to JSON-native types.

    Mapping keys MUST already be strings. Non-string keys raise
    ``ValidationError`` — they are never ``str()``'d, so ``{1: "a", "1": "b"}``
    cannot collapse. NaN / ±Infinity are rejected. ``default=str`` is never used.
    """
    if value is None or isinstance(value, (str, int, bool)):
        if isinstance(value, bool) or not isinstance(value, int):
            return value
        return value
    if isinstance(value, Enum):
        return to_jsonable(value.value, name=name)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValidationError(f"{name} must be finite")
        return value
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError(
                    f"{name} mapping keys must be strings; got {type(key).__name__}"
                )
            if key in out:
                raise ValidationError(f"{name} has colliding mapping key {key!r}")
            out[key] = to_jsonable(item, name=f"{name}.{key}")
        return out
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_jsonable(item, name=f"{name}[{index}]") for index, item in enumerate(value)]
    raise ValidationError(f"{name} is not JSON-native ({type(value).__name__})")
