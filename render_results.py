#!/usr/bin/env python3
"""Render collected market inputs as GitHub-readable Markdown files."""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def report_at_kst(payload: dict[str, Any], report_type: str) -> str:
    window_end = dt.datetime.fromisoformat(payload["window_kst"]["end"])
    report_time = (
        dt.time(hour=8, minute=10)
        if report_type == "MORNING_0810"
        else dt.time(hour=16, minute=30)
    )
    return dt.datetime.combine(
        window_end.date(), report_time, tzinfo=window_end.tzinfo
    ).isoformat()


def render_copy_package(
    payload: dict[str, Any],
    prompt: str,
    report_type: str,
) -> str:
    report_at = report_at_kst(payload, report_type)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    inner = (
        f"REPORT_TYPE: {report_type}\n"
        f"REPORT_AT_KST: {report_at}\n\n"
        f"{prompt.rstrip()}\n\n"
        "MARKET_INPUTS_JSON:\n"
        f"{serialized}\n"
    )
    return (
        "# Gemini 복사·붙여넣기용 최신 입력\n\n"
        "아래 코드블록 오른쪽 위의 복사 버튼을 누른 뒤 내부 Gemini에 그대로 "
        "붙여넣습니다.\n\n"
        "````text\n"
        f"{inner}"
        "````\n"
    )


def display_time(item: dict[str, Any]) -> str:
    if item.get("published_at_kst"):
        return str(item["published_at_kst"])
    if item.get("report_date"):
        return f"미국장 {item['report_date']}"
    return str(item.get("published_text") or "게시시각 확인 불가")


def render_sources(payload: dict[str, Any]) -> str:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in payload["items"]:
        grouped[(str(item["label"]), str(item["source"]))].append(item)

    lines = [
        "# 최신 시장 입력자료",
        "",
        f"- 수집 구간(KST): `{payload['window_kst']['start']}` ~ "
        f"`{payload['window_kst']['end']}`",
        f"- Telegram: **{payload['telegram_count']}건**",
        f"- 오선: **{payload['futuresnow_count']}건**",
        f"- 합계: **{len(payload['items'])}건**",
        "",
    ]
    for (label, source), items in sorted(grouped.items()):
        lines.extend([f"## {html.escape(label)} (`{html.escape(source)}`)", ""])
        for item in items:
            title = html.escape(str(item.get("title") or "(제목 없음)"))
            text = html.escape(str(item.get("text") or "(본문 없음)"))
            url = str(item["url"])
            lines.extend(
                [
                    f"### {html.escape(display_time(item))}",
                    "",
                    f"**{title}** · [원문]({url})",
                    "",
                    "````text",
                    text,
                    "````",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument(
        "--report-type",
        choices=("MORNING_0810", "CLOSE_1630"),
        required=True,
    )
    parser.add_argument("--copy-output", type=Path, required=True)
    parser.add_argument("--sources-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    prompt = args.prompt.read_text(encoding="utf-8")
    args.copy_output.parent.mkdir(parents=True, exist_ok=True)
    args.sources_output.parent.mkdir(parents=True, exist_ok=True)
    args.copy_output.write_text(
        render_copy_package(payload, prompt, args.report_type),
        encoding="utf-8",
    )
    args.sources_output.write_text(render_sources(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
