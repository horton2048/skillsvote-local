# skillsvote

Local-first, **personalized** "should I install this skill?" assessor for Claude Code.

Paste a skill link (GitHub / skills.vote). It scores the skill by how much value
it brings to **you** — based on your local Claude Code usage history and your
actual environment — tells you whether to install it, and generates a one-click
install prompt adapted to your machine. **Your data never leaves your computer.**

## Run it (no install)

```bash
uvx --from "https://github.com/horton2048/skillsvote-local/releases/download/v0.2.1/skillsvote-0.2.1-py3-none-any.whl" skillsvote
```

A local page opens at http://127.0.0.1:8773 — paste a skill link and go.

## Options

```bash
skillsvote --port 8080        # use a different port
skillsvote --no-open          # don't auto-open the browser
skillsvote --claude-home PATH # point at a non-default ~/.claude
```

## How scoring works

Five unified dimensions, all grounded in your real local usage:
**相关 (relevance) · 需求 (demand) · 时效 (recency) · 缺口 (gap) · 适配 (fit)**.

Built on [MemTensor/skills-vote](https://github.com/MemTensor/skills-vote) (MIT).
