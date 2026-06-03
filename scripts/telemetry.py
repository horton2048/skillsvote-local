"""Anonymous telemetry: one event per logical block, sent to Supabase Edge Function.

Hard rules (see ../references/telemetry-fields.md for the contract):
  - NEVER send skill names, URLs, paths, prompts, repo names, user identifiers.
  - Only buckets, durations, types, counts.
  - source = "skill" for every event from this skill.
  - device_id = stable random UUID stored in <claude_home>/skillsvote/device_id.txt
    (one per machine; if you reset it, it counts as a different "machine"; never identifies a person).

Disabled if:
  - SKILLSVOTE_NO_TELEMETRY=1 in env
  - SessionContext(disabled=True) at construction
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# TODO(task #20): swap to the new dedicated project endpoint once created.
TELEMETRY_URL = "https://qsucbumdikaczbjpfdmv.supabase.co/functions/v1/skillsvote-track"
TIMEOUT_S = 2.0  # fail fast — never block the user-facing flow


@dataclass
class SessionContext:
    session_id: str
    device_id: str | None
    app_version: str = "skill@2.0"
    disabled: bool = False
    started_at: float = field(default_factory=time.monotonic)


def session_context(disabled: bool = False, claude_home: Path | None = None) -> SessionContext:
    """Build a context for one assess() run.

    session_id   — uuid4, lives for this single run
    device_id    — persisted at <claude_home>/skillsvote/device_id.txt
    """
    home = claude_home or Path(os.path.expanduser("~/.claude"))
    device_id = _load_or_mint_device_id(home) if not disabled else None
    return SessionContext(
        session_id=str(uuid.uuid4()),
        device_id=device_id,
        disabled=disabled,
    )


def emit(ctx: SessionContext, event_name: str, props: dict | None = None) -> None:
    """Fire-and-forget event. Never raise; never block the caller meaningfully."""
    if ctx.disabled:
        return
    payload = {
        "event_name": event_name,
        "source": "skill",
        "session_id": ctx.session_id,
        "device_id": ctx.device_id,
        "app_version": ctx.app_version,
        "props": _sanitize(props or {}),
    }
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            TELEMETRY_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_S):
            pass
    except (urllib.error.URLError, TimeoutError, OSError):
        # Telemetry MUST NOT crash the assess flow.
        pass


def _sanitize(props: dict) -> dict:
    """Strip any keys that look like they could contain PII.

    Allowed keys: latency_ms, *_bucket, count, *_count, ok, err, verdict, has_*
    Anything else → drop with a warning key.
    """
    out: dict = {}
    for k, v in props.items():
        if (
            k.endswith("_ms")
            or k.endswith("_bucket")
            or k.endswith("_count")
            or k in {"ok", "err", "verdict", "url_shape"}
            or k.startswith("has_")
        ):
            out[k] = v
    return out


def _load_or_mint_device_id(claude_home: Path) -> str:
    d = claude_home / "skillsvote"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "device_id.txt"
    if f.exists():
        try:
            return f.read_text().strip() or str(uuid.uuid4())
        except OSError:
            pass
    new_id = str(uuid.uuid4())
    try:
        f.write_text(new_id)
    except OSError:
        pass
    return new_id
