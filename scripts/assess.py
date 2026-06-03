#!/usr/bin/env python3
"""Main entry: orchestrate fetch → score_fit → score_quality → render → telemetry.

Usage:
    python assess.py <URL>
    python assess.py <URL> --claude-home ~/.claude --no-telemetry
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Force UTF-8 stdout so emoji-bearing verdict blocks render on Windows consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass
from pathlib import Path

from fetch import fetch_skill
from render import render_verdict
from score_fit import score_fit
from score_quality import score_quality
from telemetry import emit, session_context


def main() -> int:
    parser = argparse.ArgumentParser(description="SkillsVote — should I install this skill?")
    parser.add_argument("url", help="GitHub repo / folder / SKILL.md / skills.vote URL, or local path")
    parser.add_argument("--claude-home", default=os.path.expanduser("~/.claude"),
                        help="Host agent home dir (default: ~/.claude). For Cursor use ~/.cursor.")
    parser.add_argument("--no-telemetry", action="store_true",
                        help="Disable telemetry for this run (or set env SKILLSVOTE_NO_TELEMETRY=1)")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON instead of Markdown")
    args = parser.parse_args()

    telemetry_off = args.no_telemetry or os.environ.get("SKILLSVOTE_NO_TELEMETRY") == "1"
    ctx = session_context(disabled=telemetry_off)

    t0 = time.monotonic()
    emit(ctx, "assess_started", {"url_shape": _classify_url(args.url)})

    try:
        skill_md, meta = fetch_skill(args.url, ctx=ctx)
    except Exception as exc:
        emit(ctx, "fetch_failed", {"err": type(exc).__name__})
        print(f"❌ fetch failed: {exc}", file=sys.stderr)
        return 2

    fit = score_fit(skill_md, claude_home=Path(args.claude_home), ctx=ctx)
    quality = score_quality(skill_md, ctx=ctx)

    output = render_verdict(skill_md=skill_md, meta=meta, fit=fit, quality=quality,
                            json_mode=args.json)
    print(output)

    emit(ctx, "verdict_emitted", {
        "verdict": _verdict_label(fit.total, quality.total),
        "fit_bucket": _bucket(fit.total),
        "quality_bucket": _bucket(quality.total),
        "latency_ms": int((time.monotonic() - t0) * 1000),
    })
    return 0


def _classify_url(url: str) -> str:
    """Coarse URL shape for telemetry (no skill name leaked)."""
    if url.startswith("http"):
        if "github.com" in url:
            return "github"
        if "skills.vote" in url:
            return "skills_vote"
        return "http_other"
    if os.path.exists(url):
        return "local_path"
    return "unknown"


def _bucket(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 85:
        return "85-100"
    if score >= 70:
        return "70-84"
    if score >= 50:
        return "50-69"
    return "0-49"


def _verdict_label(fit: float | None, quality: float | None) -> str:
    if fit is None:
        return "not-enough-history"
    fit_high, q_high = fit >= 70, (quality or 0) >= 70
    if fit_high and q_high:
        return "install"
    if fit_high and not q_high:
        return "install-with-caveat"
    if not fit_high and q_high:
        return "save-for-later"
    return "skip"


if __name__ == "__main__":
    sys.exit(main())
