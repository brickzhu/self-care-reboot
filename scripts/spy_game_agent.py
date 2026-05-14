#!/usr/bin/env python3
"""
谁是卧底：单 Agent 轮询对局，自动描述与投票。

- 身份与加入时一致：环境变量 SQUARE_USER_ID（默认 cursor_selfcare_assistant）。
- 若设置 OPENAI_API_KEY，则描述/投票文案走 OpenAI Chat Completions（模型可 OPENAI_MODEL，默认 gpt-4o-mini）。
- 未配置密钥时使用本脚本内置的启发式（仅保证流程跑通，观感弱于 LLM）。

用法：
  set SQUARE_BASE_URL=http://43.160.197.143:19100
  set SQUARE_USER_ID=cursor_selfcare_assistant
  set SPY_GAME_ID=spy_xxxx
  python scripts/spy_game_agent.py

可选：OPENAI_API_BASE（默认 https://api.openai.com/v1）、SPY_POLL_SEC（默认 2.5）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from typing import Any

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
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {err or exc.reason}") from exc


def _openai_chat(system: str, user: str) -> str:
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        return ""
    base = (os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1").rstrip("/")
    model = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
    url = f"{base}/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.75,
            "max_tokens": 400,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    return (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""


def _llm_json(system: str, user: str) -> dict[str, Any]:
    raw = _openai_chat(system, user).strip()
    if not raw:
        return {}
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _desc_line(d: dict[str, Any]) -> str:
    return str(d.get("text") or d.get("description") or "").strip()


def _fallback_description(word: str, rnd: int, prior: list[str]) -> tuple[str, str]:
    h = int(hashlib.sha256(f"{word}:{rnd}:{prior}".encode()).hexdigest(), 16)
    templates = [
        "生活里很常见，一时想不起来名字，但大家都用过。",
        "跟季节或心情有点关系，有人爱得不行，有人无感。",
        "可以单独出现，也常跟别的东西搭在一起用。",
        "说得太直白就没意思了，它更像一种感觉或习惯。",
        "小时候和长大后的理解可能完全不一样。",
        "既不是越贵越好，也不是越简单越好，看场合。",
        "有人当它是工具，有人当它是陪伴。",
        "两个字很难概括，但一提场景你大概能懂。",
    ]
    desc = templates[h % len(templates)]
    inner = (
        f"启发式回合{rnd}：词是「{word}」。"
        f"未接 LLM，用占位描述避免超时；已参考他人句数 {len(prior)}。"
    )
    return desc, inner


def _fallback_vote(
    my_word: str,
    me: str,
    players: list[dict[str, Any]],
    descriptions: list[dict[str, Any]],
    rnd: int,
) -> tuple[str, str]:
    alive_others = [
        p["userId"]
        for p in players
        if not p.get("eliminated") and str(p.get("userId")) != str(me)
    ]
    if not alive_others:
        return "", ""

    by_uid: dict[str, list[str]] = {}
    for d in descriptions:
        if int(d.get("round") or 0) != int(rnd):
            continue
        uid = str(d.get("userId") or "")
        by_uid.setdefault(uid, []).append(_desc_line(d))

    def score(uid: str) -> float:
        texts = by_uid.get(uid, [])
        if not texts:
            return 100.0
        last = texts[-1]
        overlap = sum(1 for c in my_word if c in last) / max(len(my_word), 1)
        length_pen = max(0, 40 - len(last)) * 0.3
        return length_pen - overlap * 10 + (random.random() * 0.01)

    target = max(alive_others, key=score)
    inner = (
        f"启发式投票回合{rnd}：我的词是「{my_word}」。"
        f"按描述长度与和本人词语素重叠综合打分，选中 {target}。"
        "未接 LLM时仅作流程占位。"
    )
    return target, inner


def _llm_description(word: str, rnd: int, prior_lines: list[str]) -> tuple[str, str]:
    sys = (
        "你是「谁是卧底」玩家。只输出 JSON 对象，键 description（一句中文，暗示但不直说词）"
        "和 innerMonologue（50～200 字，中文，解释你怎么编这句话）。不要 markdown。"
    )
    user = json.dumps(
        {"round": rnd, "my_word": word, "others_descriptions_so_far": prior_lines},
        ensure_ascii=False,
    )
    out = _llm_json(sys, user)
    desc = str(out.get("description") or "").strip()
    inner = str(out.get("innerMonologue") or "").strip()
    return desc, inner


def _llm_vote(item: dict[str, Any], me: str, my_word: str) -> tuple[str, str]:
    rnd = int(item.get("round") or 1)
    lines = []
    for d in item.get("descriptions") or []:
        if int(d.get("round") or 0) != rnd:
            continue
        uid = d.get("userId")
        lines.append(f"{uid}: {_desc_line(d)}")
    players_min = [
        {
            "userId": p.get("userId"),
            "displayName": p.get("displayName"),
            "eliminated": p.get("eliminated"),
        }
        for p in item.get("players") or []
    ]
    sys = (
        "你是「谁是卧底」玩家。你不知道自己是否卧底，只知道自己的词。"
        "只输出 JSON：targetUserId（要投的对方 userId 字符串）与 innerMonologue（80～220 字中文推理）。"
        "不能投自己。不要 markdown。"
    )
    user = json.dumps(
        {
            "round": rnd,
            "my_user_id": me,
            "my_word": my_word,
            "alive_players": players_min,
            "this_round_descriptions": lines,
        },
        ensure_ascii=False,
    )
    out = _llm_json(sys, user)
    tid = str(out.get("targetUserId") or "").strip()
    inner = str(out.get("innerMonologue") or "").strip()
    return tid, inner


def main() -> None:
    ap = argparse.ArgumentParser(description="谁是卧底 Agent 轮询")
    ap.add_argument("--game", default=os.environ.get("SPY_GAME_ID", "").strip(), help="对局 id，如 spy_xxx")
    args = ap.parse_args()
    game_id = args.game.strip()
    if not game_id:
        print("请传 --game 或设置环境变量 SPY_GAME_ID", file=sys.stderr)
        sys.exit(1)

    base = os.environ.get("SQUARE_BASE_URL", DEFAULT_SQUARE_BASE_URL).rstrip("/")
    uid = os.environ.get("SQUARE_USER_ID", "cursor_selfcare_assistant").strip()
    if not uid or uid == "anon":
        print("SQUARE_USER_ID 须为非 anon 的稳定 id", file=sys.stderr)
        sys.exit(1)

    poll = float(os.environ.get("SPY_POLL_SEC", "2.5"))
    headers = {"X-User-Id": uid}
    url_get = f"{base}/api/v1/spy-games/{game_id}"

    print(f"[spy-agent] base={base} game={game_id} uid={uid} poll={poll}s", flush=True)
    use_llm = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    print(f"[spy-agent] LLM={'OpenAI 兼容' if use_llm else '关闭（启发式）'}", flush=True)

    last_status = None
    while True:
        try:
            data = _json_request("GET", url_get, None, headers)
        except Exception as e:
            print(f"[spy-agent] GET 失败: {e}", flush=True)
            time.sleep(poll)
            continue

        if not data.get("ok"):
            print(f"[spy-agent] 服务端: {data}", flush=True)
            time.sleep(poll)
            continue

        item = data["item"]
        st = item.get("status")
        if st != last_status:
            print(f"[spy-agent] status={st} phase={item.get('currentPhase')} round={item.get('round')}", flush=True)
            last_status = st

        if st == "finished":
            w = item.get("winner")
            r = item.get("winReason")
            cw = item.get("civilianWord")
            sw = item.get("spyWord")
            print(f"[spy-agent] 结束 winner={w} winReason={r} civilian={cw} spyWord={sw}", flush=True)
            break

        if st == "waiting":
            time.sleep(poll)
            continue

        if st != "playing":
            time.sleep(poll)
            continue

        phase = item.get("currentPhase")
        rnd = int(item.get("round") or 1)
        players = list(item.get("players") or [])

        if phase == "describe" and str(item.get("currentTurnUserId")) == str(uid):
            mine = next((p for p in players if str(p.get("userId")) == str(uid)), None)
            word = (mine or {}).get("word")
            if not word:
                time.sleep(poll)
                continue

            this_round = [d for d in (item.get("descriptions") or []) if int(d.get("round") or 0) == rnd]
            prior = [_desc_line(d) for d in this_round if str(d.get("userId")) != str(uid)]

            if use_llm:
                desc, inner = _llm_description(str(word), rnd, prior)
                if not desc:
                    desc, inner = _fallback_description(str(word), rnd, prior)
            else:
                desc, inner = _fallback_description(str(word), rnd, prior)

            try:
                _json_request(
                    "POST",
                    f"{base}/api/v1/spy-games/{game_id}/describe",
                    {"description": desc[:200], "innerMonologue": (inner or "")[:500]},
                    headers,
                )
                print(f"[spy-agent] 已描述: {desc[:80]}…", flush=True)
            except Exception as e:
                print(f"[spy-agent] describe 失败: {e}", flush=True)

        elif phase == "vote":
            mine = next((p for p in players if str(p.get("userId")) == str(uid)), None)
            if not mine or mine.get("eliminated"):
                time.sleep(poll)
                continue
            votes = item.get("votes") or []
            if any(str(v.get("voterId")) == str(uid) for v in votes):
                time.sleep(poll)
                continue

            my_word = str(mine.get("word") or "")
            if use_llm:
                target, inner = _llm_vote(item, uid, my_word)
                alive_others = [
                    str(p["userId"])
                    for p in players
                    if not p.get("eliminated") and str(p.get("userId")) != str(uid)
                ]
                if target not in alive_others or target == str(uid):
                    target, inner = _fallback_vote(my_word, uid, players, list(item.get("descriptions") or []), rnd)
            else:
                target, inner = _fallback_vote(
                    my_word, uid, players, list(item.get("descriptions") or []), rnd
                )

            if not target:
                time.sleep(poll)
                continue
            try:
                _json_request(
                    "POST",
                    f"{base}/api/v1/spy-games/{game_id}/vote",
                    {"targetUserId": target, "innerMonologue": (inner or "")[:500]},
                    headers,
                )
                print(f"[spy-agent] 已投票 -> {target}", flush=True)
            except Exception as e:
                print(f"[spy-agent] vote 失败: {e}", flush=True)

        time.sleep(poll)


if __name__ == "__main__":
    main()
