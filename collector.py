#!/usr/bin/env python3
"""Collect recent public market posts for an internal summarization model.

The collector reads recent public Telegram channel pages plus the latest
오선/FuturesNow YouTube posts. It does not access private channels or download
media files.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from futuresnow import fetch_html as fetch_futuresnow_html
from futuresnow import parse_posts as parse_futuresnow_posts


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "channels.json"
UTC = dt.timezone.utc
KST = dt.timezone(dt.timedelta(hours=9))
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
CHANNEL_RE = re.compile(r"^[A-Za-z0-9_]{5,64}$")
INVISIBLE_RE = re.compile(
    r"[\u00ad\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"
)
PRINT_LOCK = threading.Lock()


def log(message: str) -> None:
    with PRINT_LOCK:
        print(message, flush=True)


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<script\b.*?</script>", "", value, flags=re.I | re.S)
    value = re.sub(r"<style\b.*?</style>", "", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = INVISIBLE_RE.sub("", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_channel(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^https?://(?:www\.)?t\.me/(?:s/)?", "", value, flags=re.I)
    value = value.split("?", 1)[0].strip("/").lstrip("@")
    if not CHANNEL_RE.fullmatch(value):
        raise ValueError(f"invalid public channel id: {value!r}")
    return value


def load_channels(config_path: Path, requested: str) -> list[dict[str, str]]:
    configured = json.loads(config_path.read_text(encoding="utf-8"))
    labels = {normalize_channel(row["id"]).lower(): row.get("label", row["id"]) for row in configured}
    if requested.strip():
        raw_values = re.split(r"[\s,]+", requested.strip())
        ids = [normalize_channel(value) for value in raw_values if value]
    else:
        ids = [normalize_channel(row["id"]) for row in configured]

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for channel in ids:
        key = channel.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append({"id": channel, "label": labels.get(key, channel)})
    if not result:
        raise ValueError("at least one channel is required")
    return result


def parse_page(body: str, requested_channel: str, label: str) -> list[dict[str, Any]]:
    blocks = re.split(r'<div class="tgme_widget_message_wrap', body)[1:]
    messages: list[dict[str, Any]] = []
    for block in blocks:
        match_id = re.search(r'data-post="([^"]+)/(\d+)"', block)
        match_time = re.search(r'<time datetime="([^"]+)"', block)
        if not (match_id and match_time):
            continue
        try:
            published = dt.datetime.fromisoformat(
                match_time.group(1).replace("Z", "+00:00")
            )
            if published.tzinfo is None:
                continue
            published = published.astimezone(UTC)
        except ValueError:
            continue

        canonical_channel = match_id.group(1)
        post_id = int(match_id.group(2))
        match_text = re.search(
            r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>',
            block,
            flags=re.S,
        )
        text = strip_tags(match_text.group(1) if match_text else "")
        match_author = re.search(
            r'<a class="tgme_widget_message_owner_name[^"]*"[^>]*>(.*?)</a>',
            block,
            flags=re.S,
        )
        match_views = re.search(
            r'<span class="tgme_widget_message_views">([^<]*)</span>', block
        )
        has_media = bool(
            re.search(
                r"tgme_widget_message_(?:photo|video|document|poll|voice|audio)",
                block,
            )
        )
        url = f"https://t.me/s/{canonical_channel}/{post_id}"
        messages.append(
            {
                "channel": requested_channel,
                "canonical_channel": canonical_channel,
                "label": label,
                "post_id": post_id,
                "message_id": f"{canonical_channel}/{post_id}",
                "published_at": published.isoformat().replace("+00:00", "Z"),
                "published_at_kst": published.astimezone(KST).isoformat(),
                "author": strip_tags(match_author.group(1)) if match_author else "",
                "text": text,
                "has_media": has_media,
                "views": strip_tags(match_views.group(1)) if match_views else "",
                "url": url,
                "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return messages


def fetch_page(
    channel: str,
    before: int | None,
    *,
    timeout: float,
    retries: int,
    ssl_context: ssl.SSLContext,
) -> str:
    quoted = urllib.parse.quote(channel, safe="")
    url = f"https://t.me/s/{quoted}"
    if before is not None:
        url += "?" + urllib.parse.urlencode({"before": before})
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_channel(
    channel_spec: dict[str, str],
    *,
    output_dir: Path,
    start_utc: dt.datetime,
    end_utc: dt.datetime,
    max_pages: int,
    delay: float,
    timeout: float,
    retries: int,
    ssl_context: ssl.SSLContext,
) -> dict[str, Any]:
    channel = channel_spec["id"]
    label = channel_spec["label"]
    before: int | None = None
    seen_before: set[int] = set()
    messages: dict[int, dict[str, Any]] = {}
    partial_path = output_dir / "by_channel" / f"{channel}.partial.jsonl"
    partial_handle = partial_path.open("w", encoding="utf-8")
    pages = 0
    error = ""
    stop_reason = "end_of_history"

    try:
        while True:
            if max_pages and pages >= max_pages:
                stop_reason = "max_pages"
                break
            body = fetch_page(
                channel,
                before,
                timeout=timeout,
                retries=retries,
                ssl_context=ssl_context,
            )
            page_messages = parse_page(body, channel, label)
            pages += 1
            if not page_messages:
                if pages == 1:
                    error = "no public messages found"
                    stop_reason = "error"
                break

            page_times = [
                dt.datetime.fromisoformat(
                    message["published_at"].replace("Z", "+00:00")
                ).astimezone(UTC)
                for message in page_messages
            ]
            new_messages = 0
            for message in page_messages:
                published = dt.datetime.fromisoformat(
                    message["published_at"].replace("Z", "+00:00")
                ).astimezone(UTC)
                if not (start_utc <= published < end_utc):
                    continue
                if message["post_id"] not in messages:
                    partial_handle.write(
                        json.dumps(
                            message, ensure_ascii=False, separators=(",", ":")
                        )
                    )
                    partial_handle.write("\n")
                    new_messages += 1
                messages[message["post_id"]] = message
            partial_handle.flush()
            oldest = min(message["post_id"] for message in page_messages)
            log(
                f"[{channel}] page={pages} page_messages={len(page_messages)} "
                f"new={new_messages} total={len(messages)} oldest={oldest}"
            )
            if min(page_times) < start_utc:
                stop_reason = "window_start_reached"
                break
            if oldest <= 1 or oldest in seen_before or oldest == before:
                stop_reason = "pagination_stopped"
                break
            seen_before.add(oldest)
            before = oldest
            if delay:
                time.sleep(delay)
    except Exception as exc:  # Keep partial data from other channels.
        error = f"{type(exc).__name__}: {exc}"
        stop_reason = "error"
        log(f"[{channel}] ERROR {error}")
    finally:
        partial_handle.close()

    ordered = sorted(
        messages.values(),
        key=lambda row: (row["published_at"], row["post_id"]),
    )
    destination = output_dir / "by_channel" / f"{channel}.jsonl"
    write_jsonl(destination, ordered)
    partial_path.unlink(missing_ok=True)
    return {
        "channel": channel,
        "label": label,
        "pages": pages,
        "messages": len(ordered),
        "oldest_post_id": min(messages) if messages else None,
        "newest_post_id": max(messages) if messages else None,
        "first_published_at": ordered[0]["published_at"] if ordered else None,
        "last_published_at": ordered[-1]["published_at"] if ordered else None,
        "stop_reason": stop_reason,
        "complete": stop_reason
        in {"end_of_history", "pagination_stopped", "window_start_reached"},
        "error": error,
        "file": destination.relative_to(output_dir).as_posix(),
        "sha256": file_sha256(destination),
    }


def build_telegram_aggregate(
    output_dir: Path, summaries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        path = output_dir / summary["file"]
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    rows.sort(key=lambda row: (row["published_at"], row["channel"], row["post_id"]))

    write_jsonl(output_dir / "telegram_messages.jsonl", rows)
    csv_fields = [
        "published_at",
        "published_at_kst",
        "channel",
        "label",
        "post_id",
        "author",
        "text",
        "has_media",
        "views",
        "url",
    ]
    with (output_dir / "telegram_messages.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def telegram_market_item(row: dict[str, Any]) -> dict[str, Any]:
    title = next((line.strip() for line in row["text"].splitlines() if line.strip()), "")
    return {
        "source_type": "telegram",
        "source": row["channel"],
        "label": row["label"],
        "item_id": str(row["post_id"]),
        "published_at": row["published_at"],
        "published_at_kst": row["published_at_kst"],
        "published_text": None,
        "report_date": None,
        "title": title[:240],
        "text": row["text"],
        "url": row["url"],
        "author": row["author"],
        "has_media": row["has_media"],
        "views": row["views"],
        "content_sha256": row["content_sha256"],
    }


def write_market_outputs(
    output_dir: Path,
    *,
    telegram_rows: list[dict[str, Any]],
    futuresnow_rows: list[dict[str, Any]],
    start_utc: dt.datetime,
    end_utc: dt.datetime,
) -> list[dict[str, Any]]:
    write_jsonl(output_dir / "futuresnow_posts.jsonl", futuresnow_rows)
    items = [telegram_market_item(row) for row in telegram_rows] + futuresnow_rows
    items.sort(
        key=lambda row: (
            row.get("published_at") or row.get("report_date") or "",
            row["source"],
            row["item_id"],
        )
    )
    write_jsonl(output_dir / "market_inputs.jsonl", items)
    payload = {
        "schema_version": 2,
        "window_utc": {
            "start": start_utc.isoformat().replace("+00:00", "Z"),
            "end": end_utc.isoformat().replace("+00:00", "Z"),
        },
        "window_kst": {
            "start": start_utc.astimezone(KST).isoformat(),
            "end": end_utc.astimezone(KST).isoformat(),
        },
        "telegram_count": len(telegram_rows),
        "futuresnow_count": len(futuresnow_rows),
        "items": items,
    }
    (output_dir / "market_inputs.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    csv_fields = [
        "source_type",
        "source",
        "label",
        "item_id",
        "published_at",
        "published_at_kst",
        "published_text",
        "report_date",
        "title",
        "text",
        "url",
    ]
    with (output_dir / "market_inputs.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(items)
    return items


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--channels",
        default="",
        help="Comma/space-separated channel ids or public t.me URLs; blank uses channels.json",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--max-pages",
        type=int,
        default=100,
        help="Safety cap per channel while walking back to the window start",
    )
    parser.add_argument(
        "--window-hours",
        type=float,
        default=12.0,
        help="Collect Telegram messages from this many hours before execution",
    )
    parser.add_argument("--futuresnow-limit", type=int, default=5)
    parser.add_argument("--skip-futuresnow", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--ca-bundle",
        type=Path,
        help="Optional corporate CA bundle; TLS verification remains enabled",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if (
        args.max_pages < 1
        or args.window_hours <= 0
        or args.futuresnow_limit < 1
        or args.workers < 1
        or args.delay < 0
    ):
        print("invalid page/window/limit/worker/delay setting", file=sys.stderr)
        return 2

    try:
        channels = load_channels(args.config, args.channels)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    output_dir = args.output_dir.resolve()
    (output_dir / "by_channel").mkdir(parents=True, exist_ok=True)
    ssl_context = ssl.create_default_context(
        cafile=str(args.ca_bundle) if args.ca_bundle else None
    )
    collected_at = dt.datetime.now(UTC).replace(microsecond=0)
    start_utc = collected_at - dt.timedelta(hours=args.window_hours)
    end_utc = collected_at + dt.timedelta(seconds=1)
    summaries: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=min(args.workers, len(channels))) as executor:
        futures = {
            executor.submit(
                collect_channel,
                spec,
                output_dir=output_dir,
                start_utc=start_utc,
                end_utc=end_utc,
                max_pages=args.max_pages,
                delay=args.delay,
                timeout=args.timeout,
                retries=args.retries,
                ssl_context=ssl_context,
            ): spec["id"]
            for spec in channels
        }
        for future in as_completed(futures):
            summaries.append(future.result())

    summaries.sort(key=lambda row: row["channel"].lower())
    telegram_rows = build_telegram_aggregate(output_dir, summaries)
    futuresnow_rows: list[dict[str, Any]] = []
    futuresnow_error = ""
    if not args.skip_futuresnow:
        try:
            futuresnow_html = fetch_futuresnow_html(
                ssl_context=ssl_context,
                user_agent=UA,
                timeout=args.timeout,
                retries=args.retries,
            )
            futuresnow_rows = parse_futuresnow_posts(
                futuresnow_html,
                collected_at=collected_at,
                limit=args.futuresnow_limit,
            )
            if not futuresnow_rows:
                futuresnow_error = "no matching 미국 증시 요약 posts found"
        except Exception as exc:
            futuresnow_error = f"{type(exc).__name__}: {exc}"
            log(f"[futuresnow] ERROR {futuresnow_error}")
    items = write_market_outputs(
        output_dir,
        telegram_rows=telegram_rows,
        futuresnow_rows=futuresnow_rows,
        start_utc=start_utc,
        end_utc=end_utc,
    )
    manifest = {
        "schema_version": 2,
        "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
        "collected_at_kst": collected_at.astimezone(KST).isoformat(),
        "window_utc": {
            "start": start_utc.isoformat().replace("+00:00", "Z"),
            "end": end_utc.isoformat().replace("+00:00", "Z"),
        },
        "window_kst": {
            "start": start_utc.astimezone(KST).isoformat(),
            "end": end_utc.astimezone(KST).isoformat(),
        },
        "public_pages_only": True,
        "media_files_downloaded": False,
        "requested_channels": [row["id"] for row in channels],
        "settings": {
            "max_pages_per_channel": args.max_pages,
            "window_hours": args.window_hours,
            "workers": args.workers,
            "request_delay_seconds": args.delay,
            "futuresnow_limit": args.futuresnow_limit,
        },
        "telegram_messages": len(telegram_rows),
        "futuresnow_posts": len(futuresnow_rows),
        "total_items": len(items),
        "complete_channels": sum(row["complete"] for row in summaries),
        "failed_channels": sum(bool(row["error"]) for row in summaries),
        "futuresnow_error": futuresnow_error,
        "channels": summaries,
        "files": {
            name: file_sha256(output_dir / name)
            for name in (
                "market_inputs.json",
                "market_inputs.jsonl",
                "market_inputs.csv",
                "telegram_messages.jsonl",
                "telegram_messages.csv",
                "futuresnow_posts.jsonl",
            )
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    log(
        f"done channels={len(channels)} telegram={len(telegram_rows)} "
        f"futuresnow={len(futuresnow_rows)} errors={manifest['failed_channels']} "
        f"output={output_dir}"
    )
    all_telegram_failed = manifest["failed_channels"] == len(channels)
    return 1 if all_telegram_failed and futuresnow_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
