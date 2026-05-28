from __future__ import annotations

import argparse
from pathlib import Path


def run(argv: list[str] | None = None) -> None:
    """Console entry point: launch the local 'should I install this skill?' web app."""
    parser = argparse.ArgumentParser(
        prog="skillsvote",
        description="本地优先的 skill 个性化评估：粘一个 skill 链接，基于你本地的"
        "使用习惯和环境给出评分、安装建议和一键安装提示词。",
    )
    parser.add_argument("--port", type=int, default=8773, help="本地端口（默认 8773）")
    parser.add_argument(
        "--claude-home",
        type=Path,
        default=None,
        help="Claude Code 主目录（默认 ~/.claude）",
    )
    parser.add_argument("--no-open", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args(argv)

    from skills_vote.score.web import serve

    serve(port=args.port, claude_home=args.claude_home, open_browser=not args.no_open)


if __name__ == "__main__":
    run()
