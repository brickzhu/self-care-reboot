#!/usr/bin/env python3
"""
单棋手轮询广场五子棋直到终局：定时 GET ?forAgent=1，轮到自己则落子（可选 LLM，否则随机空位）。

双 Agent：开两个进程，相同 MATCH_ID，不同 X_USER_ID（与各自 create/join 时一致）。

环境变量：
  SQUARE_BASE_URL   默认 http://43.160.197.143:19100
  X_USER_ID         必填
  MATCH_ID          必填 match_…
  POLL_SEC          默认 1.5
  OPENAI_API_KEY    可选；若设置则用 Chat Completions + suggestedLlmMessages
  OPENAI_BASE_URL   默认 https://api.openai.com/v1
  OPENAI_MODEL      默认 gpt-4o-mini
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
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\{\s*\"y\"\s*:\s*(\d+)\s*,\s*\"x\"\s*:\s*(\d+)\s*\}", text)
    if m:
        y, x = int(m.group(1)), int(m.group(2))
        return x, y
    raise ValueError(f"no {{x,y}} in model output: {text[:200]}")


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

    print(f"gomoku poll user={uid[:12]}… match={mid} llm={use_llm}", flush=True)
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
