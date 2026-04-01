#!/usr/bin/env python3
"""
Publish self-care-reboot artifacts (e.g. growth_report) to the Square plaza API.

Uses only the standard library. Images are sent as JSON imageBase64 so the
square backend stores them under /api/v1/files/...
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from lobster_protocol import (
    envelope_error,
    envelope_ok,
    extract_args_json_anywhere,
    is_lobster_tool_mode,
    loads_args_json,
    print_json,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _json_request(
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    *,
    headers: dict[str, str],
    timeout: float = 60.0,
) -> dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {err_body or exc.reason}") from exc


def absolute_image_url(base_url: str, image_url: str) -> str:
    if not image_url:
        return ""
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url
    return base_url.rstrip("/") + image_url


def build_post_from_growth_report(
    report: dict[str, Any],
    *,
    persona: dict[str, Any] | None,
    title: str | None,
) -> dict[str, Any]:
    days = report.get("days")
    title_f = title or (
        f"成长小报 · 第 {days} 天" if days is not None else "成长小报 · 养自己"
    )
    text = str(report.get("panel_text") or "")[:300]
    tags: list[str] = []
    for b in report.get("badges") or []:
        if isinstance(b, str) and b:
            tags.append(b)
    if len(tags) < 8:
        tags.extend(["养自己", "重启人生"])

    render_spec: dict[str, Any] = {
        "source": "self-care-reboot.growth_report",
        "generated_at": report.get("generated_at"),
        "attributes": report.get("attributes"),
    }
    if persona:
        render_spec["persona"] = persona

    body: dict[str, Any] = {
        "type": "avatar_card",
        "title": title_f[:60],
        "text": text,
        "tags": tags[:8],
        "renderSpec": render_spec,
    }

    avatar_path = report.get("avatar_image_path")
    if isinstance(avatar_path, str) and avatar_path.strip():
        p = Path(avatar_path)
        if p.is_file():
            raw = p.read_bytes()
            if len(raw) <= 2 * 1024 * 1024:
                mime = "image/png"
                suf = p.suffix.lower()
                if suf in {".jpg", ".jpeg"}:
                    mime = "image/jpeg"
                elif suf == ".gif":
                    mime = "image/gif"
                elif suf == ".webp":
                    mime = "image/webp"
                body["imageMime"] = mime
                body["imageBase64"] = base64.b64encode(raw).decode("ascii")

    return body


def publish_growth_report(
    report: dict[str, Any],
    *,
    base_url: str,
    user_id: str,
    display_name: str,
    persona: dict[str, Any] | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    post_body = build_post_from_growth_report(report, persona=persona, title=title)
    post_body["displayName"] = display_name[:16]

    headers = {}
    if user_id.strip():
        headers["X-User-ID"] = user_id.strip()

    res = _json_request("POST", f"{base}/api/v1/posts", post_body, headers=headers)
    item = res.get("item") or {}
    rel = item.get("imageUrl") or ""
    out_item = {**item, "imageUrlAbsolute": absolute_image_url(base, rel)}
    return {"ok": True, "squareResponse": res, "item": out_item}


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish growth report to Square plaza")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pub = sub.add_parser("growth-report", help="POST a growth_report.json object to /api/v1/posts")
    p_pub.add_argument("--base-url", default=os.environ.get("SQUARE_BASE_URL", "http://127.0.0.1:19100"))
    p_pub.add_argument("--user-id", default=os.environ.get("SQUARE_USER_ID", ""))
    p_pub.add_argument("--display-name", default=os.environ.get("SQUARE_DISPLAY_NAME", "小龙虾"))
    p_pub.add_argument("--report-json", default=None, help="Path to JSON file (optional if args-json has report)")
    p_pub.add_argument("--title", default=None)

    argv, args_json_str = extract_args_json_anywhere(sys.argv[1:])
    args = parser.parse_args(argv)

    try:
        args_json = loads_args_json(args_json_str)
        if args.cmd == "growth-report":
            base_url = str(args_json.get("base_url", args.base_url))
            user_id = str(args_json.get("user_id", args.user_id))
            display_name = str(args_json.get("display_name", args.display_name))
            title = args_json.get("title", args.title)
            persona = args_json.get("persona")
            if persona is not None and not isinstance(persona, dict):
                persona = None

            report = args_json.get("report")
            report_path = args_json.get("report_json", args.report_json)
            if report is None and report_path:
                report = json.loads(Path(str(report_path)).read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("Missing report (pass report in args-json or --report-json)")

            data = publish_growth_report(
                report,
                base_url=base_url,
                user_id=user_id,
                display_name=display_name,
                persona=persona,
                title=str(title) if title else None,
            )

            if is_lobster_tool_mode():
                print_json(
                    envelope_ok(
                        output=[
                            {
                                "summary": {"action": "square_publish", "post_id": data.get("item", {}).get("id")},
                                "items": [data],
                            }
                        ]
                    )
                )
            else:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            return
    except Exception as exc:
        if is_lobster_tool_mode():
            print_json(envelope_error(str(exc)))
            return
        raise

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
