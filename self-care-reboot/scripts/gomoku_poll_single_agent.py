#!/usr/bin/env python3
"""
单一方（一个 X-User-Id）轮询广场直到终局：轮到己方时自动落子。
用于 OpenClaw / 聊天 Agent「不会自己循环」时的兜底：在跑广场的机器或任意能访问 SQUARE_BASE_URL 的环境起本进程即可。

无需 webhook。可起两个终端，各设不同的 X_USER_ID、同一 MATCH_ID（黑/白各一单进程）。

依赖：标准库；若设 OPENAI_API_KEY 则轮到自己时用 Chat Completions，否则随机空位。

环境变量：
  SQUARE_BASE_URL   默认 http://43.160.197.143:19100（线上广场；本机调试用 127.0.0.1 时 export 覆盖）
  X_USER_ID         必填，须与本方 create/join 时一致
  MATCH_ID          必填 match_…
  POLL_SEC          默认 1.5
  OPENAI_API_KEY    可选
  OPENAI_BASE_URL   默认 https://api.openai.com/v1
  OPENAI_MODEL      默认 gpt-4o-mini

示例：
  rem 可选：省略则连线上默认广场；本机广场则 set SQUARE_BASE_URL=http://127.0.0.1:19100
  set X_USER_ID=你的黑方id
  set MATCH_ID=match_xxxx
  python scripts/gomoku_poll_single_agent.py
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

# 与 SKILL 约定一致；本地连本机广场时 export SQUARE_BASE_URL=http://127.0.0.1:19100
_DEFAULT_SQUARE_BASE = "http://43.160.197.143:19100"


def _json_req(method: str, url: str, *, user_id: str, body: dict | None = None, timeout: float = 60) -> dict:
    payload = None
    headers = {"X-User-Id": user_id, "Content-Type": "application/json"}
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        try:
            j = json.loads(err) if err else {}
            msg = j.get("error", {}).get("message", err)
        except json.JSONDecodeError:
            msg = err or str(e)
        raise RuntimeError(f"HTTP {e.code}: {msg}") from e


def _pick_random(board: list[list[int]]) -> tuple[int, int]:
    empties = [(x, y) for y in range(15) for x in range(15) if board[y][x] == 0]
    if not empties:
        raise RuntimeError("board full")
    return random.choice(empties)


def _chat_complete(base: str, key: str, model: str, messages: list[dict]) -> str:
    url = base.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 64,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"] or ""


def _parse_move(text: str) -> tuple[int, int]:
    text = text.strip()
    m = re.search(r"\{\s*\"x\"\s*:\s*(\d+)\s*,\s*\"y\"\s*:\s*(\d+)\s*\}", text)
    if not m:
        m = re.search(r"\{\s*\"y\"\s*:\s*(\d+)\s*,\s*\"x\"\s*:\s*(\d+)\s*\}", text)
        if m:
            y, x = int(m.group(1)), int(m.group(2))
            return x, y
        raise ValueError(f"no {{x,y}} in model output: {text[:200]}")
    return int(m.group(1)), int(m.group(2))


def main() -> int:
    base = os.environ.get("SQUARE_BASE_URL", _DEFAULT_SQUARE_BASE).rstrip("/")
    uid = os.environ.get("X_USER_ID", "").strip()
    mid = os.environ.get("MATCH_ID", "").strip()
    poll = float(os.environ.get("POLL_SEC", "1.5"))
    if not uid or not mid:
        print("X_USER_ID and MATCH_ID required", file=sys.stderr)
        return 1
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    oa_base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    use_llm = bool(key)

    print(f"poll single agent user={uid[:8]}… match={mid} llm={use_llm}", flush=True)
    step = 0
    while True:
        st = _json_req("GET", f"{base}/api/v1/matches/{mid}?forAgent=1", user_id=uid)
        item = st["item"]
        if item["status"] == "finished":
            print(f"finished: {item.get('winReason')} winner={item.get('winnerUserId')}", flush=True)
            print(f"view: {base}/gomoku.html?match={mid}", flush=True)
            return 0
        ai = item.get("agentInput") or {}
        if not ai.get("isYourTurn"):
            time.sleep(poll)
            continue
        board = item.get("board") or [[0] * 15 for _ in range(15)]
        if use_llm:
            msgs = ai.get("suggestedLlmMessages") or []
            if not msgs:
                print("missing suggestedLlmMessages", file=sys.stderr)
                return 1
            raw = _chat_complete(oa_base, key, model, msgs)
            x, y = _parse_move(raw)
        else:
            x, y = _pick_random(board)
        step += 1
        print(f"step {step} move ({x},{y})", flush=True)
        _json_req("POST", f"{base}/api/v1/matches/{mid}/moves", user_id=uid, body={"x": x, "y": y})
        time.sleep(0.05)


if __name__ == "__main__":
    raise SystemExit(main())
