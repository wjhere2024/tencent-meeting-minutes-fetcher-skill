#!/usr/bin/env python3
"""Fetch Tencent Meeting shared recording minutes/transcript as JSON and TXT.

Usage:
  python scripts/fetch_minutes.py \
    --url "https://meeting.tencent.com/crm/EXAMPLE1234" \
    --password "DEMO_PASS" \
    --outdir ./output
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

BASE = "https://meeting.tencent.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)


class FetchError(RuntimeError):
    pass


@dataclass
class ShareContext:
    share_id: str
    short_code: str | None
    meeting_id: str
    recording_id: str
    title: str | None


def _is_uuid(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value))


def _extract_short_code(url: str) -> str | None:
    path = urlparse(url).path.strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] in {"cw", "crm"}:
        return parts[1]
    return None


def _extract_share_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    query_id = parse_qs(parsed.query).get("id", [None])[0]
    if query_id and _is_uuid(query_id):
        return query_id
    return None


def _extract_share_id_from_html(html: str) -> str | None:
    m = re.search(r"id=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", html)
    if m:
        return m.group(1)
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", html)
    if m:
        return m.group(1)
    return None


def _extract_redirect_url_from_html(html: str) -> str | None:
    # JS redirect on /crm/<code>
    m = re.search(r'window\\.location\\.replace\\(\"([^\"]+)\"\\)', html)
    if m:
        return m.group(1)

    # Next.js payload redirect field
    m = re.search(r'"redirectUrl":"([^"]+)"', html)
    if m:
        return m.group(1).replace("\\/", "/")

    return None


def _format_ts(ms: int) -> str:
    sec = int(ms / 1000)
    td = timedelta(seconds=sec)
    total_sec = int(td.total_seconds())
    h, rem = divmod(total_sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _decode_title(value: str | None) -> str | None:
    if not value:
        return value
    # Some APIs return base64-encoded title text.
    if re.fullmatch(r"[A-Za-z0-9+/=]{8,}", value):
        try:
            raw = base64.b64decode(value, validate=True)
            decoded = raw.decode("utf-8")
            if decoded.strip():
                return decoded
        except Exception:
            pass
    return value


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*"})
    return s


def resolve_share_context(session: requests.Session, url: str, password: str, lang: str) -> ShareContext:
    share_id = _extract_share_id_from_url(url)
    short_code = _extract_short_code(url)

    page_resp = session.get(url, allow_redirects=True, timeout=30)
    page_resp.raise_for_status()
    page_html = page_resp.text

    if not share_id:
        share_id = _extract_share_id_from_html(page_html)
    if not share_id:
        redirect_url = _extract_redirect_url_from_html(page_html)
        if redirect_url:
            redirected = session.get(redirect_url, allow_redirects=True, timeout=30)
            redirected.raise_for_status()
            page_html = redirected.text
            share_id = _extract_share_id_from_html(page_html)
            if not short_code:
                short_code = _extract_short_code(redirected.url) or _extract_short_code(redirect_url)
    if not share_id:
        raise FetchError("Cannot resolve share_id from URL or page HTML")

    if not short_code:
        short_code = _extract_short_code(page_resp.url)

    common_payload: dict[str, Any] = {
        "pk_meeting_info_id": "",
        "sharing_id": share_id,
        "is_single": False,
        "pwd": password,
        "activity_uid": "",
        "lang": lang,
        "is_origin_content": True,
        "is_cve": True,
        "forward_cgi_path": "shares",
        "enter_from": "share",
        "short_url_code": short_code or "",
        "is_short_ctw": False,
    }
    info_resp = session.post(
        f"{BASE}/wemeet-tapi/v2/meetlog/public/detail/common-record-info",
        json=common_payload,
        timeout=30,
    )
    info_resp.raise_for_status()
    info_data = info_resp.json()

    if info_data.get("code") != 0:
        raise FetchError(
            f"common-record-info failed: code={info_data.get('code')} msg={info_data.get('msg')} "
            f"detail={info_data.get('err_detail')}"
        )

    data = info_data.get("data") or {}
    meeting_info = data.get("meeting_info") or {}
    recordings = data.get("recordings") or []
    if not recordings:
        raise FetchError("No recordings found in common-record-info response")

    recording = recordings[0]
    meeting_id = str(meeting_info.get("meeting_id") or "")
    recording_id = str(recording.get("id") or recording.get("recording_id") or "")
    title = _decode_title(meeting_info.get("origin_subject") or meeting_info.get("subject"))

    if not meeting_id or not recording_id:
        raise FetchError("Missing meeting_id or recording_id in response")

    return ShareContext(
        share_id=share_id,
        short_code=short_code,
        meeting_id=meeting_id,
        recording_id=recording_id,
        title=title,
    )


def fetch_minutes(
    session: requests.Session,
    ctx: ShareContext,
    password: str,
    lang: str,
    limit: int,
) -> dict[str, Any]:
    all_paragraphs: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, ...]] = set()
    cursor: int = 0
    first_page = True
    visited_cursors: set[int] = set()

    while cursor not in visited_cursors:
        visited_cursors.add(cursor)
        params: dict[str, Any] = {
            "id": ctx.share_id,
            "pwd": password,
            "page_source": "record",
            "meeting_id": ctx.meeting_id,
            "recording_id": ctx.recording_id,
            "lang": lang,
            "minutes_version": 0,
            "limit": limit,
            "return_ori": 0,
            "return_ori_minutes_translating": 1,
        }
        if first_page:
            params["start_pid"] = 0
        else:
            params["pid"] = cursor

        resp = session.get(f"{BASE}/wemeet-cloudrecording-webapi/v1/minutes/detail", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise FetchError(
                f"minutes/detail failed: code={data.get('code')} msg={data.get('msg')}"
            )

        minutes = data.get("minutes") or {}
        paragraphs = minutes.get("paragraphs") or []
        if not paragraphs:
            break

        for p in paragraphs:
            key = (
                p.get("pid"),
                p.get("start_time"),
                p.get("end_time"),
                ((p.get("speaker") or {}).get("user_id") or ""),
            )
            if key not in seen_keys:
                seen_keys.add(key)
                all_paragraphs.append(p)

        more = bool(data.get("more"))
        if not more:
            break

        next_pid_raw = data.get("next_pid")
        if next_pid_raw is not None:
            try:
                cursor = int(next_pid_raw)
            except (TypeError, ValueError):
                pass
            else:
                first_page = False
                continue

        pids: list[int] = []
        for p in paragraphs:
            raw_pid = p.get("pid")
            try:
                pids.append(int(raw_pid))
            except (TypeError, ValueError):
                continue
        if not pids:
            break
        cursor = max(pids) + 1
        first_page = False

    merged = {
        "code": 0,
        "share": {
            "share_id": ctx.share_id,
            "short_code": ctx.short_code,
            "meeting_id": ctx.meeting_id,
            "recording_id": ctx.recording_id,
            "title": ctx.title,
            "lang": lang,
        },
        "minutes": {
            "lang": lang,
            "paragraphs": all_paragraphs,
        },
    }
    return merged


def build_plain_text(minutes_payload: dict[str, Any]) -> str:
    lines: list[str] = []
    share = minutes_payload.get("share") or {}
    title = share.get("title")
    if title:
        lines.append(f"Title: {title}")
    lines.append(f"Meeting ID: {share.get('meeting_id', '')}")
    lines.append(f"Recording ID: {share.get('recording_id', '')}")
    lines.append("")

    paragraphs = (minutes_payload.get("minutes") or {}).get("paragraphs") or []
    for p in paragraphs:
        start = _format_ts(int(p.get("start_time") or 0))
        end = _format_ts(int(p.get("end_time") or 0))
        speaker = ((p.get("speaker") or {}).get("user_name") or "Unknown").strip()

        sentence_texts: list[str] = []
        for sent in p.get("sentences") or []:
            words = sent.get("words") or []
            text = "".join((w.get("text") or "") for w in words).strip()
            if text:
                sentence_texts.append(text)

        body = " ".join(sentence_texts).strip()
        if not body:
            continue

        lines.append(f"[{start} - {end}] {speaker}")
        lines.append(body)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Tencent Meeting share minutes/transcript")
    parser.add_argument("--url", required=True, help="Tencent Meeting share URL")
    parser.add_argument("--password", required=True, help="Share password")
    parser.add_argument("--outdir", default="output", help="Output directory")
    parser.add_argument("--lang", default="zh", help="Minutes language, default zh")
    parser.add_argument("--limit", type=int, default=50, help="Page size for minutes/detail")
    parser.add_argument("--prefix", default="minutes", help="Output file prefix")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        session = _session()
        ctx = resolve_share_context(session, args.url, args.password, args.lang)
        minutes_payload = fetch_minutes(session, ctx, args.password, args.lang, args.limit)

        json_path = outdir / f"{args.prefix}.json"
        txt_path = outdir / f"{args.prefix}.txt"

        json_path.write_text(json.dumps(minutes_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        txt_path.write_text(build_plain_text(minutes_payload), encoding="utf-8")

        para_count = len((minutes_payload.get("minutes") or {}).get("paragraphs") or [])
        print(f"[OK] share_id={ctx.share_id}")
        print(f"[OK] meeting_id={ctx.meeting_id} recording_id={ctx.recording_id}")
        print(f"[OK] paragraphs={para_count}")
        print(f"[OK] json={json_path}")
        print(f"[OK] txt={txt_path}")
        return 0
    except requests.RequestException as exc:
        print(f"[ERROR] network/http error: {exc}", file=sys.stderr)
        return 2
    except FetchError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
