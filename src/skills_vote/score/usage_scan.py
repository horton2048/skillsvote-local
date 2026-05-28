from __future__ import annotations

import json
import time
from pathlib import Path

from skills_vote.score.model import UserProfile
from skills_vote.score.tokenize import extract_slash_commands, tokenize


def default_claude_home() -> Path:
    return Path.home() / ".claude"


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
            yield text, int(timestamp) if isinstance(timestamp, int | float) else None


def scan_user_profile(
    claude_home: Path | None = None,
    *,
    max_prompts: int | None = None,
    now_ms: int | None = None,
) -> UserProfile:
    """Build a lexical UserProfile from local Claude Code usage history.

    Reads ``<claude_home>/history.jsonl`` (the user's prompt log). Each prompt
    becomes a document in an inverted index; slash-commands are tracked so the
    scorer can tell which skills the user already reaches for.
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
