from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skillsvote.model import ScoreConfig
from skillsvote.scorer import rank_skills_for_user, score_skill_library
from skillsvote.usage_scan import default_claude_home, scan_user_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m skillsvote",
        description="Score agent skills by personalized value to the local user.",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=Path.home() / ".claude" / "skills",
        help="Directory containing skills (each with a SKILL.md).",
    )
    parser.add_argument(
        "--claude-home",
        type=Path,
        default=default_claude_home(),
        help="Claude Code home directory holding history.jsonl.",
    )
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument(
        "--rank",
        nargs="*",
        default=None,
        help="Only rank these candidate skill names (recommendation re-ranking).",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=None,
        help="Glob patterns (matched on skill name/path) to skip, e.g. 'pers-*' 'seed-*'.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    parser.add_argument(
        "--html",
        nargs="?",
        const=str(_default_html_path()),
        default=None,
        help="Render a 'For You' web page. Optionally pass an output path.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated --html page in the default browser.",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch the local 'should I install this?' web app.",
    )
    parser.add_argument("--port", type=int, default=8773, help="Port for --web.")
    parser.add_argument(
        "--assess",
        metavar="LINK",
        default=None,
        help="Assess a single skill link (GitHub / skills.vote) and print the verdict.",
    )
    return parser


def _default_html_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "output" / "for-you.html"


def _run_assess(link: str, *, claude_home: Path | None, as_json: bool) -> None:
    from skillsvote.assess import assess_skill

    result = assess_skill(link, claude_home=claude_home)
    if as_json:
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return
    print(f"技能: {result.skill_name}  ({result.origin})")
    print(f"评分: {result.score.value:.0f}/100  →  {result.verdict_label}")
    print(f"理由: {result.verdict_reason}\n")
    print("─── 一键安装提示词 ───")
    print(result.install_prompt)


def main(argv: list[str] | None = None) -> None:
    # Windows consoles often default to a non-UTF-8 code page; force UTF-8 so
    # Chinese skill names and reasons render correctly.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    args = build_parser().parse_args(argv)
    config = ScoreConfig()

    if args.web:
        from skillsvote.web import serve

        serve(claude_home=args.claude_home, port=args.port)
        return

    if args.assess:
        _run_assess(args.assess, claude_home=args.claude_home, as_json=args.json)
        return

    profile = scan_user_profile(args.claude_home)

    if args.rank:
        scores = rank_skills_for_user(
            args.rank,
            skills_dir=args.skills_dir if args.skills_dir.exists() else None,
            profile=profile,
            config=config,
        )
    else:
        scores = score_skill_library(
            args.skills_dir, profile=profile, config=config, exclude=args.exclude
        )

    skills_evaluated = len(scores)
    if args.top_k > 0:
        scores = scores[: args.top_k]

    if args.html is not None:
        from skillsvote.report import render_html

        out_path = Path(args.html)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            render_html(
                scores,
                prompt_count=profile.prompt_count,
                skills_evaluated=skills_evaluated,
            ),
            encoding="utf-8",
        )
        print(f"已生成 For You 页面: {out_path}")
        if args.open:
            import webbrowser

            webbrowser.open(out_path.as_uri())
        return

    if args.json:
        print(
            json.dumps(
                {
                    "prompt_count": profile.prompt_count,
                    "scores": [s.model_dump() for s in scores],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"扫描到 {profile.prompt_count} 条本地使用记录。按“对我的价值”排序：\n")
    print(f"{'#':>2}  {'分数':>6}  {'命中':>4}  技能 / 理由")
    print("-" * 72)
    for rank, score in enumerate(scores, start=1):
        print(f"{rank:>2}  {score.value:>6.1f}  {score.matched_prompt_count:>4}  {score.skill_name}")
        if score.reason:
            print(f"{'':>16}{score.reason}")


if __name__ == "__main__":
    main()
