from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from skills_vote.score.usage_scan import default_claude_home

OsKind = Literal["windows", "macos", "linux", "other"]

# Tools a skill commonly assumes exist; probed with shutil.which.
COMMON_BINS = (
    "git", "node", "npm", "npx", "python", "python3", "uv", "pip",
    "docker", "gh", "pwsh", "bash", "curl", "jq", "rg",
)


class LocalEnvironment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    os_kind: OsKind
    platform: str
    shell: str
    skills_dir: str
    installed_skills: list[str] = Field(default_factory=list)
    bins_present: dict[str, bool] = Field(default_factory=dict)

    def has_bin(self, name: str) -> bool:
        return self.bins_present.get(name, shutil.which(name) is not None)


def detect_os_kind() -> OsKind:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


def detect_shell(os_kind: OsKind) -> str:
    shell_env = os.environ.get("SHELL", "")
    if shell_env:
        return Path(shell_env).name
    if os.environ.get("PSModulePath"):
        return "PowerShell"
    if os_kind == "windows":
        return "PowerShell"
    return "bash"


def list_installed_skills(skills_dir: Path) -> list[str]:
    if not skills_dir.exists():
        return []
    names: list[str] = []
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            names.append(child.name)
    return names


def probe_bins(names: tuple[str, ...] = COMMON_BINS) -> dict[str, bool]:
    return {name: shutil.which(name) is not None for name in names}


def detect_environment(claude_home: Path | None = None) -> LocalEnvironment:
    home = claude_home or default_claude_home()
    skills_dir = home / "skills"
    os_kind = detect_os_kind()
    return LocalEnvironment(
        os_kind=os_kind,
        platform=sys.platform,
        shell=detect_shell(os_kind),
        skills_dir=str(skills_dir),
        installed_skills=list_installed_skills(skills_dir),
        bins_present=probe_bins(),
    )
