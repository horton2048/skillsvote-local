from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from skillsvote import (
    ScoreWeights,
    SkillDescriptor,
    load_skills,
    rank_skills_for_user,
    scan_user_profile,
    score_skills,
)
from skillsvote.tokenize import extract_slash_commands, tokenize


def _write_skill(skills_dir: Path, name: str, description: str) -> None:
    skill = skills_dir / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        f'---\nname: "{name}"\ndescription: "{description}"\n---\n\n# {name}\n',
        encoding="utf-8",
    )


def _write_history(home: Path, prompts: list[str], *, now_ms: int) -> None:
    lines = []
    for i, text in enumerate(prompts):
        lines.append(
            json.dumps(
                {
                    "display": text,
                    "pastedContents": {},
                    "timestamp": now_ms - i * 60_000,
                    "project": "C:\\Users\\test",
                    "sessionId": "s1",
                },
                ensure_ascii=False,
            )
        )
    (home / "history.jsonl").write_text("\n".join(lines), encoding="utf-8")


def test_tokenize_mixed_language():
    tokens = set(tokenize("帮我写一篇公众号文章 use frontend-design"))
    assert "公众" in tokens
    assert "文章" in tokens
    assert "frontend-design" in tokens
    assert "use" not in tokens  # stopword
    assert "帮" not in tokens  # single CJK only kept when isolated run


def test_extract_slash_commands():
    assert extract_slash_commands("用 /browse 打开网页再 /wechat-mp-article") == [
        "browse",
        "wechat-mp-article",
    ]


def test_scan_user_profile(tmp_path: Path):
    now = int(time.time() * 1000)
    _write_history(
        tmp_path,
        ["帮我写公众号文章", "用 /browse 测试网站", "再写一篇小红书"],
        now_ms=now,
    )
    profile = scan_user_profile(tmp_path, now_ms=now)
    assert profile.prompt_count == 3
    assert profile.doc_freq("公众") == 1
    assert profile.used_slugs.get("browse") == 1


def test_relevant_skill_outranks_irrelevant(tmp_path: Path):
    now = int(time.time() * 1000)
    _write_history(
        tmp_path,
        [
            "帮我写一篇公众号文章",
            "把这个转成小红书内容",
            "公众号排版优化一下",
            "再写一篇公众号推广",
        ],
        now_ms=now,
    )
    profile = scan_user_profile(tmp_path, now_ms=now)

    skills = [
        SkillDescriptor(name="wechat-mp-article", description="为微信公众号撰写文章并排版"),
        SkillDescriptor(name="kubernetes-operator", description="manage kubernetes cluster operators"),
    ]
    scores = {s.skill_name: s for s in score_skills(skills, profile)}

    assert scores["wechat-mp-article"].value > scores["kubernetes-operator"].value
    # Irrelevant skill earns essentially nothing.
    assert scores["kubernetes-operator"].value < 1.0
    # Relevant skill has real signal and is in range.
    assert scores["wechat-mp-article"].matched_prompt_count >= 3
    assert 0.0 <= scores["wechat-mp-article"].value <= 100.0


def test_gap_dimension_rewards_uninstalled(tmp_path: Path):
    now = int(time.time() * 1000)
    # User does wechat tasks a lot; for one variant they already invoke the slash command.
    _write_history(
        tmp_path,
        ["写公众号文章"] * 4 + ["用 /wechat-mp-article 写公众号"],
        now_ms=now,
    )
    profile = scan_user_profile(tmp_path, now_ms=now)
    skill = SkillDescriptor(name="wechat-mp-article", description="微信公众号文章")
    [score] = score_skills([skill], profile)
    assert score.already_have is True


def test_rank_skills_for_user_orders_by_value(tmp_path: Path):
    now = int(time.time() * 1000)
    _write_history(tmp_path, ["公众号文章写作"] * 5, now_ms=now)
    profile = scan_user_profile(tmp_path, now_ms=now)
    ranked = rank_skills_for_user(
        ["kubernetes-operator", "wechat-mp-article"],
        profile=profile,
    )
    assert [s.skill_name for s in ranked][0] == "wechat-mp-article"
    assert ranked == sorted(ranked, key=lambda s: s.value, reverse=True)


def test_empty_profile_scores_zero(tmp_path: Path):
    now = int(time.time() * 1000)
    profile = scan_user_profile(tmp_path, now_ms=now)  # no history.jsonl
    assert profile.prompt_count == 0
    [score] = score_skills([SkillDescriptor(name="anything", description="does things")], profile)
    assert score.value == 0.0


def test_weights_must_sum_to_one():
    ScoreWeights()  # defaults are valid
    with pytest.raises(ValidationError):
        ScoreWeights(relevance=0.9, demand=0.9, recency=0.0, gap=0.0, fit=0.0)


def test_fetch_github_url_resolution(monkeypatch):
    from skillsvote import fetch as fetch_mod

    captured = {}

    def fake_http_get(url: str) -> str:
        captured["url"] = url
        return '---\nname: "foo-skill"\ndescription: "uses git and docker"\n---\n# foo\n'

    monkeypatch.setattr(fetch_mod, "_http_get", fake_http_get)
    result = fetch_mod.fetch_skill("https://github.com/o/r/tree/main/skills/foo")
    assert result.descriptor.name == "foo-skill"
    assert result.install_ref == "o/r"
    assert result.skill_path == "skills/foo"
    assert captured["url"] == "https://raw.githubusercontent.com/o/r/main/skills/foo/SKILL.md"


def test_assess_local_skill(tmp_path: Path):
    from skillsvote.assess import assess_skill

    now = int(time.time() * 1000)
    home = tmp_path / "home"
    home.mkdir()
    _write_history(home, ["帮我写公众号文章"] * 4 + ["公众号排版"], now_ms=now)

    skill_dir = tmp_path / "wechat-mp-article"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        '---\nname: "wechat-mp-article"\ndescription: "微信公众号文章排版与配图"\n---\n# 公众号\n',
        encoding="utf-8",
    )

    result = assess_skill(str(skill_dir), claude_home=home)
    assert result.skill_name == "wechat-mp-article"
    assert result.score.value > 0
    assert result.verdict in {"install", "optional", "skip", "already"}
    assert "wechat-mp-article" in result.install_prompt
    assert result.env.os_supported is True


def test_load_skills_parses_and_excludes(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "wechat-mp-article", "微信公众号文章")
    _write_skill(skills_dir, "pers-20260516-abc", "auto generated persona memory")
    _write_skill(skills_dir, "seed-pers-xyz", "seed persona")

    everything = load_skills(skills_dir)
    assert {d.name for d in everything} == {
        "wechat-mp-article",
        "pers-20260516-abc",
        "seed-pers-xyz",
    }
    found = next(d for d in everything if d.name == "wechat-mp-article")
    assert found.description == "微信公众号文章"
    assert found.source == "frontmatter"

    filtered = load_skills(skills_dir, exclude=["pers-*", "seed-*"])
    assert {d.name for d in filtered} == {"wechat-mp-article"}
