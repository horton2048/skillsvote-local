"""Build a lexical UserProfile from local Claude Code usage history.

Reads ``<claude_home>/history.jsonl`` and inverts it into a per-token posting
list so the scorer can answer "which prompts mention this term" in O(1).

Dependency-free (stdlib only); pydantic removed during the skill port.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from lex import extract_slash_commands, tokenize


def default_claude_home() -> Path:
    return Path.home() / ".claude"


@dataclass
class UserProfile:
    """Lexical fingerprint of how the user actually drives the host agent."""

    prompt_count: int
    postings: dict[str, list[int]] = field(default_factory=dict)
    prompt_timestamps: list[int] = field(default_factory=list)
    used_slugs: dict[str, int] = field(default_factory=dict)
    now_ms: int = 0
    sample_prompts: list[str] = field(default_factory=list)

    def doc_freq(self, token: str) -> int:
        return len(self.postings.get(token, ()))


def _iter_history_records(history_path: Path):
    with history_path.open(encoding="utf-8", errors="replace") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            text = record.get("display")
            if not isinstance(text, str) or not text.strip():
                continue
            timestamp = record.get("timestamp")
            yield text, int(timestamp) if isinstance(timestamp, (int, float)) else None


def scan_user_profile(
    claude_home: Path | None = None,
    *,
    max_prompts: int | None = 5000,
    now_ms: int | None = None,
) -> UserProfile:
    """Build a lexical UserProfile from ``<claude_home>/history.jsonl``.

    If the file does not exist, returns an empty profile (prompt_count=0). The
    caller should treat empty profile as "no history" and gracefully degrade
    relevance/demand/recency dims to ``None``.
    """
    home = claude_home or default_claude_home()
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    history_path = home / "history.jsonl"

    postings: dict[str, list[int]] = {}
    timestamps: list[int] = []
    used_slugs: dict[str, int] = {}
    samples: list[str] = []

    if history_path.exists():
        records = list(_iter_history_records(history_path))
        if max_prompts is not None and len(records) > max_prompts:
            records = records[-max_prompts:]
        for idx, (text, ts) in enumerate(records):
            timestamps.append(ts if ts is not None else now)
            for slug in extract_slash_commands(text):
                used_slugs[slug] = used_slugs.get(slug, 0) + 1
            seen: set[str] = set()
            for token in tokenize(text):
                if token in seen:
                    continue
                seen.add(token)
                postings.setdefault(token, []).append(idx)
            if len(samples) < 12:
                samples.append(text.strip()[:120])

    return UserProfile(
        prompt_count=len(timestamps),
        postings=postings,
        prompt_timestamps=timestamps,
        used_slugs=used_slugs,
        now_ms=now,
        sample_prompts=samples,
    )


def list_installed_skill_slugs(claude_home: Path | None = None) -> list[str]:
    """Slugs of every skill directory found under ``<claude_home>/skills/``."""
    home = claude_home or default_claude_home()
    skills_dir = home / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(
        p.name for p in skills_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
