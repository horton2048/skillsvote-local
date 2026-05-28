from __future__ import annotations

import re
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path

import yaml

from skillsvote.model import SkillDescriptor

_FRONTMATTER_RE = re.compile(r"^﻿?---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(raw: str, fallback_name: str, *, path: str | None = None) -> SkillDescriptor:
    """Build a SkillDescriptor from SKILL.md text, preferring YAML frontmatter."""
    match = _FRONTMATTER_RE.match(raw)
    if match is not None:
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        if isinstance(meta, dict):
            name = str(meta.get("name") or fallback_name).strip() or fallback_name
            description = str(meta.get("description") or "").strip()
            return SkillDescriptor(
                name=name, description=description, path=path, source="frontmatter"
            )
    return SkillDescriptor(name=fallback_name, path=path, source="dirname")


def parse_skill_md(skill_md_path: Path) -> SkillDescriptor:
    """Parse a SKILL.md file, preferring YAML frontmatter for name/description."""
    fallback_name = skill_md_path.parent.name or skill_md_path.stem
    try:
        raw = skill_md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return SkillDescriptor(name=fallback_name, path=str(skill_md_path), source="dirname")
    return parse_frontmatter(raw, fallback_name, path=str(skill_md_path))


def _is_excluded(descriptor: SkillDescriptor, patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return False
    targets = [descriptor.name]
    if descriptor.path:
        targets.append(descriptor.path.replace("\\", "/"))
    return any(fnmatch(target, pattern) for target in targets for pattern in patterns)


def load_skills(
    skills_dir: Path, *, exclude: Iterable[str] | None = None
) -> list[SkillDescriptor]:
    """Discover every SKILL.md beneath ``skills_dir``.

    Supports both flat layouts (``skills_dir/<slug>/SKILL.md``) and nested
    plugin layouts, deduplicating by skill name (first wins). ``exclude`` is a
    list of glob patterns matched against each skill's name and path, used to
    drop noise such as auto-generated persona/memory artifacts (``pers-*``).
    """
    skills_dir = Path(skills_dir)
    if not skills_dir.exists():
        raise FileNotFoundError(f"skills directory not found: {skills_dir}")

    patterns = tuple(exclude or ())
    descriptors: list[SkillDescriptor] = []
    seen: set[str] = set()
    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        descriptor = parse_skill_md(skill_md)
        if descriptor.name in seen or _is_excluded(descriptor, patterns):
            continue
        seen.add(descriptor.name)
        descriptors.append(descriptor)
    return descriptors
