from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from skills_vote.score.model import SkillDescriptor
from skills_vote.score.skill_source import parse_frontmatter, parse_skill_md

_UA = "skills-vote-scoring/0.1 (+local skill assessor)"
_TIMEOUT = 15
_DEFAULT_BRANCHES = ("main", "master")


@dataclass
class FetchedSkill:
    descriptor: SkillDescriptor
    body: str
    source_url: str
    raw_url: str | None = None
    origin: str = "github"  # github | skills.vote | local
    install_ref: str | None = None  # e.g. "owner/repo"
    skill_path: str | None = None  # path of the skill folder within the repo
    candidates_tried: list[str] = field(default_factory=list)


class SkillFetchError(RuntimeError):
    pass


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (trusted host check below)
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _try_fetch(url: str) -> str | None:
    try:
        return _http_get(url)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None


def _parse_github(link: str) -> tuple[str, str, str | None, str | None]:
    """Return (owner, repo, branch|None, path|None) from a GitHub-ish link."""
    link = link.strip()
    # raw.githubusercontent.com/owner/repo/branch/path...
    m = re.match(
        r"https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$", link
    )
    if m:
        return m.group(1), m.group(2), m.group(3), m.group(4)
    # github.com/owner/repo[/blob|tree/branch/path...]
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)(?:/(?:blob|tree)/([^/]+)/(.+))?/?$", link)
    if m:
        return m.group(1), m.group(2).removesuffix(".git"), m.group(3), m.group(4)
    # owner/repo[/path] shorthand
    m = re.match(r"^([\w.-]+)/([\w.-]+)(?:/(.+))?$", link)
    if m:
        return m.group(1), m.group(2).removesuffix(".git"), None, m.group(3)
    raise SkillFetchError(f"无法识别的 GitHub 链接: {link}")


def _raw_candidates(owner: str, repo: str, branch: str | None, path: str | None) -> list[str]:
    branches = (branch,) if branch else _DEFAULT_BRANCHES
    # Normalize path: if it already ends with SKILL.md use as-is, else append it.
    sub_paths: list[str] = []
    if path:
        p = path.rstrip("/")
        sub_paths = [p] if p.lower().endswith("skill.md") else [f"{p}/SKILL.md"]
    else:
        sub_paths = ["SKILL.md"]
    base = "https://raw.githubusercontent.com"
    return [f"{base}/{owner}/{repo}/{b}/{sp}" for b in branches for sp in sub_paths]


def _fetch_github(link: str) -> FetchedSkill:
    owner, repo, branch, path = _parse_github(link)
    candidates = _raw_candidates(owner, repo, branch, path)
    tried: list[str] = []
    for raw_url in candidates:
        tried.append(raw_url)
        body = _try_fetch(raw_url)
        if body is None:
            continue
        skill_path = path.rstrip("/") if path else ""
        skill_path = re.sub(r"/?SKILL\.md$", "", skill_path, flags=re.IGNORECASE)
        fallback = skill_path.rsplit("/", 1)[-1] if skill_path else repo
        descriptor = parse_frontmatter(body, fallback or repo, path=raw_url)
        return FetchedSkill(
            descriptor=descriptor,
            body=body,
            source_url=link,
            raw_url=raw_url,
            origin="github",
            install_ref=f"{owner}/{repo}",
            skill_path=skill_path or None,
            candidates_tried=tried,
        )
    raise SkillFetchError(
        "在该 GitHub 链接下没找到 SKILL.md。试过:\n  " + "\n  ".join(tried)
    )


_GH_LINK_RE = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+[^\s\"'<>)]*")
_RAW_LINK_RE = re.compile(r"https?://raw\.githubusercontent\.com/[^\s\"'<>)]+SKILL\.md", re.I)


def _fetch_skills_vote(link: str) -> FetchedSkill:
    page = _try_fetch(link)
    if page is None:
        raise SkillFetchError(f"打不开 skills.vote 链接: {link}")
    # SkillsVote indexes GitHub SKILL.md files, so a skill page should reference
    # a GitHub source. Extract it and delegate to the GitHub fetcher.
    raw = _RAW_LINK_RE.search(page)
    if raw:
        result = _fetch_github(raw.group(0))
        result.origin = "skills.vote"
        result.source_url = link
        return result
    gh = _GH_LINK_RE.search(page)
    if gh:
        result = _fetch_github(gh.group(0))
        result.origin = "skills.vote"
        result.source_url = link
        return result
    raise SkillFetchError(
        "这个 skills.vote 页面里没找到可用的 GitHub 源链接。"
        "可以把该技能对应的 GitHub 链接直接贴进来。"
    )


def _fetch_local(path: Path) -> FetchedSkill:
    skill_md = path / "SKILL.md" if path.is_dir() else path
    if not skill_md.exists():
        raise SkillFetchError(f"本地路径下没有 SKILL.md: {skill_md}")
    descriptor = parse_skill_md(skill_md)
    return FetchedSkill(
        descriptor=descriptor,
        body=skill_md.read_text(encoding="utf-8", errors="replace"),
        source_url=str(skill_md),
        origin="local",
        skill_path=str(skill_md.parent),
    )


def fetch_skill(link: str) -> FetchedSkill:
    """Resolve a skill link (GitHub / skills.vote / local path) to its SKILL.md."""
    link = link.strip()
    if not link:
        raise SkillFetchError("链接为空。")
    low = link.lower()
    if "skills.vote" in low:
        return _fetch_skills_vote(link)
    if "github.com" in low or "raw.githubusercontent.com" in low:
        return _fetch_github(link)
    # local path?
    candidate = Path(link)
    if candidate.exists():
        return _fetch_local(candidate)
    # bare owner/repo shorthand
    if re.match(r"^[\w.-]+/[\w.-]+(/.+)?$", link):
        return _fetch_github(link)
    raise SkillFetchError(f"无法识别的链接形式: {link}")
