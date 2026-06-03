---
name: skillsvote
description: "Personalized 'should I install this skill?' assessor. Given a Claude Code / Cursor / Codex skill link (GitHub URL or skills.vote page), score it on two axes — Fit (5 dims: relevance, demand, recency, gap, environment fit against the user's own prompt history and machine) and Quality (3 dims: structure, robustness, executability of SKILL.md itself) — then return a verdict (install / install-with-caveat / save-for-later / skip) plus a one-shot install prompt adapted to the user's environment. Use when the user pastes a skill URL and asks any of: 该不该装, 装不装这个, 评估这个 skill, 评估这个链接, 看看这个 skill 怎么样, 这个 skill 对我有用吗, 值不值得装, 适合我吗, 推荐一下要不要装, should I install this, is this skill worth installing, evaluate this skill, check this skill for me, is this skill a fit, paste skills.vote, paste github skill URL. Do NOT use to optimize the user's own skill (use darwin-skill for that), nor to discover/list skills (this judges a single provided URL)."
---

# SkillsVote

> Judges whether a skill is worth installing for **this** user, on **this** machine — fast static analysis, no test execution required.

## When this skill fires

The user pasted a **specific** skill URL (GitHub repo / folder / SKILL.md / skills.vote page) and asked any variant of "should I install this".

If the user is asking to **improve** their own skill → defer to `darwin-skill`.
If the user is asking what skills **exist** for a problem → this skill cannot help; suggest searching skills.vote or GitHub.

## Two-axis scoring model

| Axis | Source of truth | Weight | What it answers |
|---|---|---|---|
| **Fit** (5 dims) | User's prompt history (`~/.claude/history.jsonl`) + installed skills + available binaries + OS | 0.6 | Is this skill relevant to **me**? |
| **Quality** (3 dims) | The skill's SKILL.md itself (static analysis) | 0.4 | Is this skill **well-written**? |

`final_score = 0.6 × Fit + 0.4 × Quality`, both axes 0–100.

### Fit (5 dims, each 0–100)

| Dim | What it measures |
|---|---|
| 相关 (relevance) | Skill's vocab vs user's prompt vocab — TF-IDF cosine similarity |
| 需求 (demand) | Frequency of matching prompts in user's recent history (decay-weighted) |
| 时效 (recency) | How fresh the demand is — recent prompts weigh more than old ones |
| 缺口 (gap) | Whether user already has a skill covering similar surface (lower if duplicate) |
| 适配 (fit) | Required binaries / runtime / OS — does the user's machine satisfy them? |

### Quality (3 dims, each 0–100, condensed from darwin-skill's 9-dim rubric)

| Dim | Composes darwin's | What it measures |
|---|---|---|
| 写法 (form) | frontmatter + workflow clarity + overall architecture | Is SKILL.md well-structured and readable? |
| 稳健 (robustness) | failure-mode encoding + checkpoint design + anti-pattern blacklist | Does it handle failures, dangerous ops, and edge cases? |
| 可执行 (executable) | actionable specificity + resource integration | Are steps concrete enough to act on without further guessing? |

This skill **does not** evaluate runtime test outputs (darwin's dim 8) — that needs spawning sub-agents and is slow/expensive. Static analysis only.

## Verdict matrix (Fit × Quality quadrants)

| Fit \\ Quality | Quality ≥ 70 | Quality < 70 |
|---|---|---|
| **Fit ≥ 70** | ✅ **install** — strong match | ⚠️ **install-with-caveat** — useful but watch failure paths |
| **Fit < 70** | 💎 **save-for-later** — well-built, not for you now | ❌ **skip** |

## Workflow

### Phase 1: Validate input

Confirm the user supplied a usable link. Accepts:
- GitHub repo: `https://github.com/<owner>/<repo>` (will look for `SKILL.md` at root)
- GitHub folder: `https://github.com/<owner>/<repo>/tree/<branch>/<path>`
- GitHub raw SKILL.md: `.../blob/.../SKILL.md` or raw URL
- skills.vote page: `https://skills.vote/<slug>`
- Local path: a file path on disk

If the URL is ambiguous → **ask once**, do not guess.

🔴 **CHECKPOINT**: if URL is not one of the above shapes, stop and ask user to clarify.

### Phase 2: Fetch + parse

Run `scripts/fetch.py <url>` to retrieve the SKILL.md content and metadata.

Failure modes:
- **HTTP 404 / repo not found** → tell user the URL is dead, stop.
- **No SKILL.md found in repo** → tell user it may not be a Claude-Code-compatible skill, stop.
- **SKILL.md exceeds 200KB** → too large to be a normal skill, warn user and read first 50KB.
- **Network timeout (>15s)** → retry once with 30s timeout; if still fails, stop with clear error.

### Phase 3: Score Fit (uses user's local data)

Run `scripts/score_fit.py --skill-md <path> [--claude-home ~/.claude]`. It will:
1. Read `~/.claude/history.jsonl` (last 90 days; cap at most-recent 5000 entries).
2. Read `~/.claude/skills/` to list installed skill slugs.
3. Probe `PATH` for the binaries the candidate skill declares it needs (`bin:` / `runtime:` hints from SKILL.md frontmatter, or fall back to grep on the content).
4. Emit 5 dim scores + overall Fit (0–100) + raw matched-term evidence.

Failure modes:
- **No `history.jsonl`** → set 相关/需求/时效 to `unknown` (display "—"), continue with 缺口/适配 only. The verdict label becomes `not-enough-history`, ask user whether to install anyway.
- **history.jsonl unreadable / corrupted** → same as above.

### Phase 4: Score Quality (static analysis on SKILL.md)

Run `scripts/score_quality.py --skill-md <path>`. It will:
1. Parse the YAML frontmatter (检查 name / description / 描述质量 / 是否结尾有"灵活应用"等空话).
2. Scan the body for workflow markers (`##`, ordered steps, code blocks), failure-mode language (`if X then Y`, `failure`, `fallback`, `retry`), explicit checkpoints (`🔴`, `STOP`, `CHECKPOINT`), risk blacklist (anti-pattern lists).
3. Detect "vague hedge" patterns (`建议 / 可以考虑 / 视情况而定 / suggest / consider / depending on`) — each ≥3 occurrences subtracts from 可执行.
4. Detect runtime drift (hard-coded "Claude Code" without runtime-neutral phrasing) → flag as warning, not subtract.
5. Emit 3 dim scores + overall Quality (0–100) + reason snippets per dim.

### Phase 5: Render verdict

Run `scripts/render.py` with the two scores + matched evidence to produce the conversation-flow output (a Markdown block — see `references/output-format.md` for the exact template).

Output contains:
- Skill name + total score + verdict label
- 双轴 dim table(Fit 5 行,Quality 3 行)
- 1–2 sentence "why this verdict"(grounded in matched evidence)
- ⚠️ 隐忧 line if any Quality dim < 60 or any Fit warning
- 💡 一键安装 prompt block(adapted to user's environment)

### Phase 6: Emit telemetry

Run `scripts/telemetry.py` to fire one event per logical block above (fetch_start, fetch_done, parse_done, score_fit_done, score_quality_done, verdict_emitted, error_*). Each event carries timing + result bucket, **no skill names, no URLs, no prompts, no paths**. See [references/telemetry-fields.md](references/telemetry-fields.md) for the exact field list.

Telemetry is on by default per the project's data policy. To disable: set `SKILLSVOTE_NO_TELEMETRY=1` in the environment.

## Failure-mode summary

| Symptom | Trigger | First-line fix | Fallback |
|---|---|---|---|
| URL ambiguous | Phase 1 | Ask user once | Stop |
| Repo 404 | Phase 2 | Report URL dead | Stop |
| No SKILL.md | Phase 2 | Report not-a-skill | Stop |
| SKILL.md too large | Phase 2 | Read first 50KB, warn | Score with truncated content |
| Network timeout | Phase 2 | Retry once with 30s | Stop with clear error |
| No history.jsonl | Phase 3 | Fit dims → `unknown` | Continue with 缺口+适配 |
| Telemetry endpoint down | Phase 6 | Drop event silently | User never sees |

## Checkpoints (user-confirmable pauses)

🔴 **CHECKPOINT 1** (Phase 1): If URL shape is ambiguous, stop and ask.
🔴 **CHECKPOINT 2** (after Phase 5): If verdict is `install-with-caveat`, the rendered output includes ⚠️ explaining what to watch — user can choose to proceed or skip the install prompt.

These are explicit, visually-marked pauses — do not silently auto-proceed.

## Anti-pattern blacklist (do NOT do)

| # | Anti-pattern | Why | Do instead |
|---|---|---|---|
| 1 | Mention skill names / URLs in telemetry | Privacy violation, breaks brand promise | Only counts, buckets, durations |
| 2 | Spawn sub-agents to run test prompts | That's darwin-skill's job; expensive and slow | Static analysis only |
| 3 | Read entire `~/.claude/` recursively | Slow, may include private user data | Only `history.jsonl` + `skills/` directory listing |
| 4 | Auto-install the skill | Out of scope; this is an **advisor**, not an installer | Return a copy-paste prompt for the host agent |
| 5 | Hide low Quality scores when Fit is high | Misleads the user | Always show both axes; surface caveat |
| 6 | Hard-code "Claude Code" outside frontmatter triggers | Breaks runtime neutrality (Cursor / Codex / etc.) | Use "host agent" / "skill runtime" |
| 7 | Score with incomplete data without warning | Silent degradation | Mark dims as `unknown`, label verdict `not-enough-history` |

## Resources

- `scripts/assess.py` — main entry; orchestrates Phase 2–6 given a URL
- `scripts/fetch.py` — URL → SKILL.md text + metadata
- `scripts/score_fit.py` — 5-dim personalized scoring
- `scripts/score_quality.py` — 3-dim static analysis of SKILL.md
- `scripts/render.py` — Markdown verdict block
- `scripts/telemetry.py` — anonymous event emitter
- `references/output-format.md` — exact verdict template
- `references/telemetry-fields.md` — every field this skill ever sends
- `references/scoring-algorithm.md` — how each dim is computed
- `test-prompts.json` — typical user prompts (for darwin-skill to evaluate this skill)

## Related skills

- **darwin-skill** — optimize / score your **own** SKILL.md. Complementary: when SkillsVote returns Quality < 60, suggest running darwin-skill on it (only if the user owns that skill).

## Runtime neutrality

This skill is host-agent agnostic. The only "Claude Code"-specific reference is the path `~/.claude/history.jsonl` — replace via `--claude-home <path>` for Cursor (`~/.cursor`) / Codex / other hosts that follow the same convention.
