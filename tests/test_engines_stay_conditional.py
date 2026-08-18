"""NO UNUSED ENGINE EXECUTION: git_hotspots, blast_radius, the preservation
gate, root_cause strategies, statistics, and scale/decomposition must never
be pulled in by a default CLI command that didn't ask for them.

Checked via a real, fresh subprocess (not `sys.modules` inspection in the
same pytest session, which would already have every module loaded from
other test files and prove nothing).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

_CHECK_SCRIPT = textwrap.dedent(
    """
    import sys
    import projectkaizen.cli as cli

    cli.main(["inspect", "."])

    watched = [
        "projectkaizen.analyzers.git_hotspots",
        "projectkaizen.blast_radius",
        "projectkaizen.gates.preservation",
        "projectkaizen.gates.fresh_evidence",
        "projectkaizen.root_cause",
        "projectkaizen.statistics",
        "projectkaizen.scale.decomposition",
    ]
    for name in watched:
        print(f"{name}={name in sys.modules}")
    """
)


def test_inspect_does_not_load_optional_engines(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _CHECK_SCRIPT.replace('"."', repr(str(tmp_path)))],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(tmp_path),
    )
    lines = {line.split("=")[0]: line.split("=")[1] for line in result.stdout.strip().splitlines() if "=" in line}
    assert lines, f"script produced no output; stderr: {result.stderr}"
    for module_name, loaded in lines.items():
        assert loaded == "False", f"{module_name} was loaded by `inspect`, but nothing requested it"


def test_release_readiness_does_not_load_root_cause_or_statistics(tmp_path):
    script = textwrap.dedent(
        f"""
        import sys
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd={str(tmp_path)!r}, check=True)
        import projectkaizen.cli as cli
        cli.main(["release-readiness", {str(tmp_path)!r}])
        for name in ["projectkaizen.root_cause", "projectkaizen.statistics", "projectkaizen.analyzers.git_hotspots"]:
            print(f"{{name}}={{name in sys.modules}}")
        """
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    lines = {line.split("=")[0]: line.split("=")[1] for line in result.stdout.strip().splitlines() if "=" in line}
    assert lines, f"script produced no output; stderr: {result.stderr}"
    for module_name, loaded in lines.items():
        assert loaded == "False", f"{module_name} was loaded by release-readiness, but nothing requested it"


def test_git_hotspots_not_in_default_analyzer_registry():
    from projectkaizen.analyzers import ALL_ANALYZERS

    assert "git_hotspots" not in {name.lower() for name in ALL_ANALYZERS}
