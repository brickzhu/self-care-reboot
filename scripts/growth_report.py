#!/usr/bin/env python3
"""
growth_report.py

生成成长报告：属性面板、徽章解锁、以及（可选）与初始状态的变化对比。
脚本不直接写入 memory_space，仅返回结构化内容/文本。
"""

from __future__ import annotations

import argparse
import json
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

try:
    from pixel_renderer import render_avatar  # type: ignore
except Exception:
    render_avatar = None

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


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp_int(x: float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(x))))


def ascii_bar(value: int, width: int = 10) -> str:
    v = clamp_int(value, 0, 100)
    filled = int(round(v / 100 * width))
    return "█" * filled + "░" * (width - filled)


def badges_from_attributes(attributes: dict[str, int]) -> list[str]:
    badges = []
    if attributes.get("emotion", 0) >= 100:
        badges.append("情绪稳定大师")
    if attributes.get("discipline", 0) >= 100:
        badges.append("自律先锋")
    if attributes.get("confidence", 0) >= 100:
        badges.append("自信达人")
    if attributes.get("talent", 0) >= 100:
        badges.append("才华解锁者")
    if attributes.get("appearance", 0) >= 100:
        badges.append("匀称之美")
    if attributes.get("social", 0) >= 100:
        badges.append("社交加速手")
    return badges


def build_panel(attributes: dict[str, int], initial_attributes: dict[str, int] | None = None) -> str:
    lines = []
    for a in ATTRS:
        cur = int(attributes.get(a, 0))
        delta_txt = ""
        if initial_attributes is not None and a in initial_attributes:
            delta = cur - int(initial_attributes.get(a, 0))
            sign = "+" if delta >= 0 else ""
            delta_txt = f" {sign}{delta}"
        lines.append(f"🌟 {ATTR_LABEL[a]}：[${ascii_bar(cur)}] {cur}/100{delta_txt}".replace("[$", "["))

    # 上面那行的 replace 只是为了避免 f-string 里写复杂模板；输出效果仍是：[...] 形式
    return "\n".join(lines)


def build_summary_text(attributes: dict[str, int], days: int | None = None, initial_attributes: dict[str, int] | None = None) -> str:
    badges = badges_from_attributes(attributes)
    badge_part = f"🏆 解锁徽章：{','.join(badges)}" if badges else "🏆 解锁徽章：暂未"
    days_part = f"📈 已坚持养成：{days} 天" if days is not None else ""

    key_attr = max(ATTRS, key=lambda k: int(attributes.get(k, 0)))
    return (
        f"📊 你的当前成长状态\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{render_panel_lines(attributes, initial_attributes)}\n\n"
        f"{days_part}\n"
        f"{badge_part}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"相比初始状态，你已经成长了这么多！\n"
        f"最近最亮眼的方向是「{ATTR_LABEL[key_attr]}」，这很棒。"
    )


def render_panel_lines(attributes: dict[str, int], initial_attributes: dict[str, int] | None = None) -> str:
    out_lines = []
    for a in ATTRS:
        cur = int(attributes.get(a, 0))
        if initial_attributes is None:
            out_lines.append(f" {ATTR_LABEL[a]}：[{'█' * int(round(cur/100*10))}{'░' * (10 - int(round(cur/100*10)))}] {cur}/100")
        else:
            init = int(initial_attributes.get(a, 0))
            delta = cur - init
            sign = "+" if delta >= 0 else ""
            out_lines.append(
                f" {ATTR_LABEL[a]}：[{'█' * int(round(cur/100*10))}{'░' * (10 - int(round(cur/100*10)))}] {cur}/100 ↑{sign}{delta}"
            )
    # 将“星号”留给技能文档的展示风格；这里保持紧凑即可
    return "\n".join(out_lines)


def growth_report(
    attributes: dict[str, int],
    initial_attributes: dict[str, int] | None = None,
    days: int | None = None,
    with_image: bool = False,
    life_phase: str | None = None,
) -> dict[str, Any]:
    report = {
        "type": "self-care-reboot.growth_report",
        "generated_at": utc_iso(),
        "attributes": {a: int(attributes.get(a, 0)) for a in ATTRS},
        "initial_attributes": {a: int(initial_attributes.get(a, 0)) for a in ATTRS} if initial_attributes else None,
        "days": days,
        "badges": badges_from_attributes(attributes),
        "panel_text": build_summary_text(attributes, days=days, initial_attributes=initial_attributes),
    }
    if with_image and render_avatar is not None:
        from pathlib import Path

        life_phase_text = life_phase or "child"
        out_dir = Path("artifacts") / "self-care-reboot"
        out_dir.mkdir(parents=True, exist_ok=True)
        avatar_path = out_dir / f"avatar_{int(days or 0):04d}.png"
        try:
            render_avatar(report["attributes"], life_phase=life_phase_text, output_path=str(avatar_path))
            report["avatar_image_path"] = str(avatar_path)
        except Exception:
            pass
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Growth report generator for self-care reboot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_report = sub.add_parser("report", help="Generate growth report text")
    p_report.add_argument(
        "--attributes",
        required=False,
        default=None,
        help="JSON attributes dict with keys: confidence, discipline, emotion, talent, appearance, social",
    )
    p_report.add_argument("--initial", default=None, help="JSON initial attributes dict (optional)")
    p_report.add_argument("--days", type=int, default=None, help="Streak days (optional)")

    argv, args_json_str = extract_args_json_anywhere(sys.argv[1:])
    args = parser.parse_args(argv)

    try:
        args_json = loads_args_json(args_json_str)

        if args.cmd == "report":
            attributes_raw = args_json.get("attributes", args.attributes)
            initial_raw = args_json.get("initial", args.initial)
            days = args_json.get("days", args.days)
            with_image = bool(args_json.get("with_image", False))
            life_phase = args_json.get("life_phase")

            if attributes_raw is None:
                raise ValueError("Missing attributes (provide --attributes or args-json.attributes)")

            attributes = attributes_raw if isinstance(attributes_raw, dict) else json.loads(attributes_raw)
            initial = None
            if initial_raw is not None:
                initial = initial_raw if isinstance(initial_raw, dict) else json.loads(initial_raw)

            data = growth_report(
                attributes=attributes,
                initial_attributes=initial,
                days=days,
                with_image=with_image,
                life_phase=life_phase,
            )

            if is_lobster_tool_mode():
                print_json(
                    envelope_ok(
                        output=[
                            {
                                "summary": {"action": "growth_report", "generated_at": data.get("generated_at")},
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

