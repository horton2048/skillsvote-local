"""Score the 5 Fit dimensions against the user's local data.

Ported from packaging/skillsvote/scorer.py — same algorithm, with the
適配/fit dim upgraded from OS-only to OS + required-bin presence check.

See references/scoring-algorithm.md for the math behind each dim.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from lex import tokenize
from usage_scan import (
    UserProfile,
    list_installed_skill_slugs,
    scan_user_profile,
)

if TYPE_CHECKING:
    from telemetry import SessionContext

_DAY_MS = 86_400_000

# Algorithm constants (ported from original ScoreConfig defaults).
_DEMAND_SATURATION = 25
_RECENCY_HALF_LIFE_DAYS = 30.0
_DISTINCTIVE_IDF_RATIO = 0.35
_ALREADY_HAVE_GAP = 0.2


@dataclass
class FitResult:
    relevance: float | None = None   # 相关 (0-100)
    demand: float | None = None      # 需求 (0-100)
    recency: float | None = None     # 时效 (0-100)
    gap: float | None = None         # 缺口 (0-100)
    fit_env: float | None = None     # 适配 (0-100)
    total: float | None = None       # mean of available dims (0-100)
    matched_terms: list[str] = field(default_factory=list)
    matched_prompt_count: int = 0
    last_used_days_ago: float | None = None
    already_have: bool = False
    has_history: bool = False
    needs_bins: list[str] = field(default_factory=list)
    missing_bins: list[str] = field(default_factory=list)
    os_compatible: bool = True
    reason: str = ""


# ----------------------------- public entry ----------------------------------


def score_fit(
    skill_md: str,
    *,
    claude_home: Path | None = None,
    skill_slug: str | None = None,
    ctx: "SessionContext | None" = None,
) -> FitResult:
    """Compute Fit (5 dims) for one skill against the user's local data."""
    t0 = time.monotonic()
    if ctx is not None:
        from telemetry import emit  # local import to avoid cycle on test
        emit(ctx, "score_fit_started")

    profile = scan_user_profile(claude_home=claude_home)
    has_history = profile.prompt_count > 0

    # Extract candidate skill's lexical surface and metadata.
    skill_tokens = set(tokenize(skill_md))
    slug = skill_slug or _infer_slug_from_skill_md(skill_md) or "unknown"
    required_bins = _extract_required_bins(skill_md)
    os_constraint = _extract_os_constraint(skill_md)

    result = FitResult(
        has_history=has_history,
        needs_bins=required_bins,
    )

    # ---- relevance / demand / recency need history -----------------------
    if has_history and skill_tokens:
        idf = _build_idf(profile)
        max_idf = max(idf.values(), default=1.0)

        # relevance: IDF-weighted overlap fraction.
        total_w, matched_w, matched_pairs = 0.0, 0.0, []
        for tok in skill_tokens:
            w = idf.get(tok, max_idf)
            total_w += w
            if tok in profile.postings:
                matched_w += w
                matched_pairs.append((tok, w))
        relevance01 = (matched_w / total_w) if total_w > 0 else 0.0

        # Filter to distinctive matches before counting prompts.
        idf_floor = _DISTINCTIVE_IDF_RATIO * max_idf
        distinctive = [t for t, w in matched_pairs if w >= idf_floor]
        demand_tokens = distinctive or [t for t, _ in matched_pairs]
        matched_idx: set[int] = set()
        for tok in demand_tokens:
            matched_idx.update(profile.postings.get(tok, ()))
        result.matched_prompt_count = len(matched_idx)
        result.matched_terms = [
            t for t, _ in sorted(matched_pairs, key=lambda x: x[1], reverse=True)
        ][:6]

        # demand: log-saturated count.
        demand01 = min(
            1.0,
            math.log1p(result.matched_prompt_count) / math.log1p(_DEMAND_SATURATION),
        )

        # recency: exponential decay on the freshest match.
        if matched_idx:
            latest_ts = max(profile.prompt_timestamps[i] for i in matched_idx)
            age_days = max(0.0, (profile.now_ms - latest_ts) / _DAY_MS)
            result.last_used_days_ago = round(age_days, 1)
            recency01 = 0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS)
        else:
            recency01 = 0.0

        result.relevance = round(relevance01 * 100, 1)
        result.demand = round(demand01 * 100, 1)
        result.recency = round(recency01 * 100, 1)

    # ---- gap: do you already have something covering this surface? --------
    installed = list_installed_skill_slugs(claude_home)
    already_have = _already_have(slug, skill_tokens, installed, profile)
    result.already_have = already_have
    # gap is high when you don't yet own something similar AND you want it.
    if has_history and result.demand is not None:
        demand01 = result.demand / 100.0
        gap01 = (_ALREADY_HAVE_GAP if already_have else 1.0) * demand01
        result.gap = round(gap01 * 100, 1)
    else:
        # Without history we can still say "you already own it" → low gap.
        result.gap = 20.0 if already_have else 70.0

    # ---- fit_env: OS compatibility + required-bin presence ---------------
    os_compatible = _os_compatible(os_constraint)
    result.os_compatible = os_compatible
    present_bins = [b for b in required_bins if shutil.which(b)]
    result.missing_bins = [b for b in required_bins if b not in present_bins]
    if not os_compatible:
        fit_env01 = 0.0
    elif not required_bins:
        # Nothing claimed = nothing missing. Default to engaged-only credit.
        fit_env01 = 1.0
    else:
        fit_env01 = len(present_bins) / len(required_bins)
    # Original scorer gated fit on relevance>0; preserve that nuance so
    # ubiquitous "your env supports this skill you'd never want" doesn't lift.
    if has_history and (result.relevance or 0) <= 0:
        fit_env01 *= 0.5
    result.fit_env = round(fit_env01 * 100, 1)

    # ---- total: mean of available dims -----------------------------------
    available = [
        d for d in [result.relevance, result.demand, result.recency,
                    result.gap, result.fit_env]
        if d is not None
    ]
    result.total = round(sum(available) / len(available), 1) if available else None
    result.reason = _build_reason(result)

    if ctx is not None:
        from telemetry import emit
        emit(ctx, "score_fit_done", {
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "has_history": has_history,
            "total_bucket": _bucket(result.total),
        })
    return result


# ----------------------------- helpers ---------------------------------------


def _build_idf(profile: UserProfile) -> dict[str, float]:
    n = profile.prompt_count
    return {
        token: math.log((n + 1) / (len(plist) + 1)) + 1.0
        for token, plist in profile.postings.items()
    }


def _slug_variants(name: str) -> set[str]:
    low = name.strip().lower()
    return {v for v in {
        low, low.replace(" ", "-"), low.replace(" ", ""),
        low.replace("_", "-"), low.replace("-", ""),
    } if v}


def _already_have(
    slug: str,
    skill_tokens: set[str],
    installed: list[str],
    profile: UserProfile,
) -> bool:
    """Both: do you have a skill with a similar slug, AND do you mention this
    via slash command? Either way trips."""
    variants = _slug_variants(slug)
    if any(v in installed for v in variants):
        return True
    if any(v in profile.used_slugs for v in variants):
        return True
    # Fuzzy: any installed slug whose name overlaps significantly with the
    # candidate's distinctive tokens.
    for inst in installed:
        if any(tok in inst for tok in skill_tokens if len(tok) >= 4):
            return True
    return False


def _infer_slug_from_skill_md(skill_md: str) -> str | None:
    """Pull `name:` from YAML frontmatter."""
    m = re.search(r"^---\s*\n(.*?)\n---", skill_md, re.S | re.M)
    if not m:
        return None
    fm = m.group(1)
    nm = re.search(r"^\s*name\s*:\s*['\"]?([\w.-]+)['\"]?\s*$", fm, re.M)
    return nm.group(1).strip() if nm else None


def _extract_required_bins(skill_md: str) -> list[str]:
    """Best-effort extraction of binaries the skill claims to need.

    Looks at:
      1. ``bin:`` / ``requires:`` / ``needs:`` lines in YAML frontmatter
      2. ``which <name>`` / ``command -v <name>`` patterns in body
      3. Common tool names following backticks: ``rg``, ``gh``, ``jq``, etc.
    """
    bins: set[str] = set()

    # 1) frontmatter hints
    m = re.search(r"^---\s*\n(.*?)\n---", skill_md, re.S | re.M)
    if m:
        for key in ("bin", "bins", "requires", "needs", "runtime"):
            row = re.search(
                rf"^\s*{key}\s*:\s*\[?([^\]\n]+)\]?\s*$",
                m.group(1), re.M,
            )
            if row:
                for tok in re.split(r"[,\s]+", row.group(1)):
                    tok = tok.strip("\"' []")
                    if tok and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_+-]{1,30}", tok):
                        bins.add(tok)

    # 2) which <name> / command -v <name>
    for hit in re.finditer(
        r"(?:which|command\s+-v)\s+([a-z][a-z0-9_+-]{1,30})", skill_md
    ):
        bins.add(hit.group(1))

    return sorted(bins)


_OS_HINT_RE = re.compile(
    r"\bos\s*:\s*['\"]?(macos|mac|darwin|linux|windows|win)['\"]?\b",
    re.IGNORECASE,
)
_OS_ONLY_RE = re.compile(
    r"\b(macos|mac|linux|windows|win)\s*(only|exclusive|specific)\b",
    re.IGNORECASE,
)


def _extract_os_constraint(skill_md: str) -> str | None:
    """Returns 'macos'/'linux'/'windows' if the skill claims OS-specificity."""
    m = _OS_HINT_RE.search(skill_md) or _OS_ONLY_RE.search(skill_md)
    if not m:
        return None
    name = m.group(1).lower()
    if name in ("mac", "darwin"):
        return "macos"
    if name == "win":
        return "windows"
    return name


def _os_compatible(claim: str | None) -> bool:
    if not claim:
        return True
    cur = sys.platform
    if claim == "macos":
        return cur == "darwin"
    if claim == "linux":
        return cur.startswith("linux")
    if claim == "windows":
        return cur.startswith("win")
    return True


def _build_reason(r: FitResult) -> str:
    if not r.has_history:
        return "本机没有 Claude Code 提示词历史可参考(history.jsonl 不存在或为空)"
    parts: list[str] = []
    if r.matched_prompt_count:
        parts.append(f"匹配你 {r.matched_prompt_count} 条历史 prompt")
    if r.matched_terms:
        parts.append(f"关键词命中: {'、'.join(r.matched_terms[:4])}")
    if r.last_used_days_ago is not None:
        parts.append(f"最近 {round(r.last_used_days_ago)} 天前用到过")
    if r.already_have:
        parts.append("你已经装了类似 skill")
    if r.missing_bins:
        parts.append(f"缺少依赖: {', '.join(r.missing_bins)}")
    if not r.os_compatible:
        parts.append(f"声明的 OS 和你机器不一致")
    return "；".join(parts) if parts else "与你的历史使用几乎无重合"


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


# ----------------------------- CLI ------------------------------------------


def _main() -> int:
    """Standalone debug entry: `python score_fit.py <path-to-SKILL.md>`."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("skill_md", help="path to a SKILL.md file")
    parser.add_argument("--claude-home", default=os.path.expanduser("~/.claude"))
    args = parser.parse_args()

    text = Path(args.skill_md).read_text(encoding="utf-8")
    result = score_fit(text, claude_home=Path(args.claude_home))
    print(f"Fit total: {result.total}")
    print(f"  relevance: {result.relevance}")
    print(f"  demand:    {result.demand}")
    print(f"  recency:   {result.recency}")
    print(f"  gap:       {result.gap}")
    print(f"  fit_env:   {result.fit_env}")
    print(f"has_history: {result.has_history}")
    print(f"matched_prompts: {result.matched_prompt_count}")
    print(f"matched_terms: {result.matched_terms}")
    print(f"missing_bins: {result.missing_bins}")
    print(f"reason: {result.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
