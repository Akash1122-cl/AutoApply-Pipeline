from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def run_lock(lock_path: Path) -> Iterator[None]:
    """
    Cross-process lock using exclusive file creation.
    If lock file exists, another run is active.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    acquired = False
    try:
        with lock_path.open("x", encoding="utf-8") as fp:
            fp.write("locked")
        acquired = True
        yield
    except FileExistsError as exc:
        raise RuntimeError(f"Another orchestrator run is active: {lock_path}") from exc
    finally:
        if acquired and lock_path.exists():
            lock_path.unlink()
