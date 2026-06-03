"""Render the conversation-flow verdict block.

Produces Markdown matching references/output-format.md, or raw JSON if json_mode.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fetch import SkillMeta
    from score_fit import FitResult
    from score_quality import QualityResult


def render_verdict(skill_md: str, meta: "SkillMeta", fit: "FitResult",
                   quality: "QualityResult", json_mode: bool = False) -> str:
    """TODO(task #15): render Markdown per references/output-format.md.

    Sections:
      1. Header:  ## <slug> · **<total>/100 · <verdict label>**
      2. Two-column dim table (Fit 5 rows | Quality 3 rows)
      3. "为什么 <verdict>" — 1-2 sentence ground in matched_terms / missing_bins / installed-skill clash
      4. "⚠️ 隐忧" — if any Quality dim < 60 OR has_history=False
      5. "💡 一键安装" — copy-paste prompt block adapted to user env
    """
    if json_mode:
        return json.dumps({
            "meta": meta.__dict__,
            "fit": fit.__dict__,
            "quality": quality.__dict__,
        }, ensure_ascii=False, indent=2)
    raise NotImplementedError("render.py — implement in task #15")
