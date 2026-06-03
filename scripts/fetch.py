"""Fetch a skill's SKILL.md given a URL or local path.

Resolves any of:
  - GitHub repo root         → look for SKILL.md at default branch root
  - GitHub folder            → look for SKILL.md inside that folder
  - GitHub blob/raw URL      → fetch as-is
  - skills.vote page         → follow to underlying GitHub link
  - Local filesystem path    → read directly

Returns: (skill_md_text, meta_dict)
    meta = {"slug": str, "source_url": str, "size": int, "fetched_at": iso8601}
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telemetry import SessionContext

MAX_SIZE_BYTES = 200_000
TRUNCATE_TO_BYTES = 50_000


@dataclass
class SkillMeta:
    slug: str
    source_url: str
    size: int
    fetched_at: str


def fetch_skill(url: str, ctx: "SessionContext | None" = None) -> tuple[str, SkillMeta]:
    """TODO(task #13): real implementation.

    Steps:
      1. Classify URL shape (github repo / github folder / raw / skills.vote / local).
      2. Resolve to a raw SKILL.md URL (or local path).
      3. HTTP GET with 15s timeout; retry once at 30s on timeout.
      4. Reject if >MAX_SIZE_BYTES; warn and truncate to TRUNCATE_TO_BYTES.
      5. Return (text, SkillMeta).

    Telemetry emits: fetch_start, fetch_done(latency_ms, size_bucket).
    """
    raise NotImplementedError("fetch.py — implement in task #13")
