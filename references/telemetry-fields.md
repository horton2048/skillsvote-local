# Telemetry fields — exhaustive

Every field that ever leaves the user's machine. Public contract. If a field is not on this list, `scripts/telemetry.py` must not send it.

## Common envelope (every event)

| Field | Type | Source | Why |
|---|---|---|---|
| `event_name` | string enum (see below) | code | Which logical block fired |
| `source` | `"skill"` (constant) | code | Distinguishes from landing/cron events |
| `session_id` | uuid4 (per run) | code | Group events from the same assess() call. Discarded when assess() exits. |
| `device_id` | uuid4 (per machine) | `<claude_home>/skillsvote/device_id.txt` | Aggregate by machine without identifying who owns it. Deletable. |
| `app_version` | `"skill@2.0"` | code | Schema versioning |
| `ts` | timestamptz | server | Server-side now() |
| `client_ip` | inet | server | Captured by Edge Function for spam control. Never sent by client. |
| `props` | jsonb | code | Per-event extras (only fields below) |

## Allowed event names

| Event | When | Allowed props |
|---|---|---|
| `assess_started` | Phase 1 begin | `url_shape` (`github` / `skills_vote` / `local_path` / `http_other` / `unknown`) |
| `fetch_start` | Phase 2 begin | — |
| `fetch_done` | Phase 2 success | `latency_ms`, `size_bucket` (`<10k`/`<50k`/`<200k`/`>=200k`) |
| `fetch_failed` | Phase 2 failure | `err` (exception class name) |
| `parse_done` | After YAML parse | `has_frontmatter`, `has_description_count` (0 or 1) |
| `score_fit_done` | Phase 3 end | `latency_ms`, `has_history`, `total_bucket` (`0-49`/`50-69`/`70-84`/`85-100`) |
| `score_quality_done` | Phase 4 end | `latency_ms`, `total_bucket`, `has_checkpoints`, `has_blacklist` |
| `verdict_emitted` | Phase 5 end | `verdict` (`install` / `install-with-caveat` / `save-for-later` / `skip` / `not-enough-history`), `fit_bucket`, `quality_bucket`, `latency_ms` (total) |
| `error_*` | any phase | `err` (exception class name) |

## Allowed `props` keys (whitelist)

`scripts/telemetry.py:_sanitize()` enforces this. Any key NOT matching one of these patterns is dropped:

- `*_ms` — durations in milliseconds
- `*_bucket` — bucketed score / size ranges
- `*_count` — integer counts
- `has_*` — booleans
- `ok` — success boolean
- `err` — exception class name (e.g. `TimeoutError`, `HTTPError`) — never message body
- `verdict` — string from the allowed-verdict enum above
- `url_shape` — one of the 5 URL shape enums

## Forbidden — must never be sent

| Field | Why |
|---|---|
| Skill name / slug / repo name | Privacy & competitive concern. Aggregating "which skills do people ask about" is interesting but not worth the trust cost. |
| URL (source or any) | Same as above + leaks user's reading interests |
| File paths (any) | May contain username, project structure |
| Prompt content / SKILL.md content | Direct PII exposure |
| User identifiers (email, name, IP from client) | PII |
| Matched terms / matched evidence | Could reverse-engineer prompts |
| Free-form error messages | Tracebacks frequently contain paths and code identifiers |

## Storage

Events land in Supabase table `skillsvote.events` in the **dedicated** `skillsvote-telemetry` project (task #20 will migrate from the temporary shared project).

## Retention

No retention policy set at MVP. Will revisit when table exceeds 100M rows or when GDPR scope is needed.

## How to disable

| Method | Effect |
|---|---|
| Env var `SKILLSVOTE_NO_TELEMETRY=1` | All events dropped, including device_id mint |
| Delete `<claude_home>/skillsvote/device_id.txt` | Next run mints a new ID. Old data is unlinked but not deleted. |
| Set firewall to block `*.supabase.co` | Events fail silently (telemetry is non-blocking) |

## Verifying claims

Reproducible: run `python scripts/assess.py <url> --no-telemetry --json` to inspect every event that *would* fire, without sending. See the wire format in `scripts/telemetry.py:emit()`.
