"""Collect 오선의 미국 증시 요약 from the public YouTube Posts page."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Iterable


CHANNEL_URL = "https://www.youtube.com/@futuresnow/posts"
DATE_RE = re.compile(
    r"(?P<year>20\d{2})\s*년\s*(?P<month>\d{1,2})\s*월\s*(?P<day>\d{1,2})\s*일"
)


def fetch_html(
    *,
    ssl_context,
    user_agent: str,
    timeout: float,
    retries: int,
    url: str = CHANNEL_URL,
) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(
                request, timeout=timeout, context=ssl_context
            ) as response:
                return response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(min(2**attempt, 8))
    assert last_error is not None
    raise last_error


def extract_initial_data(page_html: str) -> dict[str, Any]:
    markers = (
        "var ytInitialData = ",
        'window["ytInitialData"] = ',
        "ytInitialData = ",
    )
    decoder = json.JSONDecoder()
    for marker in markers:
        offset = 0
        while True:
            marker_pos = page_html.find(marker, offset)
            if marker_pos < 0:
                break
            object_pos = page_html.find("{", marker_pos + len(marker))
            if object_pos < 0:
                break
            try:
                value, _ = decoder.raw_decode(page_html[object_pos:])
            except json.JSONDecodeError:
                offset = marker_pos + len(marker)
                continue
            if isinstance(value, dict) and "contents" in value:
                return value
            offset = marker_pos + len(marker)
    raise ValueError("YouTube page did not contain a usable ytInitialData object")


def iter_renderers(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        renderer = value.get("backstagePostRenderer")
        if isinstance(renderer, dict):
            yield renderer
        for child in value.values():
            yield from iter_renderers(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_renderers(child)


def text_from_runs(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    simple = value.get("simpleText")
    if isinstance(simple, str):
        return simple.strip()
    runs = value.get("runs")
    if not isinstance(runs, list):
        return ""
    return "".join(
        run.get("text", "")
        for run in runs
        if isinstance(run, dict) and isinstance(run.get("text"), str)
    ).strip()


def report_date_from_text(text: str) -> str | None:
    match = DATE_RE.search(text[:200])
    if not match:
        return None
    try:
        value = dt.date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError:
        return None
    return value.isoformat()


def parse_posts(
    page_html: str,
    *,
    collected_at: dt.datetime,
    title_contains: str = "미국 증시 요약",
    limit: int = 5,
    max_text_chars: int = 30_000,
) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for renderer in iter_renderers(extract_initial_data(page_html)):
        post_id = str(renderer.get("postId") or "").strip()
        text = text_from_runs(renderer.get("contentText"))
        if not post_id or not text or post_id in seen_ids:
            continue
        seen_ids.add(post_id)
        title = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if title_contains and title_contains not in title:
            continue
        text = text[:max_text_chars]
        posts.append(
            {
                "source_type": "youtube_post",
                "source": "futuresnow",
                "label": "오선",
                "item_id": post_id,
                "published_at": None,
                "published_at_kst": None,
                "published_text": text_from_runs(renderer.get("publishedTimeText")),
                "report_date": report_date_from_text(title),
                "title": title,
                "text": text,
                "url": f"https://www.youtube.com/post/{post_id}",
                "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
                "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
        if len(posts) >= limit:
            break
    return posts

