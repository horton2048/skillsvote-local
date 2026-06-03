# Scoring algorithm — per-dim math

Read this when implementing or auditing `scripts/score_fit.py` and `scripts/score_quality.py`.

## Fit axis (5 dims, each 0-100; total = mean of available dims)

### 1. 相关 (relevance) — vocab overlap

```
skill_terms   = unique noun/verb tokens extracted from SKILL.md (lowercase, stopwords removed,
                length ≥ 3, capped at 200 terms ranked by inverse document frequency)
history_terms = same extractor applied to user's prompts (last 90d / 5000 cap)

cosine = (|skill_terms ∩ history_terms|) /
         sqrt(|skill_terms| × |history_terms|)
relevance = clamp(100 × (cosine × 4), 0, 100)   # rare overlaps still register
```

Edge: stopwords list is in `assets/stopwords-en-zh.txt` (TODO add). For Chinese, use jieba in accurate mode.

### 2. 需求 (demand) — recent-prompt frequency

```
matched = [p for p in history if any(t in p.lower() for t in skill_terms[:30])]
weighted = Σ (e^(-age_days / 30)) for p in matched      # 30-day half-life
demand   = clamp(100 × tanh(weighted / 5), 0, 100)      # saturates around 5+ recent hits
```

Why tanh: caps benefit of "I prompt about this 100 times" so dominant-but-irrelevant terms can't dominate.

### 3. 时效 (recency) — freshness of matched prompts

```
if not matched: recency = None
else:
    avg_age_days = mean(p.age_days for p in matched)
    recency      = clamp(100 - avg_age_days × 1.5, 0, 100)
                   # age 0 days  → 100
                   # age 30 days → 55
                   # age 60 days → 10
```

### 4. 缺口 (gap) — duplicate-avoidance

```
installed_slugs = listdir(<claude_home>/skills/)
clash_score = max(jaro_winkler(this_slug, s) for s in installed_slugs)  # 0-1
gap        = 100 × (1 - clash_score)
            # e.g. installed "pdf-tools"; candidate "pdf-master" → JW≈0.85 → gap=15
```

Plus: also compare top-5 skill_terms against keywords parsed from installed skills' descriptions
(when readable). Take min(slug-gap, terms-gap).

### 5. 适配 (fit_env) — required-binary presence

```
required_bins = parse from SKILL.md frontmatter `bin:` or `runtime:`,
                fallback: extract `[a-z][a-z0-9-]{2,}` tokens after `which ` or in code blocks.
present       = [b for b in required_bins if shutil.which(b)]

if not required_bins: fit_env = 100   # nothing claimed = nothing missing
else:                 fit_env = 100 × len(present) / len(required_bins)
```

OS gate: if SKILL.md says `os: macOS` and user is on Windows → fit_env capped at 0.

### Total Fit

```
available = [d for d in [relevance, demand, recency, gap, fit_env] if d is not None]
fit_total = mean(available) if available else None
```

If `relevance / demand / recency` are all None (no history) → emit `not-enough-history` verdict.

---

## Quality axis (3 dims, each 0-100; total = mean)

### 6. 写法 (form) — darwin 1 + 2 + 7 condensed

Score starts at 100, deductions:

| Check | Deduction | Why |
|---|---|---|
| YAML frontmatter missing or unparseable | -40 | Required by spec |
| `name:` field missing | -20 | Required |
| `description:` missing | -25 | Required & is the trigger |
| `description` length < 64 chars | -10 | Too terse to disambiguate triggers |
| `description` length > 1024 chars | -5 | Wastes context budget |
| `description` ends with "灵活应用 / 根据情况 / case by case" | -8 | Empty hedge tail (darwin dim 1 rule) |
| No `##` or `###` headers in body | -15 | No section structure |
| No ordered steps detected (`\d\.\s`, `Step \d`, `Phase \d`) | -10 | No procedural workflow |
| >5 consecutive blank lines | -3 each | AI-slop tell |
| File length > 10k tokens (~7500 words) | -5 | Exceeds skill body budget |

### 7. 稳健 (robustness) — darwin 3 + 4 + 9 condensed

Score starts at 100, deductions:

| Check | Deduction |
|---|---|
| Zero "if X then Y" / "if X, fallback to" / "on failure" patterns | -30 |
| Zero visible CHECKPOINT markers (🔴, STOP, CHECKPOINT) | -15 |
| Zero anti-pattern / blacklist / "do NOT" section | -20 |
| Destructive ops (rm -rf, git reset --hard, force push) mentioned without explicit warning around them | -15 |
| Body mentions sub-agent spawning but no failure path for sub-agent unavailable | -8 |

### 8. 可执行 (executable) — darwin 5 + 6 condensed

Score starts at 100, deductions:

| Check | Deduction |
|---|---|
| "vague hedge" words density ≥3 occurrences in body (建议/可以考虑/视情况/suggest/consider/depending on) | -10 (then -2 per extra occurrence, cap -25) |
| No code blocks / no concrete command examples | -15 |
| Referenced files (`references/`, `scripts/`, `assets/`) listed but at least one path does not resolve | -10 |
| Steps phrased without subject/verb (e.g. "Processing" instead of "Process the …") | -5 |

### Warnings (no deduction, surfaced in `warnings`)

- Hardcoded "Claude Code" / "in Claude Code" / "Claude Code skill" outside frontmatter triggers
  — flag `runtime_drift`. Display in output but don't penalize.

### Total Quality

```
quality_total = (form + robustness + executable) / 3
```

---

## Final verdict

```
final = 0.6 × fit_total + 0.4 × quality_total

verdict =
  "install"             if fit ≥ 70 and quality ≥ 70
  "install-with-caveat" if fit ≥ 70 and quality < 70
  "save-for-later"      if fit < 70 and quality ≥ 70
  "skip"                if fit < 70 and quality < 70
  "not-enough-history"  if fit_total is None
```

Threshold 70 was chosen so that a skill needs to be "clearly above average" on its axis to flip the verdict — empirically anything 50-69 is "lukewarm" in user testing. Revisit when we have ≥100 real verdicts to compute base rate.
