"""Static-analysis quality score on a SKILL.md.

3 condensed dims (from darwin-skill's 9):
  - form        — darwin 1+2+7  (frontmatter + workflow clarity + architecture)
  - robustness  — darwin 3+4+9  (failure encoding + checkpoints + anti-pattern)
  - executable  — darwin 5+6    (actionable specificity + resource integration)

Rules: see references/scoring-algorithm.md (every deduction is enumerated).
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telemetry import SessionContext


@dataclass
class QualityResult:
    form: float = 0.0           # 写法     (0-100)
    robustness: float = 0.0     # 稳健     (0-100)
    executable: float = 0.0     # 可执行   (0-100)
    total: float = 0.0          # mean    (0-100)
    reasons: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    has_checkpoints: bool = False
    has_blacklist: bool = False


# ----------------------------- public entry ----------------------------------


def score_quality(skill_md: str, *, ctx: "SessionContext | None" = None) -> QualityResult:
    t0 = time.monotonic()
    if ctx is not None:
        from telemetry import emit
        emit(ctx, "score_quality_started")

    frontmatter, body = _split_frontmatter(skill_md)
    result = QualityResult()
    result.reasons = {"form": [], "robustness": [], "executable": []}

    result.form = _score_form(frontmatter, body, result.reasons["form"])
    result.robustness = _score_robustness(body, result)
    result.executable = _score_executable(skill_md, body, result.reasons["executable"])
    result.total = round((result.form + result.robustness + result.executable) / 3, 1)

    # Warnings (no deduction).
    if _runtime_drift(skill_md, frontmatter):
        result.warnings.append("runtime_drift: 正文出现『Claude Code』等单 runtime 措辞")

    if ctx is not None:
        from telemetry import emit
        emit(ctx, "score_quality_done", {
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "total_bucket": _bucket(result.total),
            "has_checkpoints": result.has_checkpoints,
            "has_blacklist": result.has_blacklist,
        })
    return result


# ----------------------------- form ------------------------------------------


_HEDGE_TAIL_RE = re.compile(
    r"(灵活应用|根据情况(?:判断|决定)|视情况而定|case\s*by\s*case|"
    r"depending\s+on\s+the\s+situation|use\s+your\s+judgment)\s*[\.。]?\s*$",
    re.IGNORECASE,
)


def _score_form(frontmatter: str | None, body: str, reasons: list[str]) -> float:
    score = 100.0

    if frontmatter is None:
        reasons.append("缺少 YAML frontmatter (-40)")
        return max(0.0, score - 40)

    # Required fields.
    name_match = re.search(r"^\s*name\s*:\s*['\"]?[\w.-]+['\"]?\s*$", frontmatter, re.M)
    if not name_match:
        score -= 20
        reasons.append("frontmatter 缺 name 字段 (-20)")

    desc_match = re.search(r"^\s*description\s*:\s*(.+?)$(?:\n\s+\S.*$)*",
                           frontmatter, re.M)
    if not desc_match:
        score -= 25
        reasons.append("frontmatter 缺 description 字段 (-25)")
    else:
        desc_full = _read_yaml_block_scalar(frontmatter, "description")
        if len(desc_full) < 64:
            score -= 10
            reasons.append("description 太短 (<64 chars) (-10)")
        if len(desc_full) > 1024:
            score -= 5
            reasons.append("description 过长 (>1024 chars) (-5)")
        if _HEDGE_TAIL_RE.search(desc_full):
            score -= 8
            reasons.append("description 结尾是『灵活应用/case by case』空话尾巴 (-8)")

    # Body structure.
    if not re.search(r"^#{2,3}\s+\S", body, re.M):
        score -= 15
        reasons.append("body 缺 ## / ### 段落结构 (-15)")
    has_ordered = bool(re.search(
        r"(?:^\s*\d+\.\s|\bStep\s+\d+\b|\bPhase\s+\d+\b)", body, re.M | re.I))
    if not has_ordered:
        score -= 10
        reasons.append("body 缺有序步骤 (1./2./Step N/Phase N) (-10)")

    # AI-slop tell.
    if re.search(r"\n\s*\n\s*\n\s*\n\s*\n", body):
        score -= 3
        reasons.append("body 存在 5+ 连续空行 (AI slop tell) (-3)")

    # Token budget — rough proxy: ~4 chars/token for mixed text.
    approx_tokens = len(body) / 4
    if approx_tokens > 10_000:
        score -= 5
        reasons.append(f"body 过长 (~{int(approx_tokens)} tokens > 10k) (-5)")

    return max(0.0, round(score, 1))


# ----------------------------- robustness ------------------------------------


_FAILURE_PATTERN_RE = re.compile(
    r"(if\s+\w[^.\n]{0,80}\s+(?:then|→|->|—|—)|on\s+failure|fallback|on\s+error|"
    r"如果\S{0,40}(?:失败|找不到|不存在|超时))",
    re.IGNORECASE,
)
_CHECKPOINT_RE = re.compile(r"(🔴|STOP\b|CHECKPOINT\b|🛑)", re.IGNORECASE)
_BLACKLIST_RE = re.compile(
    r"(anti[-\s]?pattern|blacklist|do\s+not\s+do|don't\s+do|反例|黑名单|禁止)",
    re.IGNORECASE,
)
_DESTRUCTIVE_RE = re.compile(
    r"(rm\s+-rf|git\s+reset\s+--hard|push\s+--force|force\s+push|drop\s+table)",
    re.IGNORECASE,
)


def _score_robustness(body: str, result: QualityResult) -> float:
    reasons = result.reasons["robustness"]
    score = 100.0

    failure_hits = len(_FAILURE_PATTERN_RE.findall(body))
    if failure_hits == 0:
        score -= 30
        reasons.append("没有 if-X-then-Y / fallback / 失败处理模式 (-30)")
    elif failure_hits < 3:
        score -= 10
        reasons.append(f"失败处理模式只有 {failure_hits} 处,建议 ≥3 (-10)")

    checkpoint_hits = len(_CHECKPOINT_RE.findall(body))
    result.has_checkpoints = checkpoint_hits > 0
    if checkpoint_hits == 0:
        score -= 15
        reasons.append("没有可视化 CHECKPOINT 标记 (🔴/STOP) (-15)")

    has_blacklist = bool(_BLACKLIST_RE.search(body))
    result.has_blacklist = has_blacklist
    if not has_blacklist:
        score -= 20
        reasons.append("没有 anti-pattern / blacklist / 反例 章节 (-20)")

    # Destructive ops mentioned without an adjacent warning word.
    for hit in _DESTRUCTIVE_RE.finditer(body):
        window = body[max(0, hit.start() - 100): hit.end() + 100]
        if not re.search(r"(注意|warning|caution|不要|never|do\s*not|危险|危險)",
                         window, re.IGNORECASE):
            score -= 15
            reasons.append(f"提到危险操作 `{hit.group(0)}` 但附近没有警告 (-15)")
            break

    return max(0.0, round(score, 1))


# ----------------------------- executable -----------------------------------


_HEDGE_RE = re.compile(
    r"(建议|可以考虑|视情况|case\s*by\s*case|"
    r"\bsuggest(?:s|ed|ing)?\b|\bconsider\b|\bdepending\s+on\b)",
    re.IGNORECASE,
)
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_REF_RE = re.compile(r"\[([^\]]+)\]\((?!https?://)([^)]+)\)")


def _score_executable(skill_md: str, body: str, reasons: list[str]) -> float:
    score = 100.0

    hedge_hits = len(_HEDGE_RE.findall(body))
    if hedge_hits >= 3:
        deduction = min(25, 10 + 2 * (hedge_hits - 3))
        score -= deduction
        reasons.append(f"软化措辞密度高 ({hedge_hits} 处 ≥3) (-{deduction})")

    code_blocks = _CODE_BLOCK_RE.findall(body)
    if len(code_blocks) == 0:
        score -= 15
        reasons.append("没有代码块 / 具体命令示例 (-15)")

    # Resource refs — relative links that should resolve.
    # We can't always resolve them (no fs context), so just check that
    # referenced paths look well-formed; deeper check happens at runtime.
    bad_refs: list[str] = []
    for label, target in _REF_RE.findall(skill_md):
        if target.startswith("#"):
            continue  # in-doc anchor
        # Pure scripts/references mention without odd chars is fine.
        if re.search(r"\s|[<>|]", target):
            bad_refs.append(target)
    if bad_refs:
        score -= 10
        reasons.append(f"资源引用路径不规范: {bad_refs[:3]} (-10)")

    return max(0.0, round(score, 1))


# ----------------------------- helpers ---------------------------------------


def _split_frontmatter(skill_md: str) -> tuple[str | None, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", skill_md, re.S)
    if not m:
        return None, skill_md
    return m.group(1), m.group(2)


def _read_yaml_block_scalar(frontmatter: str, key: str) -> str:
    """Read a single-line or folded-block scalar after `<key>:`.

    Handles both:
      description: "single line"
      description: |
        first line
        second line
    """
    m = re.search(rf"^\s*{re.escape(key)}\s*:\s*(.*)$", frontmatter, re.M)
    if not m:
        return ""
    head = m.group(1).strip().strip("'\"")
    if head and not head.startswith(("|", ">")):
        return head
    # Folded/literal block — collect indented continuation lines after the key line.
    lines = frontmatter.splitlines()
    out: list[str] = []
    capture = False
    for line in lines:
        if not capture:
            if re.match(rf"^\s*{re.escape(key)}\s*:\s*[|>]?\s*$", line):
                capture = True
                continue
        else:
            if re.match(r"^\s+\S", line):
                out.append(line.strip())
            elif line.strip() == "":
                out.append("")
            else:
                break
    return " ".join(out).strip()


def _runtime_drift(skill_md: str, frontmatter: str | None) -> bool:
    """`Claude Code` etc. should only appear inside frontmatter triggers."""
    body = skill_md
    if frontmatter:
        body = skill_md.replace(frontmatter, "")
    return bool(re.search(r"\b(Claude\s+Code|in\s+Claude\s+Code)\b", body))


def _bucket(score: float) -> str:
    if score >= 85:
        return "85-100"
    if score >= 70:
        return "70-84"
    if score >= 50:
        return "50-69"
    return "0-49"


# ----------------------------- CLI ------------------------------------------


def _main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("skill_md")
    args = p.parse_args()

    text = Path(args.skill_md).read_text(encoding="utf-8")
    r = score_quality(text)
    print(f"Quality total: {r.total}")
    print(f"  form:       {r.form}")
    for x in r.reasons["form"]:
        print(f"    - {x}")
    print(f"  robustness: {r.robustness}")
    for x in r.reasons["robustness"]:
        print(f"    - {x}")
    print(f"  executable: {r.executable}")
    for x in r.reasons["executable"]:
        print(f"    - {x}")
    if r.warnings:
        print("warnings:")
        for w in r.warnings:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
