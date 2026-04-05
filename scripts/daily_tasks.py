#!/usr/bin/env python3
"""
daily_tasks.py

生成“今日任务清单”（3-5 个），并输出结构化任务与属性加成。
脚本不直接写入 memory_space，仅返回 JSON 供平台侧落库。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from typing import Any

from lobster_protocol import (
    envelope_error,
    envelope_ok,
    extract_args_json_anywhere,
    is_lobster_tool_mode,
    loads_args_json,
    print_json,
)

ATTRS = ["confidence", "discipline", "emotion", "talent", "appearance", "social"]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp_int(x: float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(x))))


TASK_POOL: dict[str, list[dict[str, Any]]] = {
    "base": [
        {
            "id": "checkin_morning",
            "category": "base",
            "title": "早安打卡",
            "description": "对自己说一句鼓励的话（情绪+5）。",
            "deltas": {"emotion": 5},
        },
        {
            "id": "daily_reflection",
            "category": "base",
            "title": "今日复盘",
            "description": "回顾今天的一件小事（自律+5）。",
            "deltas": {"discipline": 5},
        },
    ],
    "trait": [
        {
            "id": "mirror_confidence",
            "category": "trait",
            "title": "自信练习",
            "description": "对着镜子说“我很棒”（自信+8）。",
            "deltas": {"confidence": 8},
        },
        {
            "id": "micro_motion",
            "category": "trait",
            "title": "微运动",
            "description": "伸展 5 分钟或散步 10 分钟（外形+5）。",
            "deltas": {"appearance": 5},
        },
    ],
    "surprise": [
        {
            "id": "reward_self",
            "category": "surprise",
            "title": "奖励自己",
            "description": "做一件让自己开心的小事（情绪+10）。",
            "deltas": {"emotion": 10},
        },
        {
            "id": "tiny_happiness",
            "category": "surprise",
            "title": "小确幸记录",
            "description": "写下今天的一个美好瞬间（情绪+8）。",
            "deltas": {"emotion": 8},
        },
    ],
}


def pick_tasks(rng: random.Random, count: int) -> list[dict[str, Any]]:
    # 固定结构：至少 1 个 base，至少 1 个 trait；surprise 按需抽取
    tasks: list[dict[str, Any]] = []

    base_choices = TASK_POOL["base"][:]
    trait_choices = TASK_POOL["trait"][:]
    surprise_choices = TASK_POOL["surprise"][:]

    rng.shuffle(base_choices)
    rng.shuffle(trait_choices)
    rng.shuffle(surprise_choices)

    tasks.append(base_choices.pop())
    if count >= 2:
        tasks.append(trait_choices.pop())

    remaining = count - len(tasks)
    # 余下优先从 surprise 填满，否则补充 trait/base
    for _ in range(remaining):
        if surprise_choices and rng.random() < 0.65:
            tasks.append(surprise_choices.pop())
        elif trait_choices:
            tasks.append(trait_choices.pop())
        elif base_choices:
            tasks.append(base_choices.pop())
        elif surprise_choices:
            tasks.append(surprise_choices.pop())

    # 保持稳定可读的展示顺序：base -> trait -> surprise
    order = {"base": 0, "trait": 1, "surprise": 2}
    tasks.sort(key=lambda t: order.get(t.get("category"), 99))
    return tasks[:count]


def generate_today_tasks(seed: int | None = None, count: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    if count is None:
        count = rng.randint(3, 5)
    tasks = pick_tasks(rng, count=count)

    total_deltas = {a: 0 for a in ATTRS}
    for t in tasks:
        for k, v in (t.get("deltas") or {}).items():
            if k in total_deltas:
                total_deltas[k] += int(v)

    return {
        "type": "self-care-reboot.daily_tasks",
        "generated_at": utc_iso(),
        "count": len(tasks),
        "tasks": tasks,
        "total_deltas": total_deltas,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily tasks generator for self-care reboot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_today = sub.add_parser("today", help="Generate today's task list")
    p_today.add_argument("--seed", type=int, default=None, help="Seed for deterministic tasks")
    p_today.add_argument("--count", type=int, default=None, help="Override count (3-5)")

    argv, args_json_str = extract_args_json_anywhere(sys.argv[1:])
    args = parser.parse_args(argv)

    try:
        args_json = loads_args_json(args_json_str)

        if args.cmd == "today":
            seed = args_json.get("seed", args.seed)
            count = args_json.get("count", args.count)
            data = generate_today_tasks(seed=seed, count=count)

            if is_lobster_tool_mode():
                print_json(
                    envelope_ok(
                        output=[
                            {
                                "summary": {"action": "today_tasks", "count": data.get("count"), "generated_at": data.get("generated_at")},
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

