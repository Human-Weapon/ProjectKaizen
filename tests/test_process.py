from __future__ import annotations

import sys

import pytest

from projectkaizen.exceptions import ConfigurationError, ValidationError
from projectkaizen.process import run_bounded, validate_argv


def test_validate_argv_accepts_list_of_strings():
    assert validate_argv(["a", "b"]) == ("a", "b")


def test_validate_argv_rejects_string():
    with pytest.raises(ConfigurationError):
        validate_argv("not a list")


def test_validate_argv_rejects_empty():
    with pytest.raises(ConfigurationError):
        validate_argv([])


def test_validate_argv_rejects_non_string_entries():
    with pytest.raises(ConfigurationError):
        validate_argv(["a", 1])


def test_validate_argv_rejects_empty_string_entry():
    with pytest.raises(ConfigurationError):
        validate_argv(["a", ""])


def test_run_bounded_real_process_success():
    code, out, err, timed_out, out_trunc, err_trunc, duration = run_bounded(
        [sys.executable, "-c", "print('hello')"],
        cwd=None,
        env=None,
        timeout=10.0,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    assert code == 0
    assert b"hello" in out
    assert timed_out is False
    assert out_trunc is False
    assert duration >= 0


def test_run_bounded_nonzero_exit():
    code, _out, _err, timed_out, *_ = run_bounded(
        [sys.executable, "-c", "import sys; sys.exit(3)"],
        cwd=None,
        env=None,
        timeout=10.0,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    assert code == 3
    assert timed_out is False


def test_run_bounded_stdout_truncation():
    code, out, _err, _timed_out, out_trunc, _err_trunc, _duration = run_bounded(
        [sys.executable, "-c", "print('x' * 1000)"],
        cwd=None,
        env=None,
        timeout=10.0,
        max_stdout_bytes=10,
        max_stderr_bytes=1024,
    )
    assert len(out) == 10
    assert out_trunc is True


def test_run_bounded_timeout_kills_descendant_and_reaps():
    code, _out, _err, timed_out, *_ = run_bounded(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=None,
        env=None,
        timeout=0.3,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    assert timed_out is True
    assert code is None


def test_run_bounded_descendant_holding_pipe_open_does_not_hang():
    # The child exits but leaves stdout/stderr effectively closed with it
    # (no grandchild keeps the pipe open on our supported platforms via
    # CREATE_NEW_PROCESS_GROUP / start_new_session), so this must return
    # promptly rather than blocking on the reader threads forever.
    code, out, _err, timed_out, *_ = run_bounded(
        [sys.executable, "-c", "print('done')"],
        cwd=None,
        env=None,
        timeout=5.0,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    assert timed_out is False
    assert code == 0
    assert b"done" in out


def test_run_bounded_missing_executable_raises_validation_error():
    with pytest.raises(ValidationError):
        run_bounded(
            ["this-executable-does-not-exist-xyz"],
            cwd=None,
            env=None,
            timeout=5.0,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
        )


def test_run_bounded_respects_cwd(tmp_path):
    marker = tmp_path / "marker.txt"
    marker.write_text("present")
    code, out, _err, _timed_out, *_ = run_bounded(
        [sys.executable, "-c", "import os; print(os.path.exists('marker.txt'))"],
        cwd=str(tmp_path),
        env=None,
        timeout=10.0,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    assert code == 0
    assert b"True" in out


def test_run_bounded_respects_env(monkeypatch):
    code, out, _err, _timed_out, *_ = run_bounded(
        [sys.executable, "-c", "import os; print(os.environ.get('KAIZEN_TEST_VAR'))"],
        cwd=None,
        env={"KAIZEN_TEST_VAR": "hello-env"},
        timeout=10.0,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    assert code == 0
    assert b"hello-env" in out
