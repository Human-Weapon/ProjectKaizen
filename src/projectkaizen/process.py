"""Cross-platform process-tree execution with bounded stdout/stderr.

Verification commands execute with the caller's normal permissions.
``shell=False`` is not a sandbox.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence

from .exceptions import ConfigurationError, ValidationError
from .numbers import require_int, require_number

DEFAULT_MAX_OUTPUT_BYTES = 1_048_576
_CHUNK = 65_536


def validate_argv(argv: Sequence[str]) -> tuple[str, ...]:
    if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
        raise ConfigurationError("verification command argv must be a list of strings")
    if not argv:
        raise ConfigurationError("verification command argv must not be empty")
    out: list[str] = []
    for item in argv:
        if not isinstance(item, str):
            raise ConfigurationError("verification command argv entries must be strings")
        if item == "":
            raise ConfigurationError("verification command argv entries must not be empty")
        out.append(item)
    return tuple(out)


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:  # pragma: no cover - already reaped
        return
    if os.name == "nt":
        taskkill = shutil.which("taskkill") or "taskkill"
        subprocess.run(  # noqa: S603
            [taskkill, "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            shell=False,
        )
    else:  # pragma: no cover - POSIX
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            with contextlib.suppress(OSError):
                proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover - stubborn child
        with contextlib.suppress(OSError):
            proc.kill()


def run_bounded(
    argv: Sequence[str],
    *,
    cwd: str | None,
    env: Mapping[str, str] | None,
    timeout: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> tuple[int | None, bytes, bytes, bool, bool, bool, float]:
    """Run argv in a new process group.

    Returns (exit_code, stdout, stderr, timed_out, stdout_truncated,
    stderr_truncated, duration).
    """
    command = validate_argv(argv)
    timeout = require_number(timeout, name="timeout_seconds", minimum=0.0, allow_zero=False)
    max_stdout_bytes = require_int(max_stdout_bytes, name="max_stdout_bytes", minimum=0)
    max_stderr_bytes = require_int(max_stderr_bytes, name="max_stderr_bytes", minimum=0)
    kwargs: dict = {
        "args": list(command),
        "cwd": cwd,
        "env": dict(env) if env is not None else None,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": False,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:  # pragma: no cover - POSIX
        kwargs["start_new_session"] = True

    started = time.perf_counter()
    try:
        proc = subprocess.Popen(**kwargs)  # noqa: S603
    except OSError as exc:
        raise ValidationError(f"cannot start verification command: {exc}") from exc

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    flags = {"out": False, "err": False}

    def _reader(stream: object, chunks: list[bytes], limit: int, key: str) -> None:
        kept = 0
        try:
            while True:
                data = stream.read(_CHUNK)  # type: ignore[union-attr]
                if not data:
                    break
                if kept < limit:
                    take = data[: limit - kept]
                    leftover = data[len(take) :]
                    chunks.append(take)
                    kept += len(take)
                    if leftover:
                        flags[key] = True
                else:
                    flags[key] = True
        except OSError:  # pragma: no cover - reader teardown
            return

    t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_chunks, max_stdout_bytes, "out"), daemon=True)
    t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_chunks, max_stderr_bytes, "err"), daemon=True)
    t_out.start()
    t_err.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
    t_out.join(timeout=5)
    t_err.join(timeout=5)
    duration = time.perf_counter() - started
    code = proc.poll()
    return (
        None if timed_out else code,
        b"".join(stdout_chunks),
        b"".join(stderr_chunks),
        timed_out,
        flags["out"],
        flags["err"],
        duration,
    )
