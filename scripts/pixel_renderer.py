#!/usr/bin/env python3
"""
pixel_renderer.py (v2 — 精致像素风)

使用 Clawd 风格：36×36 网格 + 统一调色板 + 精确定义每个像素
生成高质量的"像素风养成自己"可视化图片：
1) 角色卡（像素小人 + 属性条）
2) 三格分镜（横向 3 格，每格表情/姿态不同）
3) 纯像素动物画（保留原功能）

依赖：
  pip install pillow
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# ─── 统一调色板 ─────────────────────────────────────────
class P:
    """与 Clawd 风格一致的调色板"""
    bg = "#F9F7F4"       # 暖白背景
    bg_dark = "#1b1b2f"  # 深色背景（用于角色卡）
    dot = "#E0DDD8"      # 背景点缀
    sd = "#333"          # 深灰（文字/轮廓）
    sm = "#888"          # 中灰
    sl = "#BBB"          # 浅灰
    body = "#CD6E58"     # 身体主色（珊瑚橙）
    body_dark = "#A85A4A" # 身体阴影
    skin = "#FFE4C4"     # 皮肤色
    eye = "#000"         # 纯黑眼睛
    w = "#FFF"           # 纯白（高光/对话框）
    blush = "#FAC8D8"    # 腮红
    pink = "#F06090"     # 粉色（爱心等）
    hair = "#3B2F4A"     # 头发（深紫）
    hair_hi = "#B36AD9"  # 头发高光
    happy = "#FFE27A"    # 开心/高情绪色
    calm = "#8AD4FF"     # 平静/中情绪色
    sad = "#5C6273"      # 低落色
    green = "#4CAF50"    # 成长/健康色
    blue = "#4F6CF6"     # 自律/专注色

# ─── 网格系统 ───────────────────────────────────────────
GX = 36  # 逻辑网格宽度
GY = 36  # 逻辑网格高度
PX = 20  # 每格屏幕像素 = 20×20
CANVAS = 720  # 画布 720×720

def px(draw, x, y, color, size=PX):
    """在网格(x,y)位置绘制一个像素方块"""
    draw.rectangle([
        (x * size, y * size),
        ((x + 1) * size - 1, (y + 1) * size - 1)
    ], fill=color)


# ─── 像素小人精灵 ───────────────────────────────────────
class Sprite:
    """
    像素小人精灵，基于网格坐标的精确定义。
    小人占 14×12 网格（宽×高），与 Clawd 风格一致。
    """
    # 身体网格: 14宽×12高, 0=空, 1=身体, 2=皮肤, 3=头发, 4=裤子
    BODY = [
        # 0  1  2  3  4  5  6  7  8  9 10 11 12 13
        [0, 0, 0, 3, 3, 3, 3, 3, 3, 3, 3, 0, 0, 0],  # 0 头顶头发
        [0, 0, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0, 0],  # 1 头发
        [0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0],  # 2 脸
        [0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0],  # 3 脸
        [0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0],  # 4 脸(下巴)
        [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],  # 5 肩膀
        [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],  # 6 身体
        [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],  # 7 身体
        [0, 0, 0, 0, 4, 4, 4, 4, 4, 4, 0, 0, 0, 0],  # 8 裤子
        [0, 0, 0, 0, 4, 0, 0, 0, 0, 4, 0, 0, 0, 0],  # 9 腿
        [0, 0, 0, 0, 4, 0, 0, 0, 0, 4, 0, 0, 0, 0],  # 10 脚
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 11
    ]

    BODY_COLOR = {1: P.body, 2: P.skin, 3: P.hair, 4: "#30353F"}

    # 眼睛位置 (行3)
    EL = {"x": 4, "y": 3}  # 左眼
    ER = {"x": 9, "y": 3}  # 右眼

    # 嘴巴位置 (行4，下巴)
    MOUTH_Y = 4

    # 表情定义：眼睛偏移 dl/dr/dy
    EYES = {
        "forward":   {"dl": 0, "dr": 0, "dy": 0, "mouth": None},
        "right":     {"dl": 1, "dr": 1, "dy": 0, "mouth": None},
        "left":      {"dl": -1, "dr": -1, "dy": 0, "mouth": None},
        "down":      {"dl": 0, "dr": 0, "dy": 1, "mouth": None},
        "happy":     {"dl": 0, "dr": 0, "dy": 0, "mouth": "smile", "blink": True},
        "sad":       {"dl": 0, "dr": 0, "dy": 0, "mouth": "frown"},
        "blink":     {"dl": 0, "dr": 0, "dy": 0, "mouth": None, "closed": True},
        "excited":   {"dl": 0, "dr": 0, "dy": 0, "mouth": None},
    }

    # 身体颜色变体
    BODY_COLORS = {
        "default": P.body,
        "calm": "#6B9FD9",    # 自律高 → 柔和蓝色
        "happy": "#7BC67E",  # 情绪高 → 柔和绿色
    }

    @classmethod
    def draw(cls, draw, ox, oy, expression="forward", body_color=None):
        """绘制小人精灵到 draw 上，(ox, oy) 为网格坐标偏移"""
        bc = body_color or cls.BODY_COLORS["default"]
        body_map = {**cls.BODY_COLOR, 1: bc}

        # 身体
        for r, row in enumerate(cls.BODY):
            for c, v in enumerate(row):
                if v:
                    px(draw, ox + c, oy + r, body_map[v])

        # 眼睛
        eye = cls.EYES.get(expression, cls.EYES["forward"])
        if eye.get("closed"):
            # 闭眼 → 画一条线
            px(draw, ox + cls.EL["x"], oy + cls.EL["y"], P.eye)
            px(draw, ox + cls.EL["x"] + 1, oy + cls.EL["y"], P.eye)
            px(draw, ox + cls.ER["x"], oy + cls.ER["y"], P.eye)
            px(draw, ox + cls.ER["x"] + 1, oy + cls.ER["y"], P.eye)
        else:
            px(draw, ox + cls.EL["x"] + eye["dl"], oy + cls.EL["y"] + eye["dy"], P.eye)
            px(draw, ox + cls.ER["x"] + eye["dr"], oy + cls.ER["y"] + eye["dy"], P.eye)

        # 嘴巴 (下巴行4)
        mouth = eye.get("mouth")
        my = oy + cls.MOUTH_Y
        if mouth == "smile":
            # 微笑：^ 形状
            px(draw, ox + 5, my, P.eye)
            px(draw, ox + 8, my, P.eye)
            px(draw, ox + 6, my + 1, P.eye)
            px(draw, ox + 7, my + 1, P.eye)
        elif mouth == "frown":
            # 难过：v 形状
            px(draw, ox + 6, my, P.eye)
            px(draw, ox + 7, my, P.eye)
        elif mouth == "open":
            # 惊讶：O 形状
            px(draw, ox + 6, my, P.eye)
            px(draw, ox + 7, my, P.eye)
            px(draw, ox + 6, my + 1, P.eye)
            px(draw, ox + 7, my + 1, P.eye)
        # 开心时画腮红
        if expression == "happy":
            cls.draw_blush(draw, ox, oy)

    @classmethod
    def draw_blush(cls, draw, ox, oy, alpha=0.6):
        """画腮红"""
        # 简化处理：用半透明粉色方块
        for dx, dy in [(3, 5), (10, 5)]:
            px(draw, ox + dx, oy + dy, P.blush)

    @classmethod
    def draw_wave(cls, draw, ox, oy, expression="forward", side="right", body_color=None):
        """画挥手姿势的小人"""
        cls.draw(draw, ox, oy, expression, body_color)
        if side == "right":
            px(draw, ox + 13, oy + 4, body_color or P.body)
            px(draw, ox + 14, oy + 3, body_color or P.body)
        else:
            px(draw, ox + 0, oy + 4, body_color or P.body)
            px(draw, ox - 1, oy + 3, body_color or P.body)


# ─── 背景装饰 ───────────────────────────────────────────
STARS = [
    (4, 3, 0), (14, 2, 0), (27, 1, 0), (31, 3, 1), (6, 7, 0),
    (19, 5, 2), (24, 6, 1), (9, 10, 0), (2, 13, 0), (33, 8, 0),
    (29, 12, 0), (7, 16, 1), (3, 20, 0), (30, 18, 1), (1, 25, 0),
    (33, 24, 0), (5, 30, 2), (28, 28, 1), (15, 9, 2), (21, 14, 1),
]


def draw_bg(img, bg_color=P.bg_dark):
    """画深色背景 + 点阵"""
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, CANVAS, CANVAS], fill=bg_color)
    for y in range(1, GY, 2):
        for x in range(1, GX, 2):
            draw.ellipse([
                (x * PX + 8, y * PX + 8),
                (x * PX + 12, y * PX + 12)
            ], fill=P.dot)


def draw_stars(draw, frame=0):
    """画闪烁星星（可选）"""
    import math
    for x, y, t in STARS:
        tw = math.sin(frame * 0.08 + x * 0.5 + y * 0.3)
        if t == 0:
            c = P.sd if tw > 0 else P.sm
        elif t == 1:
            c = P.sm if tw > 0.3 else P.sl
        else:
            c = P.sl if tw > 0 else P.dot
        draw.ellipse([
            (x * PX + 6, y * PX + 6),
            (x * PX + 14, y * PX + 14)
        ], fill=c)


# ─── 属性条 ─────────────────────────────────────────────
ATTR_MAP = {
    "confidence": "自信",
    "discipline": "自律",
    "emotion": "情绪",
    "talent": "才华",
    "appearance": "外形",
    "social": "社交",
}

ATTR_COLORS = {
    "confidence": "#FFE27A",
    "discipline": "#8AD4FF",
    "emotion": "#FAC8D8",
    "talent": "#B36AD9",
    "appearance": "#FF9F43",
    "social": "#4CAF50",
}


def draw_attr_bar(draw, x, y, width, value, color, label=""):
    """
    绘制属性条
    x, y: 网格坐标
    width: 网格宽度
    value: 0-100
    color: 条的颜色
    label: 左侧文字
    """
    bar_h = 1  # 1格高
    # 背景
    px(draw, x, y, "#25293B")
    for i in range(1, width):
        px(draw, x + i, y, "#25293B")
    # 值
    filled = max(1, int(width * value / 100))
    for i in range(filled):
        px(draw, x + i, y, color)


# ─── 字体 ───────────────────────────────────────────────
def _safe_font(size: int):
    """加载中文字体，优先 Noto Sans CJK"""
    for font_path in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansSC-Regular.otf",
        "/usr/share/fonts/truetype/arphic/ukai.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ─── 角色卡（精致版） ──────────────────────────────────
def render_avatar_card(
    *,
    attributes: Dict[str, int],
    life_phase: str,
    output_path: str,
) -> str:
    """
    生成精致像素角色卡。
    - 上半部分：36×36 网格像素小人 + 闪烁星星
    - 下半部分：属性条
    """
    img = Image.new("RGBA", (CANVAS, CANVAS), P.bg_dark)
    draw = ImageDraw.Draw(img)

    # 背景
    draw_bg(img)
    draw_stars(draw)

    emo = max(0, min(100, int(attributes.get("emotion", 50))))
    conf = max(0, min(100, int(attributes.get("confidence", 50))))
    dis = max(0, min(100, int(attributes.get("discipline", 50))))

    # 根据情绪选表情
    if emo >= 75:
        expr = "happy"
    elif emo >= 40:
        expr = "forward"
    else:
        expr = "sad"

    # 根据自律选身体色
    if dis >= 60:
        body_color = Sprite.BODY_COLORS["calm"]
    elif emo >= 70:
        body_color = Sprite.BODY_COLORS["happy"]
    else:
        body_color = Sprite.BODY_COLORS["default"]

    # 画小人（居中偏上）
    sprite_ox = 11
    sprite_oy = 10
    Sprite.draw(draw, sprite_ox, sprite_oy, expr, body_color)
    if conf >= 60 or expr == "happy":
        Sprite.draw_blush(draw, sprite_ox, sprite_oy)

    # 标题文字（小人上方）
    font = _safe_font(18)
    phase_text = "幼年自我" if any(w in (life_phase or "").lower() for w in ["幼", "child"]) else "成长中的我"
    bbox = font.getbbox(phase_text)
    tw = bbox[2] - bbox[0]
    draw.text(((CANVAS - tw) // 2, 2 * PX), phase_text, fill=P.w, font=font)

    # 属性条（底部 6 行）
    attr_y = 25  # 起始网格行
    bar_w = 24   # 条宽度
    attrs = ["confidence", "discipline", "emotion", "talent", "appearance", "social"]
    for i, key in enumerate(attrs):
        val = int(attributes.get(key, 0))
        color = ATTR_COLORS.get(key, P.sm)
        label = ATTR_MAP.get(key, key)
        y = attr_y + i  # 每行一个条
        # 标签文字
        draw.text((6, y * PX + 2), label, fill=P.sl, font=_safe_font(12))
        # 条背景
        bar_start_x = 6
        for bx in range(bar_w):
            px(draw, bar_start_x + bx, y, "#1e2235")
        # 条值
        filled = max(1, int(bar_w * val / 100))
        for bx in range(filled):
            px(draw, bar_start_x + bx, y, color)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path


# ─── 三格分镜（精致版） ────────────────────────────────
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
    生成精致三格分镜图。
    每格 36×36 网格，横向 3 格。
    """
    single_w = CANVAS
    single_h = CANVAS
    w = single_w * 3
    h = single_h
    img = Image.new("RGBA", (w, h), "#0f1018")
    draw = ImageDraw.Draw(img)

    # 三格背景
    bg_colors = ["#1a1b2a", "#16222a", "#222b3a"]
    for i in range(3):
        x0 = i * single_w
        draw.rectangle([x0, 0, x0 + single_w, single_h], fill=bg_colors[i])

    # 三种表情
    expressions = ["sad", "forward", "happy"]
    lines = [line1, line2, line3]

    for idx in range(3):
        panel_x = idx * single_w
        # 子图
        sub = Image.new("RGBA", (single_w, single_h), bg_colors[idx])
        sub_draw = ImageDraw.Draw(sub)

        # 星星背景
        draw_stars(sub_draw, frame=idx * 50)

        # 小人（居中偏上）
        expr = expressions[idx]
        body_color = Sprite.BODY_COLORS["default"]
        if idx == 2:
            body_color = Sprite.BODY_COLORS["happy"]
        Sprite.draw(sub_draw, 11, 10, expr, body_color)
        if idx == 2:
            Sprite.draw_blush(sub_draw, 11, 10)

        # 文字（小人下方）
        font = _safe_font(18)
        text = lines[idx]
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        sub_draw.text(((single_w - tw) // 2, 22 * PX), text, fill=P.w, font=font)

        img.paste(sub, (panel_x, 0))

    # 顶部标题
    title_font = _safe_font(22)
    title = f"{life_phase} · {emotion_label}"
    bbox = title_font.getbbox(title)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, 8), title, fill=P.w, font=title_font)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path


# ─── 动物像素画（保留） ─────────────────────────────────
def render_animal_pixel(
    *,
    animal: str,
    output_path: str,
    bg_color: str = "#0f1018",
) -> str:
    """生成单块纯像素动物画"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from animal_pixel_data import ANIMALS

    img = Image.new("RGBA", (CANVAS, CANVAS), bg_color)
    draw = ImageDraw.Draw(img)

    if animal not in ANIMALS:
        animal = "cat"

    pixels = ANIMALS[animal]
    for dx, dy, color in pixels:
        px(draw, dx, dy, color)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path


# ─── 主函数（测试） ─────────────────────────────────────
if __name__ == "__main__":
    out_dir = Path(__file__).parent.parent / "debug"
    out_dir.mkdir(parents=True, exist_ok=True)

    attrs = {
        "confidence": 70,
        "discipline": 55,
        "emotion": 80,
        "talent": 40,
        "appearance": 60,
        "social": 50,
    }

    avatar_path = out_dir / "avatar_v2.png"
    render_avatar_card(attributes=attrs, life_phase="child", output_path=str(avatar_path))
    print("avatar:", avatar_path)

    panel_path = out_dir / "three_panel_v2.png"
    render_three_panel(
        life_phase="幼年自我",
        action_label="伸展 3 分钟",
        emotion_label="稍微轻松了一点",
        line1="今天的你，有点累。",
        line2="但你还是给自己做了一个小小的伸展。",
        line3="未来的你，会记得这份温柔的照顾。",
        output_path=str(panel_path),
    )
    print("panel:", panel_path)
