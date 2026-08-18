"""Shared input validation for the statistics package.

Self-adversarial finding: passing NaN/Inf straight into stdlib
`statistics.stdev` on Python 3.11+ (which uses exact fraction arithmetic
internally) raises a confusing internal ``AttributeError`` — not a clean,
expected failure. Every public function in this package validates its raw
sample data at the boundary instead, matching the rest of ProjectKaizen's
"validate at system boundaries" convention.
"""

from __future__ import annotations

from ..numbers import require_number


def require_finite_values(values: tuple[float, ...], *, name: str) -> tuple[float, ...]:
    for i, v in enumerate(values):
        require_number(v, name=f"{name}[{i}]", allow_negative=True)
    return values
