from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class RunLogger:
    """Phase 1 run-level metadata logger."""

    log_dir: Path = field(default_factory=lambda: Path("logs"))
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=_utc_now_iso)
    ended_at: str = ""
    agent_counts: Dict[str, int] = field(default_factory=dict)
    errors: list[Dict[str, Any]] = field(default_factory=list)

    def increment(self, agent_name: str, count: int = 1) -> None:
        self.agent_counts[agent_name] = self.agent_counts.get(agent_name, 0) + count

    def get_count(self, agent_name: str) -> int:
        return self.agent_counts.get(agent_name, 0)

    def record_error(self, job_id: str, agent_name: str, message: str) -> None:
        self.errors.append(
            {
                "timestamp": _utc_now_iso(),
                "job_id": job_id,
                "agent_name": agent_name,
                "message": message,
            }
        )

    def close(self) -> Path:
        self.ended_at = _utc_now_iso()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        output = self.log_dir / f"run-{self.run_id}.json"
        output.write_text(
            json.dumps(
                {
                    "run_id": self.run_id,
                    "started_at": self.started_at,
                    "ended_at": self.ended_at,
                    "agent_counts": self.agent_counts,
                    "errors": self.errors,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return output
