"""Score the 5 Fit dimensions against the user's local data.

Inputs:
  - skill_md text (already fetched)
  - claude_home path (default ~/.claude)

Reads:
  - <claude_home>/history.jsonl  — last 90 days, capped at 5000 most-recent entries
  - <claude_home>/skills/        — directory listing for installed-slug set
  - shutil.which(...) for binary probes

Returns FitResult with 5 sub-scores 0-100 + total + matched evidence.

See references/scoring-algorithm.md for exact math.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telemetry import SessionContext


@dataclass
class FitResult:
    relevance: float | None = None  # 相关
    demand: float | None = None     # 需求
    recency: float | None = None    # 时效
    gap: float | None = None        # 缺口
    fit_env: float | None = None    # 适配
    total: float | None = None
    matched_terms: list[str] = field(default_factory=list)
    matched_count: int = 0
    has_history: bool = False
    needs_bins: list[str] = field(default_factory=list)
    missing_bins: list[str] = field(default_factory=list)


def score_fit(skill_md: str, claude_home: Path, ctx: "SessionContext | None" = None) -> FitResult:
    """TODO(task #13): port logic from legacy packaging/skillsvote/scorer.py + assess.py.

    Algorithm sketch (see references/scoring-algorithm.md for full):
      1. Tokenize skill_md vocabulary (lowercase, dedupe, drop stopwords).
      2. Load history.jsonl → list of user prompts (90d window, 5000 cap).
         If absent: return all dims None except gap+fit_env, has_history=False.
      3. relevance = TF-IDF cosine(skill_terms, history_terms) → 0-100
      4. demand    = count(prompts containing any skill_term, decay-weighted) → 0-100
      5. recency   = freshness of matched prompts (recent ones weigh more) → 0-100
      6. gap       = 100 - overlap(this skill's slug-keywords, installed skills) → 0-100
      7. fit_env   = % of required-bins present on PATH → 0-100
      8. total     = mean of available dims

    Telemetry: score_fit_started, score_fit_done(latency, has_history, total_bucket).
    """
    raise NotImplementedError("score_fit.py — implement in task #13")
