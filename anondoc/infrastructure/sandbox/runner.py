"""
Runs document operations in a separate, resource-limited, environment-scrubbed process.

Controls: wall-clock timeout with process-group kill, RLIMIT_AS/CPU/FSIZE/NOFILE/CORE,
empty environment, cwd restricted to the job directory, bounded concurrency,
no shell, arguments never derived from user input.
"""
import json
import os
import resource
import signal
import subprocess  # nosec B404
import sys
import threading
from pathlib import Path
from typing import Any, Dict

from anondoc.config import AppConfig

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
_slots = threading.BoundedSemaphore(AppConfig.MAX_CONCURRENT_JOBS)
ACQUIRE_TIMEOUT_SECONDS = 5


class WorkerError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ServerBusy(Exception):
    pass


def _limits():
    def apply():
        os.setsid()
        mem = AppConfig.WORKER_MEMORY_BYTES
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (AppConfig.WORKER_CPU_SECONDS, AppConfig.WORKER_CPU_SECONDS))
        fsize = AppConfig.MAX_FILE_SIZE_BYTES * 4
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def build_env(cwd: str) -> Dict[str, str]:
    """Minimal environment: nothing from the API process (secrets, config, tokens) is inherited."""
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": PROJECT_ROOT,
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
        "HOME": cwd,
        "TMPDIR": cwd,
    }
    # Only numeric inspection limits are forwarded so the worker enforces the same limits as the API.
    for key, value in os.environ.items():
        if key.startswith("ANONDOC_MAX_") and value.replace(".", "", 1).isdigit():
            env[key] = value
    return env


def run_worker(request: Dict[str, Any], cwd: str) -> Dict[str, Any]:
    if not _slots.acquire(timeout=ACQUIRE_TIMEOUT_SECONDS):
        raise ServerBusy()
    proc = None
    try:
        env = build_env(cwd)
        proc = subprocess.Popen(  # nosec B603
            [sys.executable, "-s", "-P", "-m", "anondoc.worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            env=env,
            preexec_fn=_limits(),  # noqa: PLW1509
            close_fds=True,
        )
        try:
            out, _ = proc.communicate(json.dumps(request).encode(), timeout=AppConfig.WORKER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            _kill(proc)
            raise WorkerError("timeout", "El procesamiento excedió el tiempo máximo permitido.")

        if proc.returncode != 0 or len(out) > AppConfig.WORKER_MAX_OUTPUT_BYTES:
            raise WorkerError("resource_limit", "El documento excede los recursos permitidos.")
        try:
            resp = json.loads(out)
        except ValueError:
            raise WorkerError("processing_error", "No se pudo procesar el documento.")
        if not resp.get("ok"):
            raise WorkerError(resp.get("code", "processing_error"), resp.get("message", "No se pudo procesar el documento."))
        return resp
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc)
        _slots.release()


def _kill(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait()
