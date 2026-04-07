#!/usr/bin/env python3
"""
story_generator.py

生成“事件选择”（剧情式成长）及各选项的正向属性加成。
脚本不直接写入 memory_space，仅输出结构化 JSON。
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


def sanitize_choice_key(s: str) -> str:
    return (s or "").strip().upper()

#
# 事件选择系统：生成大量“可选剧情”，A/B/C/D 的加成与 references/story-events.md 一致：
# A：自信+8，社交+5
# B：情绪+5，自律+3
# C：才华+5，情绪+3
# D：自信+5，情绪+5
#
DELTAS_BY_KEY: dict[str, dict[str, int]] = {
    "A": {"confidence": 8, "social": 5},
    "B": {"emotion": 5, "discipline": 3},
    "C": {"talent": 5, "emotion": 3},
    "D": {"confidence": 5, "emotion": 5},
}

HINT_BY_KEY: dict[str, str] = {
    "A": "选择平静解释，是把“评价”和“价值”分开来看的从容。",
    "B": "暂时的停顿不是逃避，而是为更合适的时机保留能量。",
    "C": "接受并复盘，是把每次体验转成成长的证据。",
    "D": "给自己一点时间，是对内在节奏的尊重，也是边界感的练习。",
}


def build_choices() -> list[dict[str, Any]]:
    # 注意：这里的 text 保持与 references/story-events.md 的 A/B/C/D 描述一致，便于用户建立直觉。
    return [
        {"key": "A", "label": "A", "text": "平静解释自己的想法，不卑不亢", "deltas": DELTAS_BY_KEY["A"]},
        {"key": "B", "label": "B", "text": "暂时沉默，会后找合适时机再沟通", "deltas": DELTAS_BY_KEY["B"]},
        {"key": "C", "label": "C", "text": "先接受建议，反思是否有改进空间", "deltas": DELTAS_BY_KEY["C"]},
        {"key": "D", "label": "D", "text": "告诉 TA：我需要时间思考一下", "deltas": DELTAS_BY_KEY["D"]},
    ]


def generate_situations(max_scenes: int = 80) -> list[dict[str, Any]]:
    """
    自动生成大量情境文案，避免手工维护 50+ 条事件。
    """
    areas = [
        "工作/学习场景",
        "与同事沟通",
        "与朋友相处",
        "家庭相处",
        "需要做公开表达的时刻",
        "处理沟通误会的时候",
        "面对临时变动的任务",
        "需要拒绝别人的请求时",
        "努力但遇到阻力的时候",
        "社交氛围有点尴尬的时候",
        "被对比/被评价的时候",
        "你想坚持自我但容易被打断的时候",
    ]
    triggers = [
        "你的想法被否定",
        "你被打断了发言",
        "你觉得自己被误解了",
        "你需要等待一个结果",
        "临时又加了一个小任务",
        "你不确定该怎么回应",
        "你感到有点压力上来",
        "你被催得有点紧",
        "你遇到一句“看起来不太友好”的话",
        "你发现自己开始拖延",
        "你心里有点敏感，容易想太多",
        "你想表达但又怕尴尬",
        "你努力了却没有得到预期回应",
        "你需要暂时按下情绪再决定",
        "你发现沟通卡在一个点上",
    ]

    situations: list[dict[str, Any]] = []
    idx = 0
    for area in areas:
        for trig in triggers:
            # 生成“稳定但多样”的 event_id
            event_id = f"scene_{idx:03d}"
            scene = f"今天在{area}里，你遇到了{trig}的一个小情境，你会怎么选择？"
            situations.append({"event_id": event_id, "scene": scene})
            idx += 1
            if len(situations) >= max_scenes:
                return situations
    return situations


def generate_event(seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    situations = generate_situations(max_scenes=80)
    event = rng.choice(situations)
    return {
        "type": "self-care-reboot.story_event",
        "generated_at": utc_iso(),
        "event_id": event["event_id"],
        "scene": event["scene"],
        "choices": build_choices(),
    }


def feedback_for_choice(event_id: str, choice_key: str) -> dict[str, Any]:
    choice_key = sanitize_choice_key(choice_key)
    deltas = DELTAS_BY_KEY.get(choice_key, {})
    hint = HINT_BY_KEY.get(choice_key, "")
    return {"event_id": event_id, "choice": choice_key, "deltas": deltas, "feedback_hint": hint}


def main() -> None:
    parser = argparse.ArgumentParser(description="Story generator for self-care reboot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_event = sub.add_parser("event", help="Generate an event choice")
    p_event.add_argument("--seed", type=int, default=None, help="Seed for deterministic event")

    p_feedback = sub.add_parser("feedback", help="Get feedback/deltas for a given choice")
    p_feedback.add_argument("--event-id", required=False, default=None, help="event_id from event output")
    p_feedback.add_argument("--choice", required=False, default=None, help="A/B/C/D")

    argv, args_json_str = extract_args_json_anywhere(sys.argv[1:])
    args = parser.parse_args(argv)

    try:
        args_json = loads_args_json(args_json_str)

        if args.cmd == "event":
            seed = args_json.get("seed", args.seed)
            data = generate_event(seed=seed)
            if is_lobster_tool_mode():
                print_json(
                    envelope_ok(
                        output=[
                            {
                                "summary": {"action": "story_event", "event_id": data.get("event_id"), "generated_at": data.get("generated_at")},
                                "items": [data],
                            }
                        ]
                    )
                )
            else:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            return

        if args.cmd == "feedback":
            event_id = args_json.get("event_id", args.event_id)
            choice = args_json.get("choice", args.choice)
            if event_id is None or choice is None:
                raise ValueError("Missing event_id/choice (provide CLI flags or args-json)")
            data = feedback_for_choice(str(event_id), str(choice))
            if is_lobster_tool_mode():
                print_json(
                    envelope_ok(
                        output=[
                            {
                                "summary": {"action": "story_feedback", "event_id": data.get("event_id"), "choice": data.get("choice")},
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

