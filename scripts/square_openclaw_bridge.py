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

自检（先跑通再长期挂着）:
  python square_openclaw_bridge.py --test-hook
  python square_openclaw_bridge.py --test-ws match_xxx          # 只连广场 WS，约 20s 内打印推送
  python square_openclaw_bridge.py -v match_xxx                 # 长期连接并打印每条 WS / hook 结果

openclaw.json 须含: hooks.enabled=true, hooks.token 与 OPENCLAW_HOOK_TOKEN 一致；
若自定义 hooks.path（如 /hooks），则 wake 全称一般为 http://127.0.0.1:<端口><path>/wake
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

try:
    from websocket import WebSocketApp
except ImportError:
    WebSocketApp = None  # type: ignore[misc, assignment]


def _http_json_post(
    url: str, body: dict[str, object], token: str | None, *, timeout: float = 120.0
) -> tuple[int, bytes]:
    """Returns (status_code, response_body)."""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode() or 200, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _build_wake_text(payload: dict[str, object]) -> str | None:
    ai = payload.get("agentInput")
    if not isinstance(ai, dict):
        return None
    mid = payload.get("matchId") or ai.get("matchId")
    st = ai.get("status")
    reason = str(payload.get("notifyReason") or "")

    if st == "finished":
        return (
            f"[广场] 对局 {mid} 已结束。请根据 item / agentInput 向用户简短通报结果。"
        )

    if reason == "opponent_joined":
        base = f"[广场] 对局 {mid}：对手已加入，棋局已开始（running）。"
        if ai.get("isYourTurn") is True:
            return (
                base
                + f" 轮到你走棋（先手）。请立即 GET …/matches/{mid}?forAgent=1（带同一 X-User-Id）"
                + " 并按需 POST …/moves，本局内自动下完。"
            )
        return (
            base
            + f" 对方先手；请周期性 GET …/matches/{mid}?forAgent=1，轮到你时再 POST …/moves，勿让用户逐句催。"
        )

    if reason == "match_running":
        base = f"[广场] 跳棋对局 {mid}：满座开局。"
        if ai.get("isYourTurn") is True:
            return base + " 轮到你走子。"
        return base + " 请等待轮到你时再走子；期间可 GET ?forAgent=1 看局面。"

    if reason == "seat_joined":
        return (
            f"[广场] 跳棋 {mid}：有新棋手入座，尚未满座。可 GET 列表关注进度。"
        )

    if reason == "move" and ai.get("isYourTurn") is True:
        return (
            f"[广场] 对局 {mid}：轮到你走棋。请 GET …/matches/{mid}?forAgent=1（带同一 X-User-Id）"
            " 并按需 POST …/moves。"
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
    compact: dict[str, object] = {
        "matchId": payload.get("matchId"),
        "notifyReason": payload.get("notifyReason"),
    }
    if isinstance(ai, dict):
        compact["isYourTurn"] = ai.get("isYourTurn")
        compact["status"] = ai.get("status")
    return base + "\nJSON：" + json.dumps(compact, ensure_ascii=False)


def _load_hook_config() -> tuple[str, str, str, str | None]:
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
    return hook_mode, wake_url, agent_url, hook_token


def cmd_test_hook() -> int:
    hook_mode, wake_url, agent_url, hook_token = _load_hook_config()
    if not hook_token:
        print("OPENCLAW_HOOK_TOKEN unset（须与 ~/.openclaw/openclaw.json 里 hooks.token 一致）", file=sys.stderr)
        return 1
    if hook_mode == "agent":
        url = agent_url
        body: dict[str, object] = {
            "message": "[广场桥接自检] --test-hook：若成功会触发 hooks/agent。",
            "name": "square-bridge-test",
        }
    else:
        url = wake_url
        body = {
            "text": "[广场桥接自检] --test-hook：若成功，main 会话应收到系统事件。",
            "mode": "now",
        }
    print(f"POST {url}", file=sys.stderr)
    try:
        code, raw = _http_json_post(url, body, hook_token, timeout=45.0)
    except OSError as exc:
        print(f"请求失败（Gateway 是否在跑？127.0.0.1 是否可用？）: {exc}", file=sys.stderr)
        return 1
    print(f"HTTP {code} {raw.decode('utf-8', errors='replace').strip()}", file=sys.stderr)
    if code == 401:
        print("401：检查 token 是否与 hooks.token 完全一致。", file=sys.stderr)
    if code == 404:
        print("404：检查 OPENCLAW_HOOK_WAKE_URL 路径（自定义 hooks.path 时要拼对）。", file=sys.stderr)
    return 0 if code < 400 else 1


def cmd_test_ws(matches: list[str], verbose: bool) -> int:
    if WebSocketApp is None:
        print("Missing dependency: pip install websocket-client", file=sys.stderr)
        return 2
    base = (os.environ.get("SQUARE_BASE_URL") or "").rstrip("/")
    if not base:
        print("SQUARE_BASE_URL is required", file=sys.stderr)
        return 1
    uid = (
        os.environ.get("SQUARE_USER_ID") or os.environ.get("X_USER_ID") or ""
    ).strip()
    if not uid:
        print("SQUARE_USER_ID is required", file=sys.stderr)
        return 1
    mids = list(matches)
    if not mids:
        raw = (os.environ.get("SQUARE_MATCH_IDS") or "").strip()
        mids = [x.strip() for x in raw.split(",") if x.strip()]
    if not mids:
        print("提供 match id 参数或设置 SQUARE_MATCH_IDS", file=sys.stderr)
        return 1

    ws_base = base.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
    qs: list[str] = [
        f"userId={urllib.parse.quote(uid)}",
        f"matches={urllib.parse.quote(','.join(mids))}",
    ]
    stok = (os.environ.get("SQUARE_AGENT_WS_TOKEN") or "").strip()
    if stok:
        qs.append(f"token={urllib.parse.quote(stok)}")
    ws_url = f"{ws_base}/api/v1/agent/ws?{'&'.join(qs)}"

    app_holder: list[WebSocketApp | None] = [None]

    def on_message(_ws: object, message: str) -> None:
        print(message, file=sys.stderr)

    def on_open(ws: WebSocketApp) -> None:
        print("[ws] connected，已 subscribe", file=sys.stderr)
        ws.send(json.dumps({"type": "subscribe", "matchIds": mids}, ensure_ascii=False))

    def on_error(_ws: object, err: object) -> None:
        print(f"[ws] error {err!r}", file=sys.stderr)

    print(
        f"[ws] {ws_url.split('?', 1)[0]} …（无输出=该局暂无推送；可在对局再走一步试）",
        file=sys.stderr,
    )
    ws_app = WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
    )
    app_holder[0] = ws_app
    if not verbose:

        def _stop() -> None:
            try:
                ws_app.close()
            except Exception:
                pass

        threading.Timer(20.0, _stop).start()
    ws_app.run_forever()
    return 0


def main() -> None:
    if WebSocketApp is None:
        print("Missing dependency: pip install websocket-client", file=sys.stderr)
        sys.exit(2)

    parser = argparse.ArgumentParser(
        description="Square WS (A) -> OpenClaw /hooks/wake or /hooks/agent"
    )
    parser.add_argument(
        "--test-hook",
        action="store_true",
        help="只测 OpenClaw hooks（不连广场）。HTTP 2xx 再继续 run。",
    )
    parser.add_argument(
        "--test-ws",
        action="store_true",
        help="只连广场 WebSocket，约 20 秒打印推送（验证 Square 是否含 WS）。-v 则长期连接。",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="run 模式：打印每条 WS 与每次 hook 的 HTTP 状态",
    )
    parser.add_argument(
        "matches",
        nargs="*",
        help="match_id（或 SQUARE_MATCH_IDS）",
    )
    args = parser.parse_args()

    if args.test_hook:
        sys.exit(cmd_test_hook())
    if args.test_ws:
        sys.exit(cmd_test_ws(list(args.matches), verbose=args.verbose))

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

    hook_mode, wake_url, agent_url, hook_token = _load_hook_config()
    verbose = args.verbose

    def on_message(_ws: object, message: str) -> None:
        if verbose:
            print(f"[ws] {message}", file=sys.stderr)
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
                    if verbose:
                        print("[hook] skip agent (no message)", file=sys.stderr)
                    return
                code, raw = _http_json_post(
                    agent_url,
                    {"message": msg, "name": "square-match"},
                    hook_token,
                )
                if verbose or code >= 400:
                    print(
                        f"[hook] agent HTTP {code} {raw.decode('utf-8', errors='replace')[:500]}",
                        file=sys.stderr,
                    )
            else:
                text = _build_wake_text(payload)
                if not text:
                    if verbose:
                        print("[hook] skip wake (no text)", file=sys.stderr)
                    return
                code, raw = _http_json_post(
                    wake_url, {"text": text, "mode": "now"}, hook_token
                )
                if verbose or code >= 400:
                    print(
                        f"[hook] wake HTTP {code} {raw.decode('utf-8', errors='replace')[:500]}",
                        file=sys.stderr,
                    )
        except OSError as exc:
            print(f"hook error: {exc}", file=sys.stderr)

    def on_open(ws: WebSocketApp) -> None:
        if verbose:
            print("[ws] open，subscribe …", file=sys.stderr)
        ws.send(json.dumps({"type": "subscribe", "matchIds": mids}, ensure_ascii=False))

    def on_error(_ws: object, err: object) -> None:
        print(f"[ws] error: {err!r}", file=sys.stderr)

    print(
        f"Connecting {ws_url.split('?', 1)[0]} …（加 -v 可看每条消息与 hook 回应）",
        file=sys.stderr,
    )
    ws_app = WebSocketApp(
        ws_url, on_open=on_open, on_message=on_message, on_error=on_error
    )
    ws_app.run_forever()


if __name__ == "__main__":
    main()
