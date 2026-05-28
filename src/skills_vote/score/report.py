from __future__ import annotations

import html
from datetime import datetime

from skills_vote.score.model import SkillScore

_DIMENSIONS = [
    ("relevance", "相关"),
    ("demand", "需求"),
    ("recency", "时效"),
    ("gap", "缺口"),
    ("fit", "适配"),
]

_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2024;--muted:#6b7280;--line:#e6e8eb;
--hi:#0ea05a;--mid:#2563eb;--lo:#9aa3ad;--tag:#eef1f5;--bar:#eef1f5;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,"Segoe UI","Microsoft YaHei",Roboto,Helvetica,Arial,sans-serif;
line-height:1.5;}
.wrap{max-width:880px;margin:0 auto;padding:40px 20px 64px;}
.head h1{font-size:30px;margin:0 0 6px;letter-spacing:-.5px;}
.head .brand{color:var(--mid);}
.head p{color:var(--muted);margin:0;font-size:14px;}
.stats{display:flex;gap:28px;margin:22px 0 28px;flex-wrap:wrap;}
.stat .n{font-size:26px;font-weight:700;}
.stat .l{font-size:12px;color:var(--muted);}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:18px 20px;margin:12px 0;display:flex;gap:16px;align-items:flex-start;}
.rank{font-size:20px;font-weight:700;color:var(--lo);min-width:30px;text-align:center;
padding-top:2px;}
.body{flex:1;min-width:0;}
.row1{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;}
.name{font-size:17px;font-weight:650;}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;background:var(--tag);
color:var(--muted);}
.badge.have{background:#fff4e5;color:#b25e09;}
.badge.gap{background:#e7f6ee;color:#0a7a43;}
.score{margin-left:auto;font-size:22px;font-weight:800;font-variant-numeric:tabular-nums;}
.score small{font-size:12px;font-weight:500;color:var(--muted);}
.valbar{height:6px;background:var(--bar);border-radius:4px;margin:9px 0 11px;overflow:hidden;}
.valbar i{display:block;height:100%;border-radius:4px;}
.reason{color:var(--muted);font-size:13px;margin:0 0 10px;}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;}
.tag{font-size:12px;background:var(--tag);color:#48505a;border-radius:6px;padding:2px 8px;}
.dims{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;}
.dim .dl{font-size:11px;color:var(--muted);display:flex;justify-content:space-between;}
.dim .db{height:4px;background:var(--bar);border-radius:3px;margin-top:3px;overflow:hidden;}
.dim .db i{display:block;height:100%;background:var(--mid);border-radius:3px;}
.foot{color:var(--lo);font-size:12px;margin-top:30px;text-align:center;}
.empty{color:var(--muted);font-size:13px;}
"""


def _score_color(value: float) -> str:
    if value >= 70:
        return "var(--hi)"
    if value >= 40:
        return "var(--mid)"
    return "var(--lo)"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _render_card(rank: int, score: SkillScore) -> str:
    color = _score_color(score.value)
    badge = (
        '<span class="badge have">已在用</span>'
        if score.already_have
        else ('<span class="badge gap">可补齐</span>' if score.matched_prompt_count else "")
    )
    tags = "".join(f'<span class="tag">{_esc(t)}</span>' for t in score.matched_terms)
    dims = "".join(
        f'<div class="dim"><div class="dl"><span>{label}</span>'
        f"<span>{int(round(getattr(score.dimensions, key) * 100))}</span></div>"
        f'<div class="db"><i style="width:{getattr(score.dimensions, key) * 100:.0f}%"></i></div></div>'
        for key, label in _DIMENSIONS
    )
    return f"""
    <div class="card">
      <div class="rank">{rank}</div>
      <div class="body">
        <div class="row1">
          <span class="name">{_esc(score.skill_name)}</span>
          {badge}
          <span class="score" style="color:{color}">{score.value:.0f}<small>/100</small></span>
        </div>
        <div class="valbar"><i style="width:{score.value:.0f}%;background:{color}"></i></div>
        <p class="reason">{_esc(score.reason) or "—"}</p>
        <div class="tags">{tags}</div>
        <div class="dims">{dims}</div>
      </div>
    </div>"""


def render_html(
    scores: list[SkillScore],
    *,
    prompt_count: int,
    skills_evaluated: int,
    title: str = "SkillsVote · 为你推荐",
) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    if scores:
        cards = "\n".join(_render_card(i, s) for i, s in enumerate(scores, start=1))
    else:
        cards = '<p class="empty">没有可评分的技能，检查一下 --skills-dir。</p>'
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title><style>{_CSS}</style></head>
<body><div class="wrap">
  <div class="head">
    <h1><span class="brand">For You</span> · 最值得你装的技能</h1>
    <p>基于你本地 Claude Code 的真实使用习惯，按“对我的价值”排序 · 生成于 {generated}</p>
  </div>
  <div class="stats">
    <div class="stat"><div class="n">{prompt_count:,}</div><div class="l">扫描的使用记录</div></div>
    <div class="stat"><div class="n">{skills_evaluated:,}</div><div class="l">参与评分的技能</div></div>
    <div class="stat"><div class="n">{len(scores)}</div><div class="l">本页展示</div></div>
  </div>
  {cards}
  <p class="foot">评分维度：相关·需求·时效·缺口·适配 | 数据全部来自本地，未上传 | SkillsVote 个性化扩展</p>
</div></body></html>"""
