from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _is_pid_running(pid: int) -> bool:
    """Check if a process ID is running on Windows or Unix."""
    if sys.platform.startswith("win"):
        try:
            import subprocess
            output = subprocess.check_output(
                f'tasklist /FI "PID eq {pid}"', shell=True
            ).decode("utf-8", errors="ignore")
            return str(pid) in output
        except Exception:
            return True  # Safe fallback
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


@contextmanager
def run_lock(lock_path: Path) -> Iterator[None]:
    """
    Cross-process lock using exclusive file creation.
    If lock file exists, check if process is still active. If not, auto-heal.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    acquired = False
    
    # Try to acquire lock, handle stale locks
    try:
        with lock_path.open("x", encoding="utf-8") as fp:
            fp.write(str(os.getpid()))
        acquired = True
        yield
    except FileExistsError as exc:
        # Read the PID from the existing lock file
        content = "unknown"
        try:
            with lock_path.open("r", encoding="utf-8") as fp:
                content = fp.read().strip()
                pid = int(content)
        except Exception:
            pid = None

        is_stale = (pid is None) or not _is_pid_running(pid)

        if is_stale:
            print(f"WARNING: Stale orchestrator lock detected (content: {content}). Removing stale lock and retrying...")
            try:
                lock_path.unlink(missing_ok=True)
            except Exception:
                pass
            
            # Retry acquisition
            with lock_path.open("x", encoding="utf-8") as fp:
                fp.write(str(os.getpid()))
            acquired = True
            yield
        else:
            raise RuntimeError(
                f"Another orchestrator run is active (PID {pid if pid else 'unknown'}): {lock_path}"
            ) from exc
    finally:
        if acquired and lock_path.exists():
            try:
                # Only delete if we own it
                with lock_path.open("r", encoding="utf-8") as fp:
                    content = fp.read().strip()
                    owner_pid = int(content)
            except Exception:
                owner_pid = None
                
            if owner_pid == os.getpid():
                lock_path.unlink()

