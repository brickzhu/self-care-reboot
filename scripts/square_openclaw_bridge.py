#!/usr/bin/env python3
"""
Subscribe to Square agent WebSocket (mode A) and forward events to OpenClaw HTTP hooks.

Requires: pip install websocket-client

Environment:
  SQUARE_BASE_URL     e.g. http://127.0.0.1:19100
  SQUARE_USER_ID      same as X-User-Id used in REST
  OPENCLAW_HOOK_TOKEN Bearer token for hooks (match openclaw.json hooks.token)

Optional:
  SQUARE_MATCH_IDS    comma-separated match ids if not passed as argv
  SQUARE_AGENT_WS_TOKEN  if Square sets SQUARE_AGENT_WS_SECRET
  OPENCLAW_HOOK_MODE  wake (default) | agent
  OPENCLAW_HOOK_WAKE_URL   default http://127.0.0.1:18789/hooks/wake
  OPENCLAW_HOOK_AGENT_URL  default http://127.0.0.1:18789/hooks/agent
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    from websocket import WebSocketApp
except ImportError:
    WebSocketApp = None  # type: ignore[misc, assignment]


def _http_json_post(url: str, body: dict[str, object], token: str | None) -> None:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        resp.read()


def _build_wake_text(payload: dict[str, object]) -> str | None:
    ai = payload.get("agentInput")
    if not isinstance(ai, dict):
        return None
    mid = payload.get("matchId") or ai.get("matchId")
    st = ai.get("status")
    if st == "finished":
        return (
            f"[广场] 对局 {mid} 已结束。请根据 item / agentInput 向用户简短通报结果。"
        )
    if ai.get("isYourTurn") is True:
        return (
            f"[广场] 对局 {mid}：轮到你走棋。请立即 GET …/matches/{mid}?forAgent=1（带同一 X-User-Id）"
            " 并按需 POST …/moves，本局内自动下完，勿再等用户口令。"
        )
    return None


def _build_agent_message(payload: dict[str, object]) -> str | None:
    base = _build_wake_text(payload)
    if not base:
        return None
    ai = payload.get("agentInput")
    compact: dict[str, object] = {"matchId": payload.get("matchId")}
    if isinstance(ai, dict):
        compact["isYourTurn"] = ai.get("isYourTurn")
        compact["status"] = ai.get("status")
    return base + "\nJSON：" + json.dumps(compact, ensure_ascii=False)


def main() -> None:
    if WebSocketApp is None:
        print("Missing dependency: pip install websocket-client", file=sys.stderr)
        sys.exit(2)

    parser = argparse.ArgumentParser(
        description="Square WS (A) -> OpenClaw /hooks/wake or /hooks/agent"
    )
    parser.add_argument(
        "matches",
        nargs="*",
        help="match_id values (or set SQUARE_MATCH_IDS)",
    )
    args = parser.parse_args()

    base = (os.environ.get("SQUARE_BASE_URL") or "").rstrip("/")
    if not base:
        print("SQUARE_BASE_URL is required", file=sys.stderr)
        sys.exit(1)
    uid = (
        os.environ.get("SQUARE_USER_ID") or os.environ.get("X_USER_ID") or ""
    ).strip()
    if not uid:
        print("SQUARE_USER_ID is required", file=sys.stderr)
        sys.exit(1)

    mids = [str(x).strip() for x in args.matches if str(x).strip()]
    if not mids:
        raw = (os.environ.get("SQUARE_MATCH_IDS") or "").strip()
        mids = [x.strip() for x in raw.split(",") if x.strip()]
    if not mids:
        print("Provide match ids as arguments or SQUARE_MATCH_IDS", file=sys.stderr)
        sys.exit(1)

    ws_base = base.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
    qs: list[str] = [
        f"userId={urllib.parse.quote(uid)}",
        f"matches={urllib.parse.quote(','.join(mids))}",
    ]
    stok = (os.environ.get("SQUARE_AGENT_WS_TOKEN") or "").strip()
    if stok:
        qs.append(f"token={urllib.parse.quote(stok)}")
    ws_url = f"{ws_base}/api/v1/agent/ws?{'&'.join(qs)}"

    hook_mode = (os.environ.get("OPENCLAW_HOOK_MODE") or "wake").strip().lower()
    wake_url = (
        os.environ.get("OPENCLAW_HOOK_WAKE_URL") or "http://127.0.0.1:18789/hooks/wake"
    ).strip()
    agent_url = (
        os.environ.get("OPENCLAW_HOOK_AGENT_URL") or "http://127.0.0.1:18789/hooks/agent"
    ).strip()
    hook_token = (
        os.environ.get("OPENCLAW_HOOK_TOKEN") or os.environ.get("OPENCLAW_TOKEN") or ""
    ).strip() or None

    def on_message(_ws: object, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return
        if payload.get("type") != "match.updated":
            return
        if not isinstance(payload, dict):
            return
        try:
            if hook_mode == "agent":
                msg = _build_agent_message(payload)
                if not msg:
                    return
                _http_json_post(
                    agent_url,
                    {"message": msg, "name": "square-match"},
                    hook_token,
                )
            else:
                text = _build_wake_text(payload)
                if not text:
                    return
                _http_json_post(wake_url, {"text": text, "mode": "now"}, hook_token)
        except urllib.error.HTTPError as exc:
            err = exc.read().decode("utf-8", errors="replace")
            print(f"hook HTTP {exc.code}: {err}", file=sys.stderr)
        except urllib.error.URLError as exc:
            print(f"hook error: {exc}", file=sys.stderr)

    def on_open(ws: WebSocketApp) -> None:
        ws.send(json.dumps({"type": "subscribe", "matchIds": mids}, ensure_ascii=False))

    print(f"Connecting {ws_url.split('?', 1)[0]}…", file=sys.stderr)
    ws_app = WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
    ws_app.run_forever()


if __name__ == "__main__":
    main()
