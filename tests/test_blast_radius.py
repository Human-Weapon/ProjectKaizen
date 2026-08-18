from __future__ import annotations

import pytest

from projectkaizen.blast_radius import BlastRadiusCategory, estimate_blast_radius
from projectkaizen.exceptions import ValidationError
from projectkaizen.walker import walk_project


def _mkfile(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _walk(tmp_path):
    return walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)


def test_local_when_no_consumers(tmp_path, config):
    _mkfile(tmp_path / "isolated.py", "def f():\n    return 1\n")
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("isolated.py",), walk=walk, config=config)
    assert result.category == BlastRadiusCategory.LOCAL
    assert result.direct_consumers == ()


def test_bounded_with_few_consumers(tmp_path, config):
    _mkfile(tmp_path / "core.py", "def f():\n    return 1\n")
    _mkfile(tmp_path / "user1.py", "import core\n")
    _mkfile(tmp_path / "user2.py", "from core import f\n")
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("core.py",), walk=walk, config=config)
    assert result.category == BlastRadiusCategory.BOUNDED
    assert set(result.direct_consumers) == {"user1.py", "user2.py"}


def test_cross_module_with_many_consumers(tmp_path, config):
    _mkfile(tmp_path / "core.py", "def f():\n    return 1\n")
    for i in range(5):
        _mkfile(tmp_path / f"user{i}.py", "import core\n")
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("core.py",), walk=walk, config=config)
    assert result.category == BlastRadiusCategory.CROSS_MODULE


def test_cross_system_when_touching_init(tmp_path, config):
    _mkfile(tmp_path / "__init__.py", "")
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("__init__.py",), walk=walk, config=config)
    assert result.category == BlastRadiusCategory.CROSS_SYSTEM
    assert result.touches_public_contract is True


def test_cross_system_when_touching_persisted_schema(tmp_path, config):
    _mkfile(tmp_path / "persistence.py", "def f():\n    return 1\n")
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("persistence.py",), walk=walk, config=config)
    assert result.category == BlastRadiusCategory.CROSS_SYSTEM
    assert result.touches_persisted_schema is True


def test_unknown_when_path_not_in_walked_tree(tmp_path, config):
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("nope.py",), walk=walk, config=config)
    assert result.category == BlastRadiusCategory.UNKNOWN


def test_unknown_when_path_not_python(tmp_path, config):
    _mkfile(tmp_path / "README.md", "hi")
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("README.md",), walk=walk, config=config)
    assert result.category == BlastRadiusCategory.UNKNOWN


def test_transitive_consumers_discovered(tmp_path, config):
    _mkfile(tmp_path / "core.py", "def f():\n    return 1\n")
    _mkfile(tmp_path / "mid.py", "import core\n")
    _mkfile(tmp_path / "outer.py", "import mid\n")
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("core.py",), walk=walk, config=config)
    assert result.transitive_consumer_count is not None
    assert result.transitive_consumer_count >= 2


def test_tests_affected_detected(tmp_path, config):
    _mkfile(tmp_path / "core.py", "def f():\n    return 1\n")
    _mkfile(tmp_path / "tests" / "test_core.py", "import core\n")
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("core.py",), walk=walk, config=config)
    assert "tests/test_core.py" in result.tests_affected


def test_cyclic_imports_do_not_hang(tmp_path, config):
    # a imports b, b imports a: transitive search must terminate via the
    # `visited` set, not loop forever chasing the cycle.
    _mkfile(tmp_path / "a.py", "import b\n")
    _mkfile(tmp_path / "b.py", "import a\n")
    walk = _walk(tmp_path)
    result = estimate_blast_radius(affected_paths=("a.py",), walk=walk, config=config)
    assert result.category == BlastRadiusCategory.BOUNDED
    assert result.transitive_consumer_count is not None


def test_rejects_empty_affected_paths(tmp_path, config):
    walk = _walk(tmp_path)
    with pytest.raises(ValidationError):
        estimate_blast_radius(affected_paths=(), walk=walk, config=config)
