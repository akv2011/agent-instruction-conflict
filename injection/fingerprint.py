"""A hash over everything that could change a rollout's meaning.

Pooling is only sound if nothing behaviour-relevant changed between rollouts, so
every rollout records one and pooling is refused across mismatches.
"""

import hashlib
import json
from typing import Any

FIELDS = (
    "cell_name",
    "injection_path",
    "injection_content",
    "system_prompt",
    "user_prompt",
    "model",
    "provider",
    "max_steps",
    "target_errors",
    "tools",
    "temperature",
    "top_p",
)


def fingerprint(cell, config: dict[str, Any]) -> str:
    """Stable 16-hex-char digest of the behaviour-relevant configuration."""
    agent = config.get("agent", {})
    task = config.get("task", {})
    prompts = config.get("prompts", {})
    payload = {
        "cell_name": cell.name,
        "injection_path": cell.injection_path,
        "injection_content": cell.injection_content,
        "system_prompt": prompts.get("system_prompt", ""),
        "user_prompt": prompts.get("user_prompt", ""),
        "model": agent.get("model"),
        "provider": agent.get("provider"),
        "max_steps": agent.get("max_steps"),
        "target_errors": task.get("target_errors"),
        "tools": sorted(task.get("tools") or []),
        "temperature": agent.get("temperature"),
        "top_p": agent.get("top_p"),
    }
    if set(payload) != set(FIELDS):
        raise AssertionError("fingerprint fields drifted from FIELDS")
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def poolable(rows: list[dict]) -> tuple[bool, dict[str, int]]:
    """Whether a set of recorded rollouts may be analysed together."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["fingerprint"]] = counts.get(row["fingerprint"], 0) + 1
    return len(counts) <= 1, counts
