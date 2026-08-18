"""Blast radius estimation for a proposed Improvement.

Estimates how far a change to a given set of files is likely to reach:
direct importers, a bounded transitive closure, and whether it touches a
public contract (an exported package symbol or the CLI) or a persisted
schema (persistence.py / anything using its envelope). This is import-text
based, not a real static call graph — deterministic and explainable, but a
heuristic (import statements found by text search, not name resolution).

Large blast radius is not automatically bad — it raises the verification
and migration burden a caller should budget for, nothing more.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .config import KaizenConfig
from .exceptions import ValidationError
from .numbers import require_str_tuple
from .walker import WalkResult, read_text_bounded

_IMPORT_RE = re.compile(r"^\s*(?:from\s+([.\w]+)\s+import|import\s+([.\w]+))", re.MULTILINE)

#: transitive consumer search never expands beyond this many hops
MAX_TRANSITIVE_DEPTH = 3
#: ...or visits more files than this, so a huge repo can't blow up the search
MAX_VISITED_FILES = 5000


class BlastRadiusCategory(str, Enum):
    LOCAL = "local"
    BOUNDED = "bounded"
    CROSS_MODULE = "cross_module"
    CROSS_SYSTEM = "cross_system"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class BlastRadius:
    category: BlastRadiusCategory
    affected_paths: tuple[str, ...]
    direct_consumers: tuple[str, ...]
    transitive_consumer_count: int | None
    touches_public_contract: bool
    touches_persisted_schema: bool
    tests_affected: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.category, BlastRadiusCategory):
            raise ValidationError("blast_radius.category must be a BlastRadiusCategory")
        object.__setattr__(
            self, "affected_paths", require_str_tuple(self.affected_paths, name="blast_radius.affected_paths")
        )
        object.__setattr__(
            self, "direct_consumers", require_str_tuple(self.direct_consumers, name="blast_radius.direct_consumers")
        )
        object.__setattr__(
            self, "tests_affected", require_str_tuple(self.tests_affected, name="blast_radius.tests_affected")
        )


def _module_name(relative_path: str) -> str | None:
    if not relative_path.endswith(".py"):
        return None
    stem = relative_path[: -len(".py")]
    if stem.endswith("/__init__"):
        stem = stem[: -len("/__init__")]
    return stem.rsplit("/", 1)[-1] if stem else None


def _imported_module_names(text: str) -> set[str]:
    names: set[str] = set()
    for match in _IMPORT_RE.finditer(text):
        target = match.group(1) or match.group(2) or ""
        for part in target.split("."):
            if part:
                names.add(part)
    return names


_PUBLIC_CONTRACT_PATHS = {"src/projectkaizen/__init__.py", "src/projectkaizen/cli.py", "pyproject.toml"}


def _touches_public_contract(affected_paths: tuple[str, ...]) -> bool:
    return any(p in _PUBLIC_CONTRACT_PATHS or p.endswith("/__init__.py") or p == "__init__.py" for p in affected_paths)


def _touches_persisted_schema(affected_paths: tuple[str, ...]) -> bool:
    return any("persistence" in p for p in affected_paths)


def estimate_blast_radius(*, affected_paths: tuple[str, ...], walk: WalkResult, config: KaizenConfig) -> BlastRadius:
    if not affected_paths:
        raise ValidationError("affected_paths must not be empty")

    all_relative_paths = {f.relative_path for f in walk.files}
    unknown_paths = [p for p in affected_paths if p not in all_relative_paths]
    if unknown_paths:
        return BlastRadius(
            category=BlastRadiusCategory.UNKNOWN,
            affected_paths=affected_paths,
            direct_consumers=(),
            transitive_consumer_count=None,
            touches_public_contract=_touches_public_contract(affected_paths),
            touches_persisted_schema=_touches_persisted_schema(affected_paths),
            tests_affected=(),
            rationale=f"path(s) not found in the walked tree, cannot analyze imports: {unknown_paths}",
        )

    target_module_names = {name for p in affected_paths if (name := _module_name(p))}
    if not target_module_names:
        return BlastRadius(
            category=BlastRadiusCategory.UNKNOWN,
            affected_paths=affected_paths,
            direct_consumers=(),
            transitive_consumer_count=None,
            touches_public_contract=_touches_public_contract(affected_paths),
            touches_persisted_schema=_touches_persisted_schema(affected_paths),
            tests_affected=(),
            rationale="none of the affected paths are Python modules; import-based analysis does not apply",
        )

    file_imports: dict[str, set[str]] = {}
    for f in walk.files:
        if not f.relative_path.endswith(".py") or f.relative_path in affected_paths:
            continue
        try:
            text = read_text_bounded(f.absolute_path, max_bytes=config.walker_max_bytes_per_file).text
        except OSError:
            continue
        file_imports[f.relative_path] = _imported_module_names(text)

    def consumers_of(module_names: set[str]) -> set[str]:
        return {path for path, imports in file_imports.items() if imports & module_names}

    direct_consumers = consumers_of(target_module_names)

    visited = set(direct_consumers)
    frontier = set(direct_consumers)
    for _hop in range(MAX_TRANSITIVE_DEPTH - 1):
        if not frontier or len(visited) >= MAX_VISITED_FILES:
            break
        frontier_module_names = {name for p in frontier if (name := _module_name(p))}
        if not frontier_module_names:
            break
        next_layer = consumers_of(frontier_module_names) - visited
        visited |= next_layer
        frontier = next_layer

    tests_affected = tuple(sorted(p for p in direct_consumers if p.startswith("tests/") or "/tests/" in f"/{p}"))
    touches_public = _touches_public_contract(affected_paths)
    touches_schema = _touches_persisted_schema(affected_paths)

    if touches_public or touches_schema:
        category = BlastRadiusCategory.CROSS_SYSTEM
        rationale = "affects a public contract file and/or the persistence schema envelope"
    elif not direct_consumers:
        category = BlastRadiusCategory.LOCAL
        rationale = "no other analyzed file imports this module"
    elif len(direct_consumers) <= 3:
        category = BlastRadiusCategory.BOUNDED
        rationale = f"{len(direct_consumers)} direct consumer(s), no public-contract/schema involvement"
    else:
        category = BlastRadiusCategory.CROSS_MODULE
        rationale = f"{len(direct_consumers)} direct consumer(s) across the tree"

    return BlastRadius(
        category=category,
        affected_paths=affected_paths,
        direct_consumers=tuple(sorted(direct_consumers)),
        transitive_consumer_count=len(visited),
        touches_public_contract=touches_public,
        touches_persisted_schema=touches_schema,
        tests_affected=tests_affected,
        rationale=rationale,
    )
