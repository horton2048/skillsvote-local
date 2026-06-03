"""Fetch a skill's SKILL.md from URL or local path.

Resolves any of:
  - GitHub repo                 → SKILL.md at default branch root
  - GitHub tree URL             → SKILL.md inside that folder
  - GitHub blob URL             → fetch as-is (converted to raw)
  - github.com/raw / raw.github → fetch as-is
  - skills.vote page            → follow underlying GitHub link
  - Local path                  → read directly
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telemetry import SessionContext

MAX_SIZE_BYTES = 200_000
TRUNCATE_TO_BYTES = 50_000
TIMEOUT_FAST = 15
TIMEOUT_SLOW = 30
UA = "skillsvote/2.0 (+https://github.com/horton2048/skillsvote-local)"


@dataclass
class SkillMeta:
    slug: str
    source_url: str
    size: int
    truncated: bool = False
    fetched_at: float = 0.0


# ----------------------------- public entry ----------------------------------


def fetch_skill(url_or_path: str, *, ctx: "SessionContext | None" = None) -> tuple[str, SkillMeta]:
    if ctx is not None:
        from telemetry import emit
        emit(ctx, "fetch_start")

    t0 = time.monotonic()
    src = url_or_path.strip()

    if not src.startswith(("http://", "https://")):
        text, meta = _fetch_local(src)
    else:
        text, meta = _fetch_remote(src)

    truncated = len(text) > MAX_SIZE_BYTES
    if truncated:
        text = text[:TRUNCATE_TO_BYTES]
        meta.truncated = True

    meta.size = len(text)
    meta.fetched_at = time.time()

    if ctx is not None:
        from telemetry import emit
        emit(ctx, "fetch_done", {
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "size_bucket": _size_bucket(meta.size),
        })
    return text, meta


# ----------------------------- local ----------------------------------------


def _fetch_local(path: str) -> tuple[str, SkillMeta]:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"path not found: {p}")
    if p.is_dir():
        candidate = p / "SKILL.md"
        if not candidate.exists():
            raise FileNotFoundError(f"no SKILL.md found in directory: {p}")
        p = candidate
    text = p.read_text(encoding="utf-8")
    slug = _infer_slug(text) or p.parent.name
    return text, SkillMeta(slug=slug, source_url=f"file://{p}", size=len(text))


# ----------------------------- remote ---------------------------------------


def _fetch_remote(url: str) -> tuple[str, SkillMeta]:
    raw_url = _resolve_to_raw_skill_md(url)
    text = _http_get(raw_url)
    slug = _infer_slug(text) or _slug_from_url(url)
    return text, SkillMeta(slug=slug, source_url=url, size=len(text))


def _resolve_to_raw_skill_md(url: str) -> str:
    """Map any user-pasted URL shape to a raw SKILL.md URL we can fetch."""
    if "raw.githubusercontent.com" in url or url.endswith("/SKILL.md"):
        return url

    # github.com/<owner>/<repo>/blob/<branch>/<path>
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$", url)
    if m:
        owner, repo, branch, path = m.groups()
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    # github.com/<owner>/<repo>/tree/<branch>/<path>
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)$", url)
    if m:
        owner, repo, branch, path = m.groups()
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path.rstrip('/')}/SKILL.md"

    # github.com/<owner>/<repo> (repo root → default branch root SKILL.md)
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?$", url)
    if m:
        owner, repo = m.groups()
        repo = repo.removesuffix(".git")
        branch = _github_default_branch(owner, repo)
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/SKILL.md"

    # skills.vote — follow page and look for canonical github link
    if "skills.vote" in url:
        page = _http_get(url)
        m = re.search(r'href="(https://github\.com/[^"]+)"', page)
        if not m:
            raise ValueError("skills.vote page found no github link")
        return _resolve_to_raw_skill_md(m.group(1))

    # Last resort: assume direct file URL
    return url


def _github_default_branch(owner: str, repo: str) -> str:
    """Try /repos API; fall back to 'main', then 'master'."""
    try:
        api = f"https://api.github.com/repos/{owner}/{repo}"
        info = json.loads(_http_get(api))
        b = info.get("default_branch")
        if isinstance(b, str) and b:
            return b
    except (urllib.error.URLError, json.JSONDecodeError, ValueError):
        pass
    # Fall through: try 'main' then 'master' at fetch time. Caller will retry.
    return "main"


# ----------------------------- HTTP -----------------------------------------


def _http_get(url: str, *, timeout: float = TIMEOUT_FAST) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(MAX_SIZE_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code == 404 and url.endswith("/main/SKILL.md"):
            return _http_get(url.replace("/main/", "/master/"))
        raise
    except (urllib.error.URLError, TimeoutError) as e:
        if timeout < TIMEOUT_SLOW:
            return _http_get(url, timeout=TIMEOUT_SLOW)
        raise RuntimeError(f"network failed twice for {url}: {e}") from e

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


# ----------------------------- helpers --------------------------------------


def _infer_slug(skill_md: str) -> str | None:
    m = re.search(r"^---\s*\n(.*?)\n---", skill_md, re.S | re.M)
    if not m:
        return None
    nm = re.search(r"^\s*name\s*:\s*['\"]?([\w.-]+)['\"]?\s*$",
                   m.group(1), re.M)
    return nm.group(1).strip() if nm else None


def _slug_from_url(url: str) -> str:
    m = re.search(r"github\.com/[^/]+/([^/]+)", url)
    if m:
        return m.group(1).removesuffix(".git").lower()
    return "unknown"


def _size_bucket(size: int) -> str:
    if size < 10_000:
        return "<10k"
    if size < 50_000:
        return "<50k"
    if size < MAX_SIZE_BYTES:
        return "<200k"
    return ">=200k"


# ----------------------------- CLI ------------------------------------------


def _main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("url_or_path")
    args = p.parse_args()
    text, meta = fetch_skill(args.url_or_path)
    print(f"slug      : {meta.slug}")
    print(f"source    : {meta.source_url}")
    print(f"size      : {meta.size}")
    print(f"truncated : {meta.truncated}")
    print(f"---\n{text[:300]}\n...")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
