#!/usr/bin/env python3
"""
pixel_renderer.py

生成“像素风养成自己”的可视化图片：
1) 角色卡（单张 64x64 或 96x96 像素）
2) 三格分镜（横向 3 格，每格一小场景）

依赖：
  pip install pillow

说明：
- 这里只负责本地生成 PNG 文件，不做任何上传/分享。
- 由调用方决定图片路径与后续如何展示（例如在龙虾里发图片消息）。
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent


@dataclass
class PixelStyle:
    size: int = 64  # 单格基础尺寸
    scale: int = 4  # 放大倍数，实际像素风格更清晰


STYLE = PixelStyle()


def _safe_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    尝试加载等宽字体，失败则用默认字体。
    """
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _base_canvas(width: int, height: int, color: str = "#1b1b2f") -> Image.Image:
    return Image.new("RGBA", (width, height), color)


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _attr_color_bar(val: int) -> tuple[str, str]:
    """
    根据数值返回(条颜色, 背景颜色)。
    """
    v = max(0, min(100, int(val)))
    if v < 40:
        return "#5c6273", "#25293b"
    if v < 70:
        return "#8ad4ff", "#243447"
    return "#ffe27a", "#3b2f4a"


def render_avatar(attributes: Dict[str, int], life_phase: str, output_path: str) -> str:
    """
    生成单张像素角色卡。

    attributes: 六维属性 dict
    life_phase: 人生阶段描述（如 "child" / "teen" / "adult"）；勿与广场帖子 `forum` 分区混淆
    output_path: 输出 PNG 路径
    """
    size = STYLE.size
    scale = STYLE.scale
    w, h = size * scale, size * scale
    img = _base_canvas(w, h, "#171821")
    draw = ImageDraw.Draw(img)

    # 背景渐变（根据情绪值）
    emo = max(0, min(100, int(attributes.get("emotion", 50))))
    top = (20, 24, 60)
    mid = (36, 62, 114)
    hi = (66, 90, 146)
    c1 = top if emo < 40 else mid if emo < 75 else hi
    c2 = hi if emo < 40 else top if emo < 75 else mid
    for y in range(h):
        t = y / max(1, h - 1)
        r = _lerp(c1[0], c2[0], t)
        g = _lerp(c1[1], c2[1], t)
        b = _lerp(c1[2], c2[2], t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # 像素小人（非常简化：头+身体+四肢）
    center_x = w // 2
    unit = scale * 3  # 小人部件的基本单位

    # 年龄阶段影响身高
    lp_norm = (life_phase or "").lower()
    if "child" in lp_norm or "幼" in lp_norm:
        body_units = 4
    elif "teen" in lp_norm or "少" in lp_norm:
        body_units = 5
    else:
        body_units = 6

    body_height = body_units * unit
    head_r = unit * 2
    foot_y = h - unit * 2
    body_top_y = foot_y - body_height
    head_center_y = body_top_y - head_r + unit

    # 头
    head_color = "#ffe4c4"
    draw.ellipse(
        [
            (center_x - head_r, head_center_y - head_r),
            (center_x + head_r, head_center_y + head_r),
        ],
        fill=head_color,
        outline="#000000",
    )

    # 头发基于自信/外形
    conf = max(0, min(100, int(attributes.get("confidence", 50))))
    app = max(0, min(100, int(attributes.get("appearance", 50))))
    hair_color = "#3b2f4a" if conf < 40 else "#2f5c7a" if app < 70 else "#b36ad9"
    hair_height = unit if conf < 40 else int(unit * 1.5)
    draw.rectangle(
        [
            (center_x - head_r, head_center_y - head_r),
            (center_x + head_r, head_center_y - head_r + hair_height),
        ],
        fill=hair_color,
    )

    # 眼睛：情绪越高越弯
    eye_y = head_center_y
    eye_dx = unit
    emo_t = emo / 100.0
    for sign in (-1, 1):
        x = center_x + sign * eye_dx
        if emo < 40:
            draw.rectangle(
                [(x - scale, eye_y - scale), (x + scale, eye_y + scale)],
                fill="#222222",
            )
        else:
            # 微笑眼
            draw.arc(
                [
                    (x - scale * 2, eye_y - scale),
                    (x + scale * 2, eye_y + scale * 2),
                ],
                start=0,
                end=180,
                fill="#222222",
            )

    # 身体颜色按情绪/自律混合
    dis = max(0, min(100, int(attributes.get("discipline", 50))))
    body_color = "#4f6cf6" if dis >= 60 else "#4ca9e3" if emo >= 50 else "#56637a"

    body_width = unit * 4
    draw.rectangle(
        [
            (center_x - body_width // 2, body_top_y),
            (center_x + body_width // 2, foot_y),
        ],
        fill=body_color,
        outline="#000000",
    )

    # 手脚（小矩形）
    arm_y = body_top_y + unit
    arm_length = unit * 2
    draw.rectangle(
        [
            (center_x - body_width // 2 - arm_length, arm_y),
            (center_x - body_width // 2, arm_y + unit),
        ],
        fill=body_color,
    )
    draw.rectangle(
        [
            (center_x + body_width // 2, arm_y),
            (center_x + body_width // 2 + arm_length, arm_y + unit),
        ],
        fill=body_color,
    )

    leg_width = unit
    leg_top = foot_y - unit * 3
    for sign in (-1, 1):
        x = center_x + sign * unit
        draw.rectangle(
            [(x - leg_width // 2, leg_top), (x + leg_width // 2, foot_y)],
            fill="#30353f",
        )

    # 底部信息条：阶段 & 一个关键属性
    bar_h = unit * 2
    draw.rectangle([(0, h - bar_h), (w, h)], fill="#111218")
    font = _safe_font(size=int(scale * 2.2))
    phase_caption = "幼年自我" if "child" in lp_norm or "幼" in lp_norm else "未来的我"
    key_attr = max(
        ["confidence", "discipline", "emotion", "talent", "appearance", "social"],
        key=lambda k: int(attributes.get(k, 0)),
    )
    key_val = int(attributes.get(key_attr, 0))
    key_map = {
        "confidence": "自信",
        "discipline": "自律",
        "emotion": "情绪",
        "talent": "才华",
        "appearance": "外形",
        "social": "社交",
    }
    text = f"{phase_caption} · {key_map.get(key_attr,'属性')} {key_val}"
    draw.text((scale * 2, h - bar_h + scale), text, fill="#f5f5f5", font=font)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path


def render_three_panel(
    *,
    life_phase: str,
    action_label: str,
    emotion_label: str,
    line1: str,
    line2: str,
    line3: str,
    output_path: str,
) -> str:
    """
    生成三格分镜图（横向 3 格）。
    每格包含一个小人姿态变化 + 一句短文案。
    """
    size = STYLE.size
    scale = STYLE.scale
    single_w, single_h = size * scale, size * scale
    w, h = single_w * 3, single_h
    img = _base_canvas(w, h, "#0f1018")
    draw = ImageDraw.Draw(img)

    # 三格简单背景渐变 + 不同色调
    bg_colors = ["#1a1b2a", "#16222a", "#222b3a"]
    for i in range(3):
        x0 = i * single_w
        for y in range(single_h):
            base = ImageColor_get(bg_colors[i])
            factor = 0.2 + 0.8 * (y / max(1, single_h - 1))
            col = tuple(int(c * (0.5 + factor * 0.5)) for c in base)
            draw.line([(x0, y), (x0 + single_w, y)], fill=col)

    # 三个状态下的小人（头位置略微不同，表示状态变化）
    font = _safe_font(int(scale * 2.2))
    lines = [line1, line2, line3]

    for idx in range(3):
        panel_x = idx * single_w
        local = img.crop((panel_x, 0, panel_x + single_w, single_h))
        ldraw = ImageDraw.Draw(local)

        # 用一个简单的“脸表情 + 姿态”变化
        cx, cy = single_w // 2, int(single_h * 0.45)
        r = int(scale * 4.5)
        head_col = "#ffe4c4"
        ldraw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=head_col, outline="#000000")

        # 不同格子的表情
        if idx == 0:
            # 有点累
            ldraw.line([(cx - scale * 3, cy), (cx - scale, cy)], fill="#222222", width=1)
            ldraw.line([(cx + scale, cy), (cx + scale * 3, cy)], fill="#222222", width=1)
            ldraw.line([(cx - scale * 2, cy + scale * 3), (cx + scale * 2, cy + scale * 3)], fill="#b36b6b", width=1)
        elif idx == 1:
            # 认真做事
            ldraw.ellipse(
                [(cx - scale * 2, cy - scale), (cx - scale, cy + scale)],
                fill="#222222",
            )
            ldraw.ellipse(
                [(cx + scale, cy - scale), (cx + scale * 2, cy + scale)],
                fill="#222222",
            )
        else:
            # 轻微微笑
            ldraw.ellipse(
                [(cx - scale * 2, cy - scale), (cx - scale, cy + scale)],
                fill="#222222",
            )
            ldraw.ellipse(
                [(cx + scale, cy - scale), (cx + scale * 2, cy + scale)],
                fill="#222222",
            )
            ldraw.arc(
                [(cx - scale * 3, cy + scale), (cx + scale * 3, cy + scale * 4)],
                start=0,
                end=180,
                fill="#b36b6b",
            )

        # 下方文字
        text = lines[idx]
        text_y = int(single_h * 0.7)
        _draw_multiline_center(ldraw, text, cx, text_y, font, fill="#f5f5f5", max_width=int(single_w * 0.85))
        img.paste(local, (panel_x, 0))

    # 顶部标签：阶段 + 情绪 + 行动
    title_font = _safe_font(int(scale * 2.8))
    title = f"{life_phase} · {emotion_label} · {action_label}"
    bbox = title_font.getbbox(title)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, scale), title, fill="#f5f5f5", font=title_font)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path


def ImageColor_get(color: str) -> tuple[int, int, int]:
    from PIL import ImageColor

    return ImageColor.getrgb(color)


def _draw_multiline_center(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int,
    y: int,
    font: ImageFont.ImageFont,
    fill: str,
    max_width: int,
) -> None:
    """
    简易多行文字居中绘制。
    """
    words = list(text)
    lines: list[str] = []
    cur = ""
    for ch in words:
        bbox = font.getbbox(cur + ch)
        w = bbox[2] - bbox[0]
        if w > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)

    total_h = 0
    line_sizes = []
    for line in lines:
        bbox = font.getbbox(line)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_sizes.append((w, h))
        total_h += h + 2
    total_h -= 2

    start_y = y - total_h // 2
    cy = start_y
    for line, (lw, lh) in zip(lines, line_sizes):
        draw.text((cx - lw // 2, cy), line, fill=fill, font=font)
        cy += lh + 2


if __name__ == "__main__":
    # 简单本地测试
    attrs = {
        "confidence": 70,
        "discipline": 55,
        "emotion": 80,
        "talent": 40,
        "appearance": 60,
        "social": 50,
    }
    out_dir = ROOT / "debug"
    out_dir.mkdir(parents=True, exist_ok=True)
    avatar_path = out_dir / "avatar.png"
    render_avatar(attrs, life_phase="child", output_path=str(avatar_path))

    panel_path = out_dir / "three_panel.png"
    render_three_panel(
        life_phase="幼年自我",
        action_label="伸展 3 分钟",
        emotion_label="稍微轻松了一点",
        line1="今天的你，有点累。",
        line2="但你还是给自己做了一个小小的伸展。",
        line3="未来的你，会记得这份温柔的照顾。",
        output_path=str(panel_path),
    )
    print("generated:", avatar_path, panel_path)

