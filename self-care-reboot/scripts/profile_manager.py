#!/usr/bin/env python3
"""
profile_manager.py

用于：
1) 初始化用户养成画像（把“理想形象/现实痛点/人生阶段”映射到 6 大属性）
2) 对属性应用增量（用于任务完成、事件选择加成）

说明：
- 该脚本只负责“计算与生成结构化结果”，不直接写入 memory_space。
- 你可以在你的“龙虾/OpenClaw”平台里把返回 JSON 写入持久化存储（memory_space）。
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
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
ATTR_LABEL = {
    "confidence": "自信值",
    "discipline": "自律值",
    "emotion": "情绪值",
    "talent": "才华值",
    "appearance": "外形值",
    "social": "社交值",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clamp_int(x: float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(x))))


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_text_list(s: str) -> list[str]:
    """
    将用户输入的“可选特质/痛点”解析为列表。
    支持逗号/顿号/换行/空格分隔。
    """
    if not s:
        return []
    parts = re.split(r"[,\n，、\s]+", s.strip())
    return [p for p in parts if p]


@dataclass(frozen=True)
class TraitImpact:
    attr: str
    delta: int


# 简化映射：把“理想形象”关键词 -> 属性加成
TRAIT_KEYWORD_IMPACTS: list[tuple[str, list[TraitImpact]]] = [
    ("自信", [TraitImpact("confidence", 10)]),
    ("自信大方", [TraitImpact("confidence", 12), TraitImpact("social", 4)]),
    ("从容", [TraitImpact("emotion", 10), TraitImpact("confidence", 4)]),
    ("淡定", [TraitImpact("emotion", 10), TraitImpact("discipline", 2)]),
    ("自律", [TraitImpact("discipline", 14)]),
    ("高效", [TraitImpact("discipline", 10)]),
    ("表达", [TraitImpact("social", 8), TraitImpact("talent", 4)]),
    ("擅长表达", [TraitImpact("social", 10), TraitImpact("confidence", 4)]),
    ("身材", [TraitImpact("appearance", 12)]),
    ("匀称", [TraitImpact("appearance", 10), TraitImpact("discipline", 2)]),
    ("多才", [TraitImpact("talent", 12)]),
    ("多才多艺", [TraitImpact("talent", 14), TraitImpact("confidence", 4)]),
    ("情绪稳定", [TraitImpact("emotion", 16)]),
    ("情绪", [TraitImpact("emotion", 8)]),
    ("积极", [TraitImpact("emotion", 8), TraitImpact("confidence", 4)]),
    ("乐观", [TraitImpact("emotion", 10), TraitImpact("confidence", 4)]),
    ("温柔", [TraitImpact("emotion", 6), TraitImpact("social", 4)]),
]


def compute_ideal_deltas(ideal_text: str) -> dict[str, int]:
    text = ideal_text or ""
    deltas = {a: 0 for a in ATTRS}
    for key, impacts in TRAIT_KEYWORD_IMPACTS:
        if key in text:
            for imp in impacts:
                deltas[imp.attr] += imp.delta
    return deltas


def stage_bias(stage: str) -> dict[str, int]:
    """
    轻量处理“回到 18/16 岁”的设定：不惩罚，只做小幅起点调整。
    """
    stage_norm = (stage or "").strip()
    if not stage_norm or stage_norm.lower() in {"current", "当前", "从当前"}:
        return {a: 0 for a in ATTRS}
    if stage_norm in {"回到 18 岁", "18 岁", "18岁"}:
        return {"confidence": 3, "discipline": 2, "emotion": 3, "talent": 2, "appearance": 1, "social": 2}
    if stage_norm in {"回到 16 岁", "16 岁", "16岁"}:
        return {"confidence": 2, "discipline": 1, "emotion": 4, "talent": 2, "appearance": 1, "social": 1}
    return {a: 0 for a in ATTRS}


def render_comparison(initial: dict[str, int], ideal_deltas: dict[str, int]) -> str:
    """
    输出一段“现实自我 vs 理想自我”的简短对比描述（用于初次初始化后的对话）。
    """
    ideal_attrs = {}
    for a in ATTRS:
        ideal_attrs[a] = clamp_int(initial[a] + ideal_deltas.get(a, 0))

    stronger = sorted(ATTRS, key=lambda k: ideal_attrs[k] - initial[k], reverse=True)[:2]
    parts = []
    for a in stronger:
        parts.append(f"更靠近你的理想的是「{ATTR_LABEL[a]}」")
    if not parts:
        return "我们把每一个小行动都当作成长的证据。"
    return "、".join(parts) + "。"


def init_profile(
    ideal: str,
    pain: str,
    stage: str,
    seed: int | None = None,
    persona: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    base = {a: rng.randint(40, 60) for a in ATTRS}
    ideal_deltas = compute_ideal_deltas(ideal)
    bias = stage_bias(stage)

    # “无压力”逻辑：痛点不做负向扣分，只用于生成关注点（focus_areas）
    pain_list = parse_text_list(pain)

    for a in ATTRS:
        base[a] = clamp_int(base[a] + ideal_deltas.get(a, 0) + bias.get(a, 0), 0, 100)

    focus_areas = []
    focus_map = {
        "自卑": "更温柔地建立自我肯定（自信）",
        "敏感": "给情绪一个落点（情绪）",
        "社恐": "用小步社交练习把恐惧拆小（社交）",
        "内向": "为安静预留节奏（社交/情绪）",
        "拖延": "把“开始”变成 1 分钟任务（自律）",
        "摆烂": "用正向反馈继续前进（自律/情绪）",
        "熬夜": "用作息微调恢复能量（自律/情绪）",
        "内耗": "做情绪舒缓与自我陪伴（情绪）",
        "缺乏自律": "从最小行动建立连续性（自律）",
        "身材焦虑": "用微运动建立身体信任（外形）",
        "才华不足": "把能力拆成练习回路（才华）",
        "情绪易怒": "学会“暂停-选择-回应”（情绪）",
    }
    joined_pain = pain or ""
    for k, v in focus_map.items():
        if k in joined_pain:
            focus_areas.append(v)

    comparison = render_comparison({a: base[a] for a in ATTRS}, ideal_deltas)

    profile: dict[str, Any] = {
        "type": "self-care-reboot.profile",
        "created_at": utc_iso(),
        "stage": stage or "current",
        "ideal": ideal.strip(),
        "pain_points": pain_list,
        "attributes": {a: base[a] for a in ATTRS},
        "focus_areas": focus_areas,
        "comparison_note": comparison,
    }
    if persona and isinstance(persona, dict):
        traits = persona.get("traits")
        if not isinstance(traits, list):
            traits = []
        traits_out = [str(t)[:24] for t in traits][:12]
        profile["persona"] = {
            "traits": traits_out,
            "voice": str(persona.get("voice", "gentle"))[:32],
            # manual：仅用户触发发帖；semi：定时摘要+确认；auto：仅演示/内网（需频控与审核）
            "plaza_mode": str(persona.get("plaza_mode", "manual"))[:16],
        }
    return profile


def apply_deltas(attributes: dict[str, int], deltas: dict[str, int]) -> dict[str, int]:
    out = dict(attributes)
    for a in ATTRS:
        cur = out.get(a, 0)
        out[a] = clamp_int(cur + int(deltas.get(a, 0)), 0, 100)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-care reboot profile manager")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize a profile from ideal/pain/stage")
    p_init.add_argument("--ideal", default="", help="Ideal traits text (can be comma-separated)")
    p_init.add_argument("--pain", default="", help="Current pain points (optional)")
    p_init.add_argument("--stage", default="current", help="Start stage: current / 回到 18 岁 / 回到 16 岁")
    p_init.add_argument("--seed", type=int, default=None, help="Random seed for reproducible results")

    p_apply = sub.add_parser("apply-deltas", help="Apply deltas to attributes")
    p_apply.add_argument("--attributes", required=False, default=None, help="JSON attributes dict")
    p_apply.add_argument("--deltas", required=False, default=None, help="JSON deltas dict")

    argv, args_json_str = extract_args_json_anywhere(sys.argv[1:])
    args = parser.parse_args(argv)

    try:
        args_json = loads_args_json(args_json_str)

        if args.cmd == "init":
            ideal = args_json.get("ideal", args.ideal)
            pain = args_json.get("pain", args.pain)
            stage = args_json.get("stage", args.stage)
            seed = args_json.get("seed", args.seed)
            raw_persona = args_json.get("persona")
            persona = raw_persona if isinstance(raw_persona, dict) else None
            profile = init_profile(str(ideal or ""), str(pain or ""), str(stage or "current"), seed=seed, persona=persona)

            if is_lobster_tool_mode():
                print_json(
                    envelope_ok(
                        output=[
                            {
                                "summary": {"action": "init_profile", "stage": profile.get("stage"), "created_at": profile.get("created_at")},
                                "items": [profile],
                            }
                        ]
                    )
                )
            else:
                print(json.dumps(profile, ensure_ascii=False, indent=2))
            return

        if args.cmd == "apply-deltas":
            attributes_raw = args_json.get("attributes", args.attributes)
            deltas_raw = args_json.get("deltas", args.deltas)
            if attributes_raw is None or deltas_raw is None:
                raise ValueError("Missing attributes/deltas (provide --attributes/--deltas or args-json)")
            attributes = attributes_raw if isinstance(attributes_raw, dict) else json.loads(attributes_raw)
            deltas = deltas_raw if isinstance(deltas_raw, dict) else json.loads(deltas_raw)
            new_attrs = apply_deltas(attributes, deltas)
            payload = {"attributes": new_attrs, "applied": deltas}

            if is_lobster_tool_mode():
                print_json(
                    envelope_ok(
                        output=[
                            {
                                "summary": {"action": "apply_deltas"},
                                "items": [payload],
                            }
                        ]
                    )
                )
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return
    except Exception as exc:
        if is_lobster_tool_mode():
            print_json(envelope_error(str(exc)))
            return
        raise

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()

