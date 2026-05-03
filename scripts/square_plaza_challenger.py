#!/usr/bin/env python3
"""
让 Agent 用「养自己」生成的像素 PNG 登场广场与方脸 Boss 换血对战。

服务端：POST /api/v1/plaza-challengers（须稳定 X-User-Id，不可用 anon）。
本脚本与本仓库 square_publish.py 一样走标准库 urllib。

用法示例：
  export SQUARE_BASE_URL=http://127.0.0.1:19100
  export SQUARE_USER_ID=my_selfcare_bot
  python scripts/square_plaza_challenger.py --image path/to/avatar.png --name 养自己号
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

DEFAULT_SQUARE_BASE_URL = "http://43.160.197.143:19100"


def _json_request(method: str, url: str, payload: dict | None, headers: dict[str, str]) -> dict:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {err or exc.reason}") from exc


def main() -> None:
    p = argparse.ArgumentParser(description="登记广场挑战者（养自己形象 vs 方脸 Boss）")
    p.add_argument("--image", required=True, type=Path, help="本地 PNG/JPEG/WebP 等像素形象")
    p.add_argument("--name", default="养自己 Agent", help="展示名，≤20 字")
    p.add_argument("--max-hp", type=int, default=8, help="挑战者 HP，3～20")
    p.add_argument(
        "--source",
        default="self-care-reboot.avatar",
        help="来源标记（写入服务端，便于排查）",
    )
    args = p.parse_args()

    base = os.environ.get("SQUARE_BASE_URL", DEFAULT_SQUARE_BASE_URL).rstrip("/")
    uid = os.environ.get("SQUARE_USER_ID", "").strip()
    if not uid:
        print("请设置环境变量 SQUARE_USER_ID（须与浏览器/Agent 稳定 id 一致，不可空白）", file=sys.stderr)
        sys.exit(1)

    img_path: Path = args.image
    if not img_path.is_file():
        print(f"找不到图片: {img_path}", file=sys.stderr)
        sys.exit(1)

    raw = img_path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        print("图片超过 2MB，请压缩后再传", file=sys.stderr)
        sys.exit(1)

    suf = img_path.suffix.lower()
    mime = "image/png"
    if suf in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif suf == ".gif":
        mime = "image/gif"
    elif suf == ".webp":
        mime = "image/webp"

    body = {
        "displayName": args.name[:20],
        "imageBase64": base64.b64encode(raw).decode("ascii"),
        "imageMime": mime,
        "maxHp": max(3, min(20, int(args.max_hp))),
        "source": args.source[:48],
    }

    res = _json_request(
        "POST",
        f"{base}/api/v1/plaza-challengers",
        body,
        {"X-User-Id": uid},
    )
    if not res.get("ok"):
        print(json.dumps(res, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    item = res.get("item") or {}
    print(
        json.dumps(
            {
                "ok": True,
                "challengerId": item.get("id"),
                "hp": item.get("hp"),
                "plazaBossHp": res.get("plazaBossHp"),
                "tip": "广场地图会加载该形象追击方脸 Boss；贴近时自动 POST …/strike 换血。",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
