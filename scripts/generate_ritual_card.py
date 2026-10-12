#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
麦麦下班仪式感 · 卡片生成器

输入 JSON（命令行第一个参数为 JSON 文件路径，或从 stdin 读入）：
{
  "mood": "累",
  "timeText": "23:12",
  "store": "麦当劳阳泉桃北餐厅（24h）",
  "date": "2026-10-12",
  "copy": "今天也很努力地把一天撑完了……",
  "items": [{"name": "板烧鸡腿堡三件套", "price": "35.0", "kcal": 391}],
  "total": "35.0",
  "note": "数据来自麦当劳官方 MCP 实时接口"
}

输出：output/ritual_card_<时间戳>.png（750×1080）
若本机没装 Pillow，自动降级为同目录下 .md 文本卡片，不报错。
"""

import json
import os
import sys
import datetime

WIDTH, HEIGHT = 750, 1080
BG = (250, 246, 238)          # 宣纸暖白
INK = (44, 44, 41)            # 墨黑
MUTED = (122, 118, 110)       # 次级灰
GOLD = (186, 117, 23)         # 麦金
RED = (200, 60, 52)           # 朱红
CARD = (255, 255, 255)

FONT_DIRS = [
    "C:/Windows/Fonts",
    "/System/Library/Fonts",
    "/usr/share/fonts",
]
FONT_CANDIDATES = ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "NotoSansCJK-Regular.ttc"]


def find_font():
    for d in FONT_DIRS:
        for f in FONT_CANDIDATES:
            p = os.path.join(d, f)
            if os.path.exists(p):
                return p
    return None


def wrap(text, drawer, font, max_width):
    """按像素宽度折行，兼容中英文。"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        test = cur + ch
        if drawer.textlength(test, font=font) > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def render_png(data, out_path, font_path):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)

    f_title = ImageFont.truetype(font_path, 44)
    f_big = ImageFont.truetype(font_path, 34)
    f_body = ImageFont.truetype(font_path, 27)
    f_small = ImageFont.truetype(font_path, 21)
    f_tiny = ImageFont.truetype(font_path, 18)

    pad = 60
    y = 78

    # 顶部：店名 + 时间
    d.text((pad, y), data.get("store", ""), font=f_small, fill=MUTED)
    tr = data.get("timeText", "") + "  " + data.get("date", "")
    d.text((WIDTH - pad - d.textlength(tr, font=f_small), y), tr, font=f_small, fill=MUTED)
    y += 52

    # 标题
    mood = data.get("mood", "")
    title = "下班仪式感" + ("·" + mood if mood else "")
    d.text((pad, y), title, font=f_title, fill=INK)
    y += 70
    d.line((pad, y, WIDTH - pad, y), fill=(210, 205, 196), width=2)
    y += 40

    # 文案区（白卡片）
    copy = data.get("copy", "")
    lines = wrap(copy, d, f_big, WIDTH - pad * 2 - 56)
    box_h = max(220, 60 + len(lines) * 52)
    d.rounded_rectangle((pad, y, WIDTH - pad, y + box_h), radius=18, fill=CARD,
                        outline=(225, 220, 210), width=2)
    cy = y + 34
    for ln in lines:
        d.text((pad + 28, cy), ln, font=f_big, fill=INK)
        cy += 52
    y += box_h + 40

    # 推荐清单
    d.text((pad, y), "今晚这一餐", font=f_small, fill=GOLD)
    y += 42
    for it in data.get("items", []):
        name = it.get("name", "")
        d.text((pad, y), name, font=f_body, fill=INK)
        right = "%s 元" % it.get("price", "")
        d.text((WIDTH - pad - d.textlength(right, font=f_body), y), right, font=f_body, fill=INK)
        y += 42
        meta = "约 %s kcal" % it.get("kcal", "-")
        d.text((pad + 4, y), meta, font=f_tiny, fill=MUTED)
        y += 40
    y += 10

    # 总价
    d.line((pad, y, WIDTH - pad, y), fill=(210, 205, 196), width=2)
    y += 26
    d.text((pad, y), "合计", font=f_body, fill=INK)
    total = "%s 元" % data.get("total", "-")
    d.text((WIDTH - pad - d.textlength(total, font=f_big), y - 6), total, font=f_big, fill=RED)
    y += 60

    # 页脚
    note = data.get("note", "")
    for ln in wrap(note, d, f_tiny, WIDTH - pad * 2):
        d.text((pad, y), ln, font=f_tiny, fill=MUTED)
        y += 26
    y += 10
    d.text((pad, HEIGHT - 66), "本卡片由 WorkBuddy + 麦当劳官方 MCP 生成",
           font=f_tiny, fill=MUTED)

    img.save(out_path)
    return out_path


def render_md(data, out_path):
    lines = []
    lines.append("# 下班仪式感 · %s\n" % data.get("date", ""))
    lines.append("> %s · %s\n" % (data.get("store", ""), data.get("timeText", "")))
    lines.append("\n%s\n" % data.get("copy", ""))
    lines.append("\n## 今晚这一餐\n")
    for it in data.get("items", []):
        lines.append("- %s —— %s 元（约 %s kcal）" % (it.get("name", ""), it.get("price", ""), it.get("kcal", "-")))
    lines.append("\n**合计：%s 元**\n" % data.get("total", "-"))
    lines.append("\n_%s_\n" % data.get("note", ""))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(base, "output")
    os.makedirs(outdir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    font_path = find_font()
    try:
        if not font_path:
            raise RuntimeError("未找到中文字体")
        out = os.path.join(outdir, "ritual_card_%s.png" % stamp)
        render_png(data, out, font_path)
        kind = "PNG"
    except Exception as e:
        out = os.path.join(outdir, "ritual_card_%s.md" % stamp)
        render_md(data, out)
        kind = "Markdown（降级，原因：%s）" % e

    print(json.dumps({"ok": True, "path": out, "format": kind}, ensure_ascii=False))


if __name__ == "__main__":
    main()
