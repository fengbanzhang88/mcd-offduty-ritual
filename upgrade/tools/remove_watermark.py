#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
去平台水印工具（先贤插画资产生成管线）

背景：ImageGen（混元）出图会在右下角叠加半透明「AI生成 WORKBUDDY>」水印，
本工具用「上下文模板匹配 + 羽化融合」把水印区补回与原画面一致的纸纹/内容，
不引入任何新元素，不改变画布尺寸。

用法：
    python remove_watermark.py <图片路径> [图片路径 ...]

原理：
    1. 水印区按经验值取右下角矩形 W = (w-260, h-70) ~ (w-3, h-3)；
    2. 以 W 左侧 60px 干净内容为「上文」，在图中向左搜索偏移 d，
       取「距 W 左侧 d 处的同尺寸补丁」中与上文最接近的一块；
    3. 用左羽化 18px 的软蒙版把补丁贴回 W，边缘融进原画面。
"""

import sys
import os

# 经验水印区（相对右下角）
WM_W = 260
WM_H = 70
WM_MARGIN = 3
# 搜索参数
CTX = 60          # 上文宽度
MAX_SHIFT = 560   # 最大向左搜索距离
FEATHER = 18      # 左羽化宽度


def _rms(diff_image, box):
    """计算 box 区域的 RMS 差异（0 = 完全一致）。"""
    from PIL import ImageStat
    region = diff_image.crop(box)
    return ImageStat.Stat(region).rms[0] if region.getbbox() else 0.0


def remove_watermark(path, verbose=True):
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    img = Image.open(path).convert("RGB")
    w, h = img.size
    x1, y1 = w - WM_MARGIN, h - WM_MARGIN
    x0, y0 = x1 - WM_W, y1 - WM_H
    if x0 < 0 or y0 < 0:
        if verbose:
            print("  [skip] %s 尺寸过小，无水印处理" % path)
        return False

    # 上文：水印区左侧 CTX 宽的干净内容
    ctx_box = (x0 - CTX, y0, x0, y1)
    if ctx_box[0] < 0:
        ctx_box = (0, y0, CTX, y1)

    # 搜索最佳偏移：补丁左缘应与上文衔接自然
    best_d, best_score = None, None
    d = CTX + 10
    while d <= MAX_SHIFT and x0 - d >= 0:
        cand = img.crop((x0 - d, y0, x1 - d, y1))
        # 补丁最左 CTX 列 vs 上文
        diff = ImageChops.difference(cand.crop((0, 0, CTX, y1 - y0)),
                                     img.crop(ctx_box))
        score = _rms(diff, (0, 0, CTX, y1 - y0))
        if best_score is None or score < best_score:
            best_d, best_score = d, score
        d += 10

    if best_d is None:
        if verbose:
            print("  [skip] %s 搜索空间不足" % path)
        return False

    # 取补丁并做左羽化软贴回
    patch = img.crop((x0 - best_d, y0, x1 - best_d, y1))
    mask = Image.new("L", patch.size, 255)
    md = ImageDraw.Draw(mask)
    for i in range(FEATHER):
        alpha = int(255 * (i / FEATHER))
        md.line((i, 0, i, patch.size[1]), fill=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(2))
    img.paste(patch, (x0, y0), mask)

    img.save(path)
    if verbose:
        print("  [done] %s  偏移=%d  上文RMS=%.1f" % (os.path.basename(path), best_d, best_score))
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    ok = 0
    for p in sys.argv[1:]:
        if os.path.isfile(p):
            if remove_watermark(p):
                ok += 1
        else:
            print("  [miss] %s 不存在" % p)
    print("处理完成：%d/%d" % (ok, len(sys.argv) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
