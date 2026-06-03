"""Render the conversation-flow verdict block (Markdown).

See references/output-format.md for the canonical template.
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fetch import SkillMeta
    from score_fit import FitResult
    from score_quality import QualityResult


VERDICT_LABEL = {
    "install": "install",
    "install-with-caveat": "install-with-caveat",
    "save-for-later": "save-for-later",
    "skip": "skip",
    "not-enough-history": "not-enough-history",
}
VERDICT_EMOJI = {
    "install": "✅",
    "install-with-caveat": "⚠️",
    "save-for-later": "💎",
    "skip": "❌",
    "not-enough-history": "❓",
}


def render_verdict(
    skill_md: str,
    meta: "SkillMeta",
    fit: "FitResult",
    quality: "QualityResult",
    *,
    json_mode: bool = False,
) -> str:
    if json_mode:
        return json.dumps({
            "meta": {
                "slug": meta.slug,
                "source_url": meta.source_url,
                "size": meta.size,
                "truncated": meta.truncated,
            },
            "fit": _dict(fit),
            "quality": _dict(quality),
        }, ensure_ascii=False, indent=2)

    verdict = _decide_verdict(fit, quality)
    total = _final_total(fit, quality)
    header = _header(meta.slug, total, verdict)
    table = _table(fit, quality)
    why = _why(verdict, fit, quality)
    caveat = _caveat(fit, quality)
    install = _install_prompt(meta, fit)

    chunks = [header, "", table, "", why]
    if caveat:
        chunks += ["", caveat]
    chunks += ["", install]
    return "\n".join(chunks)


# ----------------------------- decisions ------------------------------------


def _decide_verdict(fit: "FitResult", quality: "QualityResult") -> str:
    if fit.total is None:
        return "not-enough-history"
    fh, qh = fit.total >= 70, quality.total >= 70
    if fh and qh:
        return "install"
    if fh and not qh:
        return "install-with-caveat"
    if not fh and qh:
        return "save-for-later"
    return "skip"


def _final_total(fit: "FitResult", quality: "QualityResult") -> float | None:
    if fit.total is None:
        # Quality-only: report quality.
        return round(quality.total, 1)
    return round(0.6 * fit.total + 0.4 * quality.total, 1)


# ----------------------------- formatting -----------------------------------


def _header(slug: str, total: float | None, verdict: str) -> str:
    emoji = VERDICT_EMOJI.get(verdict, "")
    total_str = f"{total}/100 · " if total is not None else ""
    return f"## {slug} · **{total_str}{emoji} {VERDICT_LABEL.get(verdict, verdict)}**"


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{int(round(v))}"


def _table(fit: "FitResult", quality: "QualityResult") -> str:
    rows = [
        "|     **Fit** 你的事        | 分 | | **Quality** skill 本身    | 分 |",
        "|--------------------------|----|--|---------------------------|----|",
        f"| 相关 keywords           | {_fmt(fit.relevance)} | "
        f"| 写法 frontmatter+流程     | {_fmt(quality.form)} |",
        f"| 需求 prompt 频次        | {_fmt(fit.demand)} | "
        f"| 稳健 fallback+checkpoint  | {_fmt(quality.robustness)} |",
        f"| 时效 最近多新           | {_fmt(fit.recency)} | "
        f"| 可执行 具体性+资源        | {_fmt(quality.executable)} |",
        f"| 缺口 是否已有类似       | {_fmt(fit.gap)} |  |                           |    |",
        f"| 适配 环境是否满足       | {_fmt(fit.fit_env)} |  |                           |    |",
        f"| **Fit 综合**            | **{_fmt(fit.total)}** | "
        f"| **Quality 综合**          | **{_fmt(quality.total)}** |",
    ]
    return "\n".join(rows)


def _why(verdict: str, fit: "FitResult", quality: "QualityResult") -> str:
    parts: list[str] = [f"**为什么 {VERDICT_LABEL.get(verdict, verdict)}**:"]
    if not fit.has_history:
        parts.append("本机没有 prompt 历史可参考(`history.jsonl` 不存在或为空)。")
        parts.append("仅基于 skill 本身质量给出判断。")
    else:
        if fit.matched_prompt_count:
            parts.append(f"匹配你 {fit.matched_prompt_count} 条历史 prompt")
        if fit.matched_terms:
            parts.append(f"关键词命中 {', '.join(fit.matched_terms[:4])};")
        if fit.last_used_days_ago is not None:
            parts.append(f"最近 {round(fit.last_used_days_ago)} 天前用到过;")
        if fit.already_have:
            parts.append("你**已经装了**类似 skill;")
        if fit.missing_bins:
            parts.append(f"缺少依赖 `{', '.join(fit.missing_bins)}`;")
        if not fit.os_compatible:
            parts.append("声明的 OS 与你机器不一致;")
    return " ".join(parts).rstrip("; ").rstrip(",;")


def _caveat(fit: "FitResult", quality: "QualityResult") -> str | None:
    pieces: list[str] = []
    low = [("写法", quality.form), ("稳健", quality.robustness),
           ("可执行", quality.executable)]
    weak = [name for name, val in low if val < 60]
    if weak:
        pieces.append(f"Quality 上 {'/'.join(weak)} 偏弱")
        for dim, key in (("form", "写法"), ("robustness", "稳健"),
                         ("executable", "可执行")):
            if key in weak:
                reasons = quality.reasons.get(dim, [])
                if reasons:
                    pieces.append("(" + "; ".join(reasons[:2]) + ")")
                    break
    if not fit.has_history:
        pieces.append("Fit 维度无 history,verdict 信心降低")
    if fit.missing_bins:
        pieces.append(f"装之前先准备 `{', '.join(fit.missing_bins)}`")
    if fit.already_have:
        pieces.append("你已经装了类似 skill,可能重复")
    if not pieces:
        return None
    return "⚠️ 隐忧: " + "; ".join(pieces) + "。"


def _install_prompt(meta: "SkillMeta", fit: "FitResult") -> str:
    test_input = _guess_test_input(fit.matched_terms)
    test_hint = f",装好后{test_input}试一下" if test_input else ""
    return (
        "**💡 一键安装** (复制给 host agent):\n"
        f"> 把 `{meta.slug}` 这个 skill 装到我的 skills 目录{test_hint}。"
        f"源 URL: {meta.source_url}"
    )


def _guess_test_input(matched_terms: list[str]) -> str | None:
    if not matched_terms:
        return None
    joined = " ".join(matched_terms).lower()
    if "pdf" in joined:
        return "处理我桌面上一份 pdf"
    if "translate" in joined or "翻译" in joined:
        return "翻译一段中文"
    if "test" in joined or "spec" in joined:
        return "跑一下当前项目测试"
    if "deploy" in joined or "ship" in joined or "vercel" in joined:
        return "看看部署状态"
    return None


def _dict(obj) -> dict:
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return dict(obj)
