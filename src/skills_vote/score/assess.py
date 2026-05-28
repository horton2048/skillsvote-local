from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from skills_vote.score.environment import COMMON_BINS, LocalEnvironment, detect_environment
from skills_vote.score.fetch import FetchedSkill, fetch_skill
from skills_vote.score.model import ScoreConfig, SkillScore, UserProfile
from skills_vote.score.scorer import build_idf, score_skill
from skills_vote.score.usage_scan import scan_user_profile

Verdict = Literal["install", "optional", "skip", "already"]

_EXTRA_BINS = ("ffmpeg", "go", "cargo", "java", "make", "deno", "bun")
_OS_WORDS = {"windows": "windows", "macos": "macos", "mac": "macos", "linux": "linux"}


class EnvCompat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    os_supported: bool = True
    os_note: str = ""
    required_bins: list[str] = Field(default_factory=list)
    missing_bins: list[str] = Field(default_factory=list)
    already_installed: bool = False
    env_fit: float = Field(default=1.0, ge=0.0, le=1.0)


class AssessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str
    source_url: str
    origin: str
    install_ref: str | None = None
    score: SkillScore
    env: EnvCompat
    verdict: Verdict
    verdict_label: str
    verdict_reason: str
    install_prompt: str


def _slug_variants(name: str) -> set[str]:
    low = name.strip().lower()
    return {v for v in {low, low.replace(" ", "-"), low.replace(" ", ""),
                        low.replace("_", "-"), low.replace("-", "")} if v}


def _detect_required_bins(body: str) -> list[str]:
    low = body.lower()
    pool = tuple(COMMON_BINS) + _EXTRA_BINS
    return [b for b in pool if re.search(rf"\b{re.escape(b)}\b", low)]


def _detect_os_support(body: str, env: LocalEnvironment) -> tuple[bool, str]:
    low = body.lower()
    constrained: set[str] = set()
    for word, kind in _OS_WORDS.items():
        if re.search(rf"\b{word}[ -]?only\b", low) or re.search(rf"only (?:on |runs on )?{word}\b", low):
            constrained.add(kind)
    if constrained and env.os_kind not in constrained:
        return False, f"该技能声明仅支持 {', '.join(sorted(constrained))}，与你的 {env.os_kind} 不匹配"
    return True, ""


def assess_skill(
    link: str,
    *,
    profile: UserProfile | None = None,
    env: LocalEnvironment | None = None,
    config: ScoreConfig | None = None,
    claude_home: Path | None = None,
    fetched: FetchedSkill | None = None,
) -> AssessResult:
    config = config or ScoreConfig()
    profile = profile or scan_user_profile(claude_home)
    env = env or detect_environment(claude_home)
    fetched = fetched or fetch_skill(link)
    descriptor = fetched.descriptor

    # --- usage-based personalized score (relevance/demand/recency/gap) ---
    idf = build_idf(profile)
    max_idf = max(idf.values(), default=1.0)
    base = score_skill(descriptor, profile, idf=idf, max_idf=max_idf, config=config)

    # --- real local-environment compatibility ---
    required_bins = _detect_required_bins(fetched.body)
    missing_bins = [b for b in required_bins if not env.has_bin(b)]
    os_supported, os_note = _detect_os_support(fetched.body, env)
    installed_lower = {s.lower() for s in env.installed_skills}
    already_installed = bool(_slug_variants(descriptor.name) & installed_lower)

    if not os_supported:
        env_fit = 0.3
    elif missing_bins:
        env_fit = 0.7
    else:
        env_fit = 1.0
    engaged = 1.0 if base.dimensions.relevance > 0 else 0.0
    fit_dim = round(env_fit * engaged, 4)

    w = config.weights
    d = base.dimensions
    value = 100.0 * (
        w.relevance * d.relevance
        + w.demand * d.demand
        + w.recency * d.recency
        + w.gap * d.gap
        + w.fit * fit_dim
    )
    value = round(min(100.0, max(0.0, value)), 2)
    score = base.model_copy(
        update={
            "value": value,
            "dimensions": d.model_copy(update={"fit": fit_dim}),
            "already_have": already_installed,
        }
    )

    env_compat = EnvCompat(
        os_supported=os_supported,
        os_note=os_note,
        required_bins=required_bins,
        missing_bins=missing_bins,
        already_installed=already_installed,
        env_fit=env_fit,
    )

    verdict, label, reason = _decide(score, env_compat)
    prompt = build_install_prompt(descriptor.name, fetched, env, env_compat)

    return AssessResult(
        skill_name=descriptor.name,
        source_url=fetched.source_url,
        origin=fetched.origin,
        install_ref=fetched.install_ref,
        score=score,
        env=env_compat,
        verdict=verdict,
        verdict_label=label,
        verdict_reason=reason,
        install_prompt=prompt,
    )


def _decide(score: SkillScore, env: EnvCompat) -> tuple[Verdict, str, str]:
    if env.already_installed:
        return "already", "已安装", "你本地已经装过同名技能，无需重复安装。"
    if not env.os_supported:
        return "skip", "不建议安装", env.os_note
    bin_note = ""
    if env.missing_bins:
        bin_note = f"（注意：需要先装这些命令行工具：{', '.join(env.missing_bins)}）"
    if score.value >= 60:
        return "install", "建议安装", f"对你价值较高（{score.value:.0f} 分）：{score.reason}{bin_note}"
    if score.value >= 40:
        return "optional", "可装可不装", f"中等价值（{score.value:.0f} 分）：{score.reason}{bin_note}"
    return "skip", "暂不建议", f"对你价值不大（{score.value:.0f} 分）：{score.reason}"


def build_install_prompt(
    name: str,
    fetched: FetchedSkill,
    env: LocalEnvironment,
    compat: EnvCompat,
) -> str:
    source = fetched.raw_url or fetched.source_url
    lines: list[str] = []
    lines.append(f"请把下面这个 skill 安装到我本地的 Claude Code，并原生适配我的环境。")
    lines.append("")
    lines.append(f"技能名: {name}")
    lines.append(f"来源: {source}")
    if fetched.install_ref:
        skill_arg = f" --skill {name}" if fetched.skill_path else ""
        lines.append(f"安装方式(优先): npx skills add {fetched.install_ref}{skill_arg}")
    lines.append(
        f"安装方式(手动兜底): 把该 SKILL.md 连同同目录脚本放到 {env.skills_dir}\\{name}\\ 下"
    )
    lines.append("")
    lines.append("我的本地环境:")
    lines.append(f"- 操作系统: {env.os_kind} ({env.platform})，shell: {env.shell}")
    lines.append(f"- skills 目录: {env.skills_dir}")
    if compat.required_bins:
        present = [b for b in compat.required_bins if b not in compat.missing_bins]
        lines.append(f"- 该技能需要的工具: {', '.join(compat.required_bins)}")
        lines.append(f"  已具备: {', '.join(present) or '无'}；缺失: {', '.join(compat.missing_bins) or '无'}")
    lines.append("")
    lines.append("适配要求:")
    lines.append("- 把技能里任何 macOS/Linux 专用命令改写成我的 " + env.shell + " 等价写法")
    lines.append("- 所有路径用我上面的真实路径，不要用示例路径")
    if compat.missing_bins:
        lines.append(f"- 先给我 {', '.join(compat.missing_bins)} 的安装指引，装好再继续")
    lines.append("- 安装完做一次自检：在我的环境里跑通该技能的核心流程，失败就修到能跑")
    lines.append("- 如果和我已装的同类技能重复，提示我并帮我合并，不要静默覆盖")
    return "\n".join(lines)
