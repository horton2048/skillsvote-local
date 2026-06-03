"""Static-analysis quality score on a SKILL.md (3 condensed dims from darwin's 9).

Inputs:
  - skill_md text

Returns QualityResult with 3 sub-scores 0-100 + total + per-dim reasons.

See references/scoring-algorithm.md for the rule set per dim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telemetry import SessionContext


@dataclass
class QualityResult:
    form: float = 0.0           # 写法 (darwin 1+2+7)
    robustness: float = 0.0     # 稳健 (darwin 3+4+9)
    executable: float = 0.0     # 可执行 (darwin 5+6)
    total: float = 0.0
    reasons: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def score_quality(skill_md: str, ctx: "SessionContext | None" = None) -> QualityResult:
    """TODO(task #14): implement static analysis.

    form (0-100)        — darwin 1+2+7:
      - YAML frontmatter parses, has name + description
      - description length 64-1024 chars
      - description does NOT end with "灵活应用 / 根据情况判断 / case by case" (empty hedge tail)
      - body has H2/H3 section structure
      - ordered steps (1./2./3. or "Step 1") detected
      - no >5 consecutive blank lines (AI-slop tell)

    robustness (0-100)  — darwin 3+4+9:
      - explicit "if X then Y" / "if X, fallback to Y" patterns counted
      - visible CHECKPOINT markers (🔴 / STOP / CHECKPOINT) counted
      - anti-pattern / blacklist / "do NOT" section present
      - destructive-op warnings (rm -rf / git reset --hard / force push) explicitly addressed

    executable (0-100)  — darwin 5+6:
      - "vague hedge" word density (建议/可以考虑/视情况/suggest/consider) — ≥3 in body subtracts
      - code blocks / concrete commands ratio
      - resource refs (scripts/.../references/...) exist and paths resolve

    Warnings (no score deduction, just flags):
      - runtime drift: "Claude Code" appears outside frontmatter triggers

    Telemetry: score_quality_done(latency, total_bucket, has_checkpoints, has_blacklist).
    """
    raise NotImplementedError("score_quality.py — implement in task #14")
