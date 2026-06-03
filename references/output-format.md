# Verdict output format

The exact Markdown block `scripts/render.py` produces. Place this inline in the user-facing reply.

## Template

```markdown
## <slug> · **<total>/100 · <verdict-emoji> <verdict-label>**

| **Fit** 你的事     | 分  | | **Quality** skill 本身    | 分  |
|--------------------|-----|--|---------------------------|-----|
| 相关 keywords      | <r> | | 写法 frontmatter+流程     | <f> |
| 需求 prompt 频次   | <d> | | 稳健 fallback+checkpoint  | <ro>|
| 时效 最近多新      | <re>| | 可执行 具体性+资源        | <ex>|
| 缺口 是否已有类似  | <g> | |                           |     |
| 适配 环境是否满足  | <e> | |                           |     |
| **Fit 综合**       | **<fit_total>** | | **Quality 综合** | **<q_total>** |

**为什么 <verdict-label>**: <one-or-two-sentences-grounded-in-evidence>

<optional-section-if-Quality-dim<60-or-has_history=False>
⚠️ <隐忧 line>
</optional-section>

**💡 一键安装** (复制给 host agent):
> <install-prompt-adapted-to-user-env>
```

## Verdict labels and emoji

| (Fit, Quality) quadrant | Label | Emoji |
|---|---|---|
| Fit ≥70 AND Quality ≥70 | install | ✅ |
| Fit ≥70 AND Quality <70 | install-with-caveat | ⚠️ |
| Fit <70 AND Quality ≥70 | save-for-later | 💎 |
| Fit <70 AND Quality <70 | skip | ❌ |
| Fit unknown (no history) | not-enough-history | ❓ |

## "为什么" sentence anatomy

Always ground in concrete evidence pulled from the scoring step:
- Fit-high: "你最近 N 周有 M 条 prompt 涉及 <matched-term>;你没有装过类似 skill;你的 <bin-list> 满足要求。"
- Fit-low: "你最近的 prompt 历史里几乎没有这类需求(M 条匹配);你已经装了 <similar-skill-slug> 覆盖类似面。"
- Quality-low: "SKILL.md 缺少 <missing-element>;<warning-detail>。"

Never invent — if score_fit.matched_terms is empty, do NOT fabricate "matched keywords".

## "💡 一键安装" prompt anatomy

The user copies this and pastes back into their host agent. So phrase it as a **user → agent instruction**, not as a system command:

```
> 把 <slug> 这个 skill 装到我的 skills 目录,装好后用 <plausible-test-input> 试一下。源 URL: <source_url>
```

Adapt `<plausible-test-input>` from matched_terms when available — e.g., "处理我桌面上的 sample.pdf" if pdf-related, "翻译我刚才的那段中文" if translate-related. If no clear match, just say "试一下能不能跑起来".

## Sample (renders well in chat)

```markdown
## pdf-master · **78/100 · ✅ install**

| **Fit** 你的事     | 分 | | **Quality** skill 本身   | 分 |
|--------------------|----|--|--------------------------|----|
| 相关 keywords      | 92 | | 写法 frontmatter+流程    | 82 |
| 需求 prompt 频次   | 78 | | 稳健 fallback+checkpoint | 60 |
| 时效 最近多新      | 90 | | 可执行 具体性+资源       | 71 |
| 缺口 是否已有类似  | 88 | |                          |    |
| 适配 环境是否满足  | 75 | |                          |    |
| **Fit 综合**       | **85** | | **Quality 综合**   | **71** |

**为什么 install**: 你最近 3 周 14 条 prompt 涉及 PDF;你没有任何 PDF skill;你机器上已装 pdftotext。

⚠️ 隐忧: skill 没有显式失败 fallback。PDF 加密或损坏时可能没兜底,装完试一下边界用例。

**💡 一键安装** (复制给 host agent):
> 把 pdf-master 这个 skill 装到我的 skills 目录,装好后处理我桌面上的 sample.pdf 试一下。源 URL: https://github.com/.../pdf-master
```
