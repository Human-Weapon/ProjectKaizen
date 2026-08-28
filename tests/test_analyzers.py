from __future__ import annotations

from projectkaizen.analyzers import (
    ALL_ANALYZERS,
    ai_agent_readiness,
    architecture,
    code_health,
    dependencies,
    developer_experience,
    documentation,
    repository_hygiene,
    run_all,
    test_health,
)
from projectkaizen.models import AnalysisStatus
from projectkaizen.walker import walk_project


def _walk(tmp_path, **limits):
    defaults = {"max_files": 1000, "max_depth": 64, "max_total_bytes": 10_000_000}
    defaults.update(limits)
    return walk_project(tmp_path, **defaults)


def _mkfile(path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_registry_covers_nine_analyzers():
    assert len(ALL_ANALYZERS) == 9


def test_run_all_is_deterministic_order(tmp_path, config):
    _mkfile(tmp_path / "a.py", "print(1)\n")
    walk = _walk(tmp_path)
    r1 = run_all(walk, config=config)
    r2 = run_all(walk, config=config)
    assert [r.analyzer for r in r1] == [r.analyzer for r in r2]
    assert [r.analyzer for r in r1] == sorted(r.analyzer for r in r1)


# --- ArchitectureAnalyzer -------------------------------------------------


def test_architecture_flags_oversized_module(tmp_path, config):
    big = "\n".join(f"x{i} = {i}" for i in range(700))
    _mkfile(tmp_path / "big.py", big)
    walk = _walk(tmp_path)
    result = architecture.analyze(walk, config=config)
    assert result.status == AnalysisStatus.COMPLETE
    assert any("oversized module" in f.title for f in result.findings)


def test_architecture_flags_mixed_layout(tmp_path, config):
    _mkfile(tmp_path / "src" / "pkg" / "__init__.py", "")
    _mkfile(tmp_path / "flatpkg" / "__init__.py", "")
    walk = _walk(tmp_path)
    result = architecture.analyze(walk, config=config)
    assert any("mixed src-layout" in f.title for f in result.findings)


def test_architecture_clean_project_no_findings(tmp_path, config):
    _mkfile(tmp_path / "a.py", "print(1)\n")
    walk = _walk(tmp_path)
    result = architecture.analyze(walk, config=config)
    assert result.findings == ()


# --- CodeHealthAnalyzer ----------------------------------------------------


def test_code_health_flags_oversized_function(tmp_path, config):
    body = "\n".join(f"    x{i} = {i}" for i in range(90))
    _mkfile(tmp_path / "f.py", f"def big():\n{body}\n")
    walk = _walk(tmp_path)
    result = code_health.analyze(walk, config=config)
    assert any("oversized function" in f.title for f in result.findings)


def test_code_health_flags_todo(tmp_path, config):
    _mkfile(tmp_path / "f.py", "# TODO: fix this\nx = 1\n")
    walk = _walk(tmp_path)
    result = code_health.analyze(walk, config=config)
    assert any("TODO" in f.title for f in result.findings)


def test_code_health_flags_broad_except(tmp_path, config):
    _mkfile(tmp_path / "f.py", "try:\n    x = 1\nexcept:\n    pass\n")
    walk = _walk(tmp_path)
    result = code_health.analyze(walk, config=config)
    assert any("broad except" in f.title for f in result.findings)


def test_code_health_clean_file_no_findings(tmp_path, config):
    _mkfile(tmp_path / "f.py", "def small():\n    return 1\n")
    walk = _walk(tmp_path)
    result = code_health.analyze(walk, config=config)
    assert result.findings == ()


# --- TestHealthAnalyzer -----------------------------------------------------


def test_test_health_flags_untested_module(tmp_path, config):
    _mkfile(tmp_path / "src" / "mymod.py", "def f():\n    return 1\n")
    walk = _walk(tmp_path)
    result = test_health.analyze(walk, config=config)
    assert any("without a matching test" in f.title for f in result.findings)


def test_test_health_matched_test_suppresses_finding(tmp_path, config):
    _mkfile(tmp_path / "src" / "mymod.py", "def f():\n    return 1\n")
    _mkfile(tmp_path / "tests" / "test_mymod.py", "def test_f():\n    assert True\n")
    walk = _walk(tmp_path)
    result = test_health.analyze(walk, config=config)
    assert not any("without a matching test" in f.title for f in result.findings)


def test_test_health_flags_skipped_test(tmp_path, config):
    _mkfile(tmp_path / "tests" / "test_x.py", "import pytest\n\n@pytest.mark.skip\ndef test_x():\n    pass\n")
    walk = _walk(tmp_path)
    result = test_health.analyze(walk, config=config)
    assert any("skipped tests" in f.title for f in result.findings)


def test_test_health_flags_tautological_assertion(tmp_path, config):
    _mkfile(tmp_path / "tests" / "test_x.py", "def test_x():\n    assert True\n")
    walk = _walk(tmp_path)
    result = test_health.analyze(walk, config=config)
    assert any("tautological" in f.title for f in result.findings)


# --- DocumentationAnalyzer --------------------------------------------------


def test_documentation_flags_missing_readme(tmp_path, config):
    _mkfile(tmp_path / "a.py", "x = 1\n")
    walk = _walk(tmp_path)
    result = documentation.analyze(walk, config=config)
    assert any("missing README" in f.title for f in result.findings)


def test_documentation_readme_present_no_missing_finding(tmp_path, config):
    _mkfile(tmp_path / "README.md", "# hi\n")
    walk = _walk(tmp_path)
    result = documentation.analyze(walk, config=config)
    assert not any("missing README" in f.title for f in result.findings)


def test_documentation_version_mismatch_detected(tmp_path, config):
    _mkfile(tmp_path / "README.md", "This is version 9.9.9 of the project.\n")
    _mkfile(tmp_path / "pkg" / "_version.py", '__version__ = "1.0.0"\n')
    walk = _walk(tmp_path)
    result = documentation.analyze(walk, config=config)
    assert any("version mismatch" in f.title.lower() or "disagree" in f.title for f in result.findings)


# --- DependencyAnalyzer ------------------------------------------------------


def test_dependencies_no_pyproject_no_findings(tmp_path, config):
    walk = _walk(tmp_path)
    result = dependencies.analyze(walk, config=config)
    assert result.findings == ()


def test_dependencies_flags_duplicate(tmp_path, config):
    _mkfile(tmp_path / "pyproject.toml", 'dependencies = [\n  "requests>=2",\n  "requests>=3",\n]\n')
    walk = _walk(tmp_path)
    result = dependencies.analyze(walk, config=config)
    assert any("duplicate" in f.title for f in result.findings)


def test_dependencies_flags_unpinned_vcs(tmp_path, config):
    _mkfile(tmp_path / "pyproject.toml", 'dependencies = [\n  "mylib @ git+https://example.com/mylib.git",\n]\n')
    walk = _walk(tmp_path)
    result = dependencies.analyze(walk, config=config)
    assert any("unpinned" in f.title for f in result.findings)


def test_dependencies_pinned_vcs_no_finding(tmp_path, config):
    _mkfile(tmp_path / "pyproject.toml", 'dependencies = [\n  "mylib @ git+https://example.com/mylib.git@abc123",\n]\n')
    walk = _walk(tmp_path)
    result = dependencies.analyze(walk, config=config)
    assert not any("unpinned" in f.title for f in result.findings)


# --- RepositoryHygieneAnalyzer -----------------------------------------------


def test_repository_hygiene_flags_missing_gitignore(tmp_path, config):
    _mkfile(tmp_path / "a.py")
    walk = _walk(tmp_path)
    result = repository_hygiene.analyze(walk, config=config)
    assert any("missing .gitignore" in f.title for f in result.findings)


def test_repository_hygiene_gitignore_present_no_missing_finding(tmp_path, config):
    _mkfile(tmp_path / ".gitignore", "dist/\nbuild/\n")
    walk = _walk(tmp_path)
    result = repository_hygiene.analyze(walk, config=config)
    assert not any("missing .gitignore" in f.title for f in result.findings)


def test_repository_hygiene_flags_env_file(tmp_path, config):
    _mkfile(tmp_path / ".env", "SECRET=1\n")
    walk = _walk(tmp_path)
    result = repository_hygiene.analyze(walk, config=config)
    assert any(".env" in f.title for f in result.findings)


# --- DeveloperExperienceAnalyzer ---------------------------------------------


def test_developer_experience_flags_missing_packaging(tmp_path, config):
    _mkfile(tmp_path / "main.py", "def main():\n    return 0\n")
    walk = _walk(tmp_path)
    result = developer_experience.analyze(walk, config=config)
    assert any("packaging" in f.title for f in result.findings)


def test_developer_experience_ignores_tooling_only_python_in_static_web_game(tmp_path, config):
    _mkfile(tmp_path / "index.html", "<main id='game'></main>\n")
    _mkfile(tmp_path / "src" / "game.js", "export const start = () => {};\n")
    _mkfile(tmp_path / "src" / "boss.js", "export const boss = {};\n")
    _mkfile(tmp_path / "src" / "weapons.js", "export const weapons = [];\n")
    _mkfile(tmp_path / "assets" / "player.png")
    _mkfile(tmp_path / "assets" / "boss.png")
    _mkfile(tmp_path / "tools" / "benchmark.py", "def benchmark():\n    return 1\n")
    _mkfile(tmp_path / "tests" / "benchmark_runner.py", "def test_benchmark():\n    assert True\n")

    result = developer_experience.analyze(_walk(tmp_path), config=config)

    assert not any("no standard Python packaging" in f.title for f in result.findings)


def test_developer_experience_flags_missing_packaging_for_python_package(tmp_path, config):
    _mkfile(tmp_path / "game" / "__init__.py", "")
    _mkfile(tmp_path / "game" / "boss.py", "class Boss:\n    pass\n")

    result = developer_experience.analyze(_walk(tmp_path), config=config)

    assert any("no standard Python packaging" in f.title for f in result.findings)


def test_developer_experience_flags_missing_packaging_for_mixed_python_package(tmp_path, config):
    _mkfile(tmp_path / "index.html", "<main id='game'></main>\n")
    _mkfile(tmp_path / "src" / "game.js", "export const start = () => {};\n")
    _mkfile(tmp_path / "service" / "__init__.py", "")
    _mkfile(tmp_path / "service" / "combat.py", "def apply_damage():\n    return 1\n")

    result = developer_experience.analyze(_walk(tmp_path), config=config)

    assert any("no standard Python packaging" in f.title for f in result.findings)


def test_developer_experience_packaging_present_no_finding(tmp_path, config):
    _mkfile(tmp_path / "pyproject.toml", "[project]\nname='x'\n")
    walk = _walk(tmp_path)
    result = developer_experience.analyze(walk, config=config)
    assert not any("no standard Python packaging" in f.title for f in result.findings)


def test_developer_experience_flags_missing_contributing(tmp_path, config):
    walk = _walk(tmp_path)
    result = developer_experience.analyze(walk, config=config)
    assert any("CONTRIBUTING" in f.title for f in result.findings)


# --- AIAgentReadinessAnalyzer -------------------------------------------------


def test_ai_agent_readiness_flags_missing_doc(tmp_path, config):
    walk = _walk(tmp_path)
    result = ai_agent_readiness.analyze(walk, config=config)
    assert any("agent-facing instructions" in f.title for f in result.findings)


def test_ai_agent_readiness_doc_present_no_finding(tmp_path, config):
    _mkfile(tmp_path / "AGENTS.md", "# agents\n")
    walk = _walk(tmp_path)
    result = ai_agent_readiness.analyze(walk, config=config)
    assert not any("agent-facing instructions" in f.title for f in result.findings)


def test_ai_agent_readiness_flags_nondeterministic_calls(tmp_path, config):
    _mkfile(tmp_path / "src" / "mod.py", "import random\n\ndef f():\n    return random.random()\n")
    walk = _walk(tmp_path)
    result = ai_agent_readiness.analyze(walk, config=config)
    assert any("non-deterministic" in f.title for f in result.findings)


def test_ai_agent_readiness_ignores_nondeterminism_in_tests(tmp_path, config):
    _mkfile(tmp_path / "tests" / "test_mod.py", "import random\n\ndef test_f():\n    random.random()\n")
    walk = _walk(tmp_path)
    result = ai_agent_readiness.analyze(walk, config=config)
    assert not any("non-deterministic" in f.title for f in result.findings)
