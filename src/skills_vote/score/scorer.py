from __future__ import annotations

import math
from pathlib import Path

from skills_vote.score.model import (
    ScoreConfig,
    ScoreDimensions,
    SkillDescriptor,
    SkillScore,
    UserProfile,
)
from skills_vote.score.skill_source import load_skills
from skills_vote.score.tokenize import tokenize
from skills_vote.score.usage_scan import scan_user_profile

_DAY_MS = 86_400_000


def build_idf(profile: UserProfile) -> dict[str, float]:
    """Smoothed inverse document frequency over the prompt corpus."""
    n = profile.prompt_count
    return {
        token: math.log((n + 1) / (len(plist) + 1)) + 1.0
        for token, plist in profile.postings.items()
    }


def _slug_variants(name: str) -> set[str]:
    low = name.strip().lower()
    variants = {
        low,
        low.replace(" ", "-"),
        low.replace(" ", ""),
        low.replace("_", "-"),
        low.replace("-", ""),
    }
    return {v for v in variants if v}


def _matched_prompt_indices(
    profile: UserProfile, tokens: list[str]
) -> set[int]:
    indices: set[int] = set()
    for token in tokens:
        indices.update(profile.postings.get(token, ()))
    return indices


def score_skill(
    descriptor: SkillDescriptor,
    profile: UserProfile,
    *,
    idf: dict[str, float],
    max_idf: float,
    config: ScoreConfig | None = None,
) -> SkillScore:
    config = config or ScoreConfig()
    weights = config.weights

    token_set = set(tokenize(f"{descriptor.name} {descriptor.description}"))

    # --- relevance: IDF-weighted fraction of the skill's informative terms that
    # the user actually engages with. ---
    total_weight = 0.0
    matched_weight = 0.0
    matched_tokens: list[tuple[str, float]] = []
    for token in token_set:
        weight = idf.get(token, max_idf)
        total_weight += weight
        if token in profile.postings:
            matched_weight += weight
            matched_tokens.append((token, weight))
    relevance = (matched_weight / total_weight) if total_weight > 0 else 0.0

    # Distinctive matched terms drive demand/recency so ubiquitous filler that
    # happens to overlap does not inflate the score.
    idf_floor = config.distinctive_idf_ratio * max_idf
    distinctive = [t for t, w in matched_tokens if w >= idf_floor]
    demand_tokens = distinctive or [t for t, _ in matched_tokens]
    matched_indices = _matched_prompt_indices(profile, demand_tokens)
    matched_prompt_count = len(matched_indices)

    # --- demand: how often the user does tasks in this skill's domain. ---
    demand = min(1.0, math.log1p(matched_prompt_count) / math.log1p(config.demand_saturation))

    # --- recency: time-decayed freshness of the most recent matching task. ---
    last_used_days_ago: float | None = None
    recency = 0.0
    if matched_indices:
        latest_ts = max(profile.prompt_timestamps[i] for i in matched_indices)
        age_days = max(0.0, (profile.now_ms - latest_ts) / _DAY_MS)
        last_used_days_ago = age_days
        recency = 0.5 ** (age_days / config.recency_half_life_days)

    # --- gap: unmet capability the user reaches for but has not installed. ---
    already_have = any(
        v in profile.used_slugs or v in profile.postings
        for v in _slug_variants(descriptor.name)
    )
    own_factor = config.already_have_gap if already_have else 1.0
    gap = own_factor * demand

    # --- fit: environment compatibility, only credited for relevant skills. ---
    engaged = 1.0 if relevance > 0 else 0.0
    fit = _fit_quality(descriptor) * engaged

    value = 100.0 * (
        weights.relevance * relevance
        + weights.demand * demand
        + weights.recency * recency
        + weights.gap * gap
        + weights.fit * fit
    )

    matched_terms = [t for t, _ in sorted(matched_tokens, key=lambda x: x[1], reverse=True)]

    return SkillScore(
        skill_name=descriptor.name,
        value=round(min(100.0, max(0.0, value)), 2),
        dimensions=ScoreDimensions(
            relevance=round(relevance, 4),
            demand=round(demand, 4),
            recency=round(recency, 4),
            gap=round(gap, 4),
            fit=round(fit, 4),
        ),
        matched_prompt_count=matched_prompt_count,
        matched_terms=matched_terms[:6],
        last_used_days_ago=(round(last_used_days_ago, 1) if last_used_days_ago is not None else None),
        already_have=already_have,
        reason=_build_reason(
            matched_prompt_count=matched_prompt_count,
            matched_terms=matched_terms[:4],
            last_used_days_ago=last_used_days_ago,
            already_have=already_have,
            demand=demand,
        ),
    )


def _fit_quality(descriptor: SkillDescriptor) -> float:
    """Lightweight OS compatibility heuristic against the current platform."""
    import sys

    text = f"{descriptor.name} {descriptor.description}".lower()
    current = sys.platform
    if current.startswith("win"):
        if ("macos only" in text or "mac only" in text or "linux only" in text) and (
            "windows" not in text
        ):
            return 0.3
    elif current == "darwin":
        if "windows only" in text or "linux only" in text:
            return 0.3
    elif current.startswith("linux"):
        if "windows only" in text or ("macos only" in text or "mac only" in text):
            return 0.3
    return 1.0


def _build_reason(
    *,
    matched_prompt_count: int,
    matched_terms: list[str],
    last_used_days_ago: float | None,
    already_have: bool,
    demand: float,
) -> str:
    if matched_prompt_count == 0:
        return "与你的历史使用几乎无重合"
    parts = [f"命中你 {matched_prompt_count} 条历史任务"]
    if matched_terms:
        parts.append(f"关键词: {'、'.join(matched_terms)}")
    if last_used_days_ago is not None:
        parts.append(f"最近约 {round(last_used_days_ago)} 天前用到")
    if already_have:
        parts.append("你已在用该 skill")
    elif demand >= 0.4:
        parts.append("常做但还没装，补齐能力缺口")
    return "；".join(parts)


def score_skills(
    descriptors: list[SkillDescriptor],
    profile: UserProfile,
    *,
    config: ScoreConfig | None = None,
) -> list[SkillScore]:
    config = config or ScoreConfig()
    idf = build_idf(profile)
    max_idf = max(idf.values(), default=1.0)
    scores = [
        score_skill(d, profile, idf=idf, max_idf=max_idf, config=config)
        for d in descriptors
    ]
    scores.sort(key=lambda s: (s.value, s.matched_prompt_count, s.skill_name), reverse=True)
    return scores


def score_skill_library(
    skills_dir: Path,
    *,
    profile: UserProfile | None = None,
    config: ScoreConfig | None = None,
    claude_home: Path | None = None,
    exclude: list[str] | None = None,
) -> list[SkillScore]:
    profile = profile or scan_user_profile(claude_home)
    descriptors = load_skills(Path(skills_dir), exclude=exclude)
    return score_skills(descriptors, profile, config=config)


def rank_skills_for_user(
    skill_names: list[str],
    *,
    skills_dir: Path | None = None,
    profile: UserProfile | None = None,
    config: ScoreConfig | None = None,
    claude_home: Path | None = None,
) -> list[SkillScore]:
    """Re-rank a candidate set of skills by personalized value to the user.

    This is the recommendation-ranking entry point: feed it the skill names a
    recommender proposed and it returns them ordered by "value to me", using
    SKILL.md metadata from ``skills_dir`` when available.
    """
    profile = profile or scan_user_profile(claude_home)
    by_name: dict[str, SkillDescriptor] = {}
    if skills_dir is not None:
        by_name = {d.name: d for d in load_skills(Path(skills_dir))}
    descriptors = [
        by_name.get(name, SkillDescriptor(name=name, source="name-only"))
        for name in skill_names
    ]
    return score_skills(descriptors, profile, config=config)
