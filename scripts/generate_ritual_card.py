#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
麦麦下班仪式感 · 卡片生成器（先贤插画版）

输入 JSON（命令行第一个参数为 JSON 文件路径，或从 stdin 读入）：
{
  "mood": "累",
  "timeText": "23:12",
  "store": "麦当劳阳泉桃北餐厅（24h）",
  "date": "2026-10-12",
  "copy": "今天也很努力地把一天撑完了……",
  "items": [{"name": "板烧鸡腿堡三件套", "price": "35.0", "kcal": 391}],
  "total": "35.0",
  "note": "数据来自麦当劳官方 MCP 实时接口",
  "sage": {
    "id": "sushi",                          // 必填：先贤 id（解析插画文件名用）
    "scene": "S07",                         // 选填：场景 id（S01–S12，仅作记录）
    "name": "苏轼",                          // 必填：先贤名（落款用）
    "quote": "高兴这事，不用等大日子。",        // 必填：贴心话（先贤版大字号独立成区；无插画时进 md 降级）
    "classic": "自笑平生为口忙",              // 选填：典籍引文（画窗内书法题词）
    "source": "《初到黄州》",                 // 选填：出处（落款）
    "seal": "苏",                            // 选填：印章字（缺省取 name 首字）
    "intro": "最会张罗庆祝的那位，来了。",      // 选填：出场白（只用于聊天回复，不上卡）
    "image": "upgrade/illustrations/sage_sushi.png"  // 选填：显式插画路径
  }
}

输出：output/ritual_card_<时间戳>.png（750×1080）
- 输入带 sage 且本地能找到对应插画 → 卡片叠加「先贤区」画窗带
  （630×300 插画 + 书法题词 + 落款 + 朱文印章；贴心话以大字号独立成区）；
- 找不到插画文件 → 退回纯文字版式：有 sage 时附加贴心话文字层
  （金色首行 + 饭搭子署名，防功能静默失败）；无 sage 时与原来逐行一致；
- 若本机没装 Pillow → 自动降级为同目录下 .md 文本卡片，不报错。

先贤文案硬校验（00 纪要 §10，渲染入口，不通过则拒绝出卡并告警、严禁截断）：
  1. 贴心话 quote ≤20 字；
  2. quote / classic / intro 不得含 forbidden_copy 禁忌词（尤其"求签/解签"）。

插画文件约定（依据 00_团长拍板对齐纪要 §3，约定优于配置，无需改代码）：
  upgrade/illustrations/sage_<id>.png   一位先贤一张，跨场景复用
  交付规格 1260×600（2×），运行时居中裁 cover 后缩放到 630×300。
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
PAPER = (250, 246, 238)       # 题词底衬（宣纸暖白）

# ---- 先贤插画资产约定（依据 00_团长拍板对齐纪要 §3）----
# 存放位置：upgrade/illustrations/；命名：sage_<先贤id>.png（一位先贤一张，跨场景复用）
ILLUSTRATION_SUBDIR = os.path.join("upgrade", "illustrations")
SAGE_BAND_XY = (60, 216)      # 先贤区（画窗带）左上角
SAGE_BAND_WH = (630, 300)     # 先贤区尺寸（与插画交付比例 21:10 一致）
SAGE_BAND_RADIUS = 20         # 画窗圆角
SAGE_CALLO_SIZE = 34          # 题词字号（行楷）
SAGE_QUOTE_SIZE = 34          # 贴心话字号（全卡内容区最大）
SAGE_COPY_SIZE = 24           # 先贤版情绪文案字号（原版为 27，为先贤区让位）
SAGE_SEAL_SIZE = 26           # 朱文印章边长
SAGE_FOOTER_RIGHT = 546       # 先贤版页脚文字右界（避开 x566–690 二维码/券码预留区）

FONT_DIRS = [
    "C:/Windows/Fonts",
    "/System/Library/Fonts",
    "/usr/share/fonts",
]
FONT_CANDIDATES = ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "NotoSansCJK-Regular.ttc"]
# 题词字体链：华文行楷 → 楷体 → 回落正文字体
CALLO_FONT_CANDIDATES = ["STXINGKA.TTF", "simkai.ttf", "msyh.ttc", "simhei.ttf"]


def project_root():
    """Skill 包根目录（scripts/ 的上一级）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_font():
    for d in FONT_DIRS:
        for f in FONT_CANDIDATES:
            p = os.path.join(d, f)
            if os.path.exists(p):
                return p
    return None


def find_calligraphy_font():
    """题专用字体：行楷优先，找不到返回 None（由调用方回落正文字体）。"""
    for d in FONT_DIRS:
        for f in CALLO_FONT_CANDIDATES:
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


# ------------------------------------------------------------------
# 新增：先贤插画层（解析 → 加载 → 版式）
# ------------------------------------------------------------------

def resolve_sage_illustration(data, base_dir=None):
    """按约定目录解析 sage 对应的本地插画文件路径。

    查找顺序（依据 00_团长拍板对齐纪要 §3，约定优于配置）：
      1. upgrade/illustrations/sage_<id>.png   拍板位置（一位先贤一张）
      2. sage.image 显式路径（相对项目根或绝对路径，应急通道）
    参数：
        data     —— 卡片输入 JSON（读 sage.id / sage.image）
        base_dir —— Skill 包根目录，默认自动推断（scripts/ 的上一级）
    返回：
        插画文件的绝对路径；找不到、字段缺失、路径不合法一律返回 None。
        本函数保证不抛异常——插画层任何问题都不能拖垮卡片生成。
    """
    try:
        sage = data.get("sage") or {}
        sid = str(sage.get("id", "")).strip().strip("/\\")
        if not sid:
            return None
        root = base_dir or project_root()
        candidates = [os.path.join(ILLUSTRATION_SUBDIR, "sage_%s.png" % sid)]
        img = str(sage.get("image", "")).strip()
        if img:
            candidates.append(img)
        for c in candidates:
            p = c if os.path.isabs(c) else os.path.join(root, c)
            if os.path.isfile(p):
                return p
        return None
    except Exception:
        return None


def load_illustration(path, size=SAGE_BAND_WH):
    """打开插画并居中裁 cover 到目标尺寸（默认 630×300）。

    参数：
        path —— 插画文件路径（PNG，交付规格 1260×600）
        size —— 目标显示尺寸 (宽, 高)
    返回：
        PIL.Image（RGBA）；打开/解码/裁切任何一步失败都返回 None。
    """
    try:
        from PIL import Image
        img = Image.open(path)
        img = img.convert("RGBA")
        tw, th = size
        # 居中裁到目标宽高比（cover），再缩放，避免拉伸变形
        w, h = img.size
        target = tw / th
        if w / h > target:          # 太宽 → 裁左右
            nw = int(h * target)
            left = (w - nw) // 2
            img = img.crop((left, 0, left + nw, h))
        elif w / h < target:        # 太高 → 裁上下
            nh = int(w / target)
            top = (h - nh) // 2
            img = img.crop((0, top, w, top + nh))
        if img.size != (tw, th):
            img = img.resize((tw, th), Image.LANCZOS)
        return img
    except Exception:
        return None


def load_forbidden_words(base_dir=None):
    """从 references/sage_match.json 读 forbidden_copy 禁忌词表；读不到用内置兜底。"""
    fallback = ["治愈", "疗效", "保佑", "开运", "显灵", "天意", "命里",
                "注定", "转运", "消灾", "渡劫", "求签", "解签"]
    try:
        path = os.path.join(base_dir or project_root(), "references", "sage_match.json")
        with open(path, "r", encoding="utf-8") as f:
            words = json.load(f).get("forbidden_copy") or []
        return words or fallback
    except Exception:
        return fallback


def validate_sage_copy(data, base_dir=None):
    """先贤文案硬校验（00 纪要 §10）。返回告警列表，空列表 = 通过。

    规则：
    1. 贴心话 quote ≤20 字，超长 → 告警（渲染入口拒绝出卡，严禁截断——
       截断会改变文案语义，宁可报错也不截）；
    2. quote / classic / intro 不得含 forbidden_copy 禁忌词
       （尤其"求签/解签"——先贤不是算命，须与麦当劳官方抽奖隔离）。
    """
    warnings = []
    sage = data.get("sage") or {}
    quote = str(sage.get("quote", ""))
    if quote and len(quote) > 20:
        warnings.append("贴心话超长：%d 字 > 20 字上限（%s）" % (len(quote), quote))
    forbidden = load_forbidden_words(base_dir)
    for field in ("quote", "classic", "intro"):
        v = str(sage.get(field, ""))
        hit = [w for w in forbidden if w in v]
        if hit:
            warnings.append("%s 含禁忌词 %s（%s）" % (field, "、".join(hit), v))
    return warnings


def render_png(data, out_path, font_path, illustration_path=None):
    """PNG 渲染总入口。

    参数：
        data             —— 卡片输入 JSON
        out_path         —— 输出 PNG 路径
        font_path        —— 中文字体路径
        illustration_path—— 先贤插画文件路径；None 表示纯文字卡片（原版式）
    行为：
        illustration_path 为 None → 走原版纯文字版式（与改造前逐行一致）；
        有插画路径 → 走先贤版式；插画加载失败 → 自动回退纯文字版式。
    """
    if illustration_path:
        illustration = load_illustration(illustration_path)
        if illustration is not None:
            return render_png_with_sage(data, out_path, font_path, illustration)
    return render_png_plain(data, out_path, font_path)


def render_png_plain(data, out_path, font_path):
    """纯文字卡片版式（750×1080）。

    无 sage 输入时与原版逐行一致（历史行为不变）。
    有 sage 但无插画文件时（降级路径），在文案卡内附加渲染：
    金色贴心话首行 +「今晚的饭搭子 · {name}」署名小字——
    避免插画缺失时功能"静默失败"（用户被识别出先贤却看不到任何痕迹）。
    """
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
    sage = data.get("sage") or {}
    quote = sage.get("quote", "")
    who = sage.get("name", "")
    # 无插画降级时，先贤贴心话（纯文字层）必须保留，否则功能"静默失败"——
    # 用户被识别出先贤却在卡片上看不到任何痕迹，会以为功能没生效。
    extra = (40 if quote else 0) + (34 if quote and who else 0)
    box_h = max(220, 60 + extra + len(lines) * 52)
    d.rounded_rectangle((pad, y, WIDTH - pad, y + box_h), radius=18, fill=CARD,
                        outline=(225, 220, 210), width=2)
    cy = y + 34
    if quote:
        d.text((pad + 28, cy), quote, font=f_body, fill=GOLD)
        cy += 40
        if who:
            d.text((pad + 28, cy), "—— 今晚的饭搭子 · " + who, font=f_tiny, fill=MUTED)
            cy += 34
    for ln in lines:
        d.text((pad + 28, cy), ln, font=f_body, fill=INK)
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


def render_png_with_sage(data, out_path, font_path, illustration):
    """先贤版卡片版式（750×1080，方案 A：标题下「画窗带」）。

    版式分区（依据 00_团长拍板对齐纪要 §5 合并叙事 + 02 方案 A）：
      A 顶栏      78–130    店名 / 时间+日期（原样保留）
      B 标题区    130–200   「下班仪式感·{mood}」+ 分隔线（原样保留）
      C 先贤区    216–516   630×300 插画 + 圆角烫金描边 + 书法题词 + 落款 + 朱文印章
      D 贴心话区  536 起     34pt 麦金「quote」（全卡内容区最大字号，≤2 行）
      E 文案卡    D 后      情绪文案（24pt，≤3 行，超出末行加「…」）
      F 餐单区    E 后      「今晚这一餐」+ 条目（单行 40px：名称/价格/热量，溢出截断）
      G 合计区    F 后      分隔线 + 合计 + 总价（朱红 34pt）
      H 页脚区    G 后      note 小字（放不下自动省行）+ 生成说明贴底
    所有区间动态流动 + 溢出保护，任何输入不画出 1080 画布。
    """
    from PIL import Image, ImageDraw, ImageFont, ImageChops

    img = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    d = ImageDraw.Draw(img)

    f_title = ImageFont.truetype(font_path, 44)
    f_big = ImageFont.truetype(font_path, 34)
    f_body = ImageFont.truetype(font_path, 27)
    f_small = ImageFont.truetype(font_path, 21)
    f_tiny = ImageFont.truetype(font_path, 18)
    f_seal = ImageFont.truetype(font_path, 16)
    f_quote = ImageFont.truetype(font_path, SAGE_QUOTE_SIZE)
    f_copy = ImageFont.truetype(font_path, SAGE_COPY_SIZE)
    callo_path = find_calligraphy_font()
    f_call = ImageFont.truetype(callo_path or font_path, SAGE_CALLO_SIZE)

    pad = 60

    # ---- A 顶栏（与原版一致）----
    y = 78
    d.text((pad, y), data.get("store", ""), font=f_small, fill=MUTED)
    tr = data.get("timeText", "") + "  " + data.get("date", "")
    d.text((WIDTH - pad - d.textlength(tr, font=f_small), y), tr, font=f_small, fill=MUTED)

    # ---- B 标题区（与原版一致）----
    y = 130
    mood = data.get("mood", "")
    title = "下班仪式感" + ("·" + mood if mood else "")
    d.text((pad, y), title, font=f_title, fill=INK)
    d.line((pad, 200, WIDTH - pad, 200), fill=(210, 205, 196), width=2)

    sage = data.get("sage") or {}

    # ---- C 先贤区：插画 + 圆角蒙版 + 烫金描边 ----
    bx, by = SAGE_BAND_XY
    bw, bh = SAGE_BAND_WH
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw, bh), radius=SAGE_BAND_RADIUS, fill=255)
    if illustration.mode == "RGBA":
        # 插画自带透明通道时，与圆角蒙版求交，两者都尊重
        mask = ImageChops.multiply(mask, illustration.getchannel("A"))
    img.paste(illustration, (bx, by), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=SAGE_BAND_RADIUS,
                        outline=GOLD, width=2)
    d.rounded_rectangle((bx + 3, by + 3, bx + bw - 3, by + bh - 3), radius=SAGE_BAND_RADIUS - 3,
                        outline=(227, 221, 208), width=1)

    # 书法题词（典籍引文）：半透明宣纸底衬 + 行楷，压在插画顶部预留留白区
    classic = sage.get("classic", "")
    if classic:
        clo_lines = wrap(classic, d, f_call, bw - 48)[:2]
        line_h = 46
        wmax = max(d.textlength(l, font=f_call) for l in clo_lines)
        box = (bx + 24 - 14, by + 20 - 8,
               bx + 24 + wmax + 14, by + 20 + line_h * len(clo_lines) + 8)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rounded_rectangle(box, radius=10, fill=PAPER + (179,))
        img.alpha_composite(overlay)
        d = ImageDraw.Draw(img)
        cy = by + 20
        for ln in clo_lines:
            d.text((bx + 24, cy), ln, font=f_call, fill=INK)
            cy += line_h

    # 落款 + 朱文印章（左下预留素地）
    name = sage.get("name", "")
    source = sage.get("source", "")
    sign = "——%s%s" % (name, source)
    if sign != "——":
        d.text((bx + 24, by + bh - 42), sign, font=f_tiny, fill=INK)
        seal_char = str(sage.get("seal", "") or (name[:1] if name else ""))
        if seal_char:
            sx = bx + 24 + d.textlength(sign, font=f_tiny) + 10
            sy = by + bh - 46
            d.rounded_rectangle((sx, sy, sx + SAGE_SEAL_SIZE, sy + SAGE_SEAL_SIZE),
                                radius=5, fill=RED)
            tw = d.textlength(seal_char, font=f_seal)
            d.text((sx + (SAGE_SEAL_SIZE - tw) / 2, sy + 3), seal_char,
                   font=f_seal, fill=PAPER)

    # ---- D 贴心话区（34pt 麦金，全卡内容区最大字号，≤2 行）----
    y = 536
    quote = sage.get("quote", "")
    q_lines = wrap("「" + quote + "」", d, f_quote, WIDTH - pad * 2)[:2] if quote else []
    for ln in q_lines:
        d.text((pad, y), ln, font=f_quote, fill=GOLD)
        y += 48
    y += 14

    # ---- E 文案卡（24pt，≤3 行，超出末行加「…」）----
    copy = data.get("copy", "")
    copy_lines = wrap(copy, d, f_copy, WIDTH - pad * 2 - 56)
    if len(copy_lines) > 3:
        copy_lines = copy_lines[:3]
        copy_lines[-1] = copy_lines[-1][:-1] + "…" if len(copy_lines[-1]) > 1 else "…"
    box_h = 24 + len(copy_lines) * 42 + 20
    d.rounded_rectangle((pad, y, WIDTH - pad, y + box_h), radius=18, fill=CARD,
                        outline=(225, 220, 210), width=2)
    cy = y + 24
    for ln in copy_lines:
        d.text((pad + 28, cy), ln, font=f_copy, fill=INK)
        cy += 42
    y += box_h + 18

    # ---- F 餐单区（单行 40px：名称左，价格+热量右；溢出截断）----
    d.text((pad, y), "今晚这一餐", font=f_small, fill=GOLD)
    y += 32
    for it in data.get("items", []):
        if y + 40 > 936:                        # G 合计区预留，超出截断
            d.text((pad, y), "…", font=f_body, fill=MUTED)
            y += 36
            break
        name_i = it.get("name", "")
        d.text((pad, y), name_i, font=f_body, fill=INK)
        price = "%s 元" % it.get("price", "")
        kcal = "约 %s kcal" % it.get("kcal", "-")
        pw = d.textlength(price, font=f_body)
        kw = d.textlength(kcal, font=f_tiny)
        d.text((WIDTH - pad - pw, y), price, font=f_body, fill=INK)
        d.text((WIDTH - pad - pw - kw - 10, y + 6), kcal, font=f_tiny, fill=MUTED)
        y += 40
    y += 8

    # ---- G 合计区 ----
    d.line((pad, y, WIDTH - pad, y), fill=(210, 205, 196), width=2)
    y += 22
    d.text((pad, y), "合计", font=f_body, fill=INK)
    total = "%s 元" % data.get("total", "-")
    d.text((WIDTH - pad - d.textlength(total, font=f_big), y - 6), total, font=f_big, fill=RED)
    y += 48

    # ---- H 页脚区（note 仅显示放得下的行；右界避让券码预留区；生成说明固定贴底）----
    note = data.get("note", "")
    for ln in wrap(note, d, f_tiny, SAGE_FOOTER_RIGHT - pad):
        if y + 26 > 1042:
            break
        d.text((pad, y), ln, font=f_tiny, fill=MUTED)
        y += 26
    d.text((pad, HEIGHT - 30), "本卡片由 WorkBuddy + 麦当劳官方 MCP 生成",
           font=f_tiny, fill=MUTED)

    img.convert("RGB").save(out_path)
    return out_path


def render_md(data, out_path):
    lines = []
    lines.append("# 下班仪式感 · %s\n" % data.get("date", ""))
    lines.append("> %s · %s\n" % (data.get("store", ""), data.get("timeText", "")))
    lines.append("\n%s\n" % data.get("copy", ""))
    # 新增（附加式）：有 sage 时在文案下插先贤块；无 sage 时与原来逐字一致
    sage = data.get("sage") or {}
    if sage.get("quote") or sage.get("classic"):
        who = sage.get("name", "")
        if sage.get("source"):
            who += sage["source"]
        lines.append("\n> 「%s」%s\n" % (sage.get("quote", ""), ("—— " + who) if who else ""))
        if sage.get("classic"):
            lines.append("> %s\n" % sage.get("classic", ""))
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

    base = project_root()
    outdir = os.path.join(base, "output")
    os.makedirs(outdir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # 先贤文案硬校验（00 纪要 §10）：不通过则拒绝渲染该卡，输出告警，不出文件
    warnings = validate_sage_copy(data, base)
    if warnings:
        print(json.dumps({"ok": False, "path": None, "format": None,
                          "illustration": False,
                          "error": "先贤文案校验未通过，已拒绝渲染（严禁截断，请修文案）",
                          "warnings": warnings}, ensure_ascii=False))
        sys.exit(2)

    font_path = find_font()
    used_illustration = False
    try:
        if not font_path:
            raise RuntimeError("未找到中文字体")
        out = os.path.join(outdir, "ritual_card_%s.png" % stamp)
        # 先解析插画：找不到文件 / 加载失败都在 render_png 内部降级为纯文字卡片
        illustration_path = resolve_sage_illustration(data, base)
        render_png(data, out, font_path, illustration_path=illustration_path)
        used_illustration = illustration_path is not None
        kind = "PNG"
    except Exception as e:
        out = os.path.join(outdir, "ritual_card_%s.md" % stamp)
        render_md(data, out)
        kind = "Markdown（降级，原因：%s）" % e

    print(json.dumps({"ok": True, "path": out, "format": kind,
                      "illustration": used_illustration}, ensure_ascii=False))


if __name__ == "__main__":
    main()
