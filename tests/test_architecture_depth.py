from __future__ import annotations

from projectkaizen.analyzers import architecture_depth
from projectkaizen.models import AnalysisStatus
from projectkaizen.walker import walk_project


def _mkfile(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _walk(tmp_path):
    return walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)


def test_flags_multiple_passthrough_functions(tmp_path, config):
    _mkfile(
        tmp_path / "shallow.py",
        "import other\n\n"
        "def a(x, y):\n    return other.a(x, y)\n\n"
        "def b(x):\n    return other.b(x)\n\n"
        "def c(x, y, z):\n    return other.c(x, y, z)\n",
    )
    result = architecture_depth.analyze(_walk(tmp_path), config=config)
    assert result.status == AnalysisStatus.COMPLETE
    assert any("pass-through" in f.title for f in result.findings)


def test_does_not_flag_below_threshold(tmp_path, config):
    _mkfile(tmp_path / "mostly_fine.py", "import other\n\ndef a(x):\n    return other.a(x)\n")
    result = architecture_depth.analyze(_walk(tmp_path), config=config)
    assert result.findings == ()


def test_flags_shallow_wrapper_class(tmp_path, config):
    _mkfile(
        tmp_path / "wrapper.py",
        "class Wrapper:\n"
        "    def __init__(self, wrapped):\n        self._wrapped = wrapped\n"
        "    def m1(self, x):\n        return self._wrapped.m1(x)\n"
        "    def m2(self, x):\n        return self._wrapped.m2(x)\n"
        "    def m3(self, x):\n        return self._wrapped.m3(x)\n",
    )
    result = architecture_depth.analyze(_walk(tmp_path), config=config)
    assert any("shallow wrapper" in f.title for f in result.findings)
    wrapper_finding = next(f for f in result.findings if "shallow wrapper" in f.title)
    assert wrapper_finding.confidence.value == "medium"


def test_does_not_flag_real_deep_module(tmp_path, config):
    _mkfile(
        tmp_path / "deep.py",
        "class RealDeepModule:\n"
        "    def __init__(self):\n        self._cache = {}\n"
        "    def compute(self, x):\n"
        "        if x in self._cache:\n            return self._cache[x]\n"
        "        result = x * 2 + 1\n"
        "        self._cache[x] = result\n"
        "        return result\n",
    )
    result = architecture_depth.analyze(_walk(tmp_path), config=config)
    assert result.findings == ()


def test_init_files_excluded_from_passthrough_check(tmp_path, config):
    _mkfile(
        tmp_path / "__init__.py",
        "import other\n\n"
        "def a(x, y):\n    return other.a(x, y)\n\n"
        "def b(x):\n    return other.b(x)\n\n"
        "def c(x, y, z):\n    return other.c(x, y, z)\n",
    )
    result = architecture_depth.analyze(_walk(tmp_path), config=config)
    assert result.findings == ()


def test_syntax_error_reported_incomplete_not_crashed(tmp_path, config):
    _mkfile(tmp_path / "broken.py", "def f(:\n    pass\n")
    result = architecture_depth.analyze(_walk(tmp_path), config=config)
    assert result.status == AnalysisStatus.ANALYSIS_INCOMPLETE
    assert any("broken.py" in r for r in result.incomplete_reasons)


def test_function_without_own_params_not_flagged_as_passthrough(tmp_path, config):
    _mkfile(
        tmp_path / "noargs.py",
        "import other\n\n"
        "def a():\n    return other.constant()\n\n"
        "def b():\n    return other.other_constant()\n\n"
        "def c():\n    return other.third()\n",
    )
    result = architecture_depth.analyze(_walk(tmp_path), config=config)
    assert result.findings == ()
