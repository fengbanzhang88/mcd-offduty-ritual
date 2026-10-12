#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
先贤匹配器（「时空饭搭子」第 3 步用）

用法：
    python scripts/match_sage.py "用户原话" 小时
    例：python scripts/match_sage.py "加班到现在，快累死了" 23

输入：
    参数 1：用户下班原话（字符串）
    参数 2：当前小时 0–23（来自第 2 步 now-time-info；缺省取本机时间）
输出：
    stdout 打印 JSON：
    - 正常：{"id","scene","name","quote","classic","source","seal","intro"}
            直接拼进卡片 JSON 的 "sage" 字段（插画路径由卡片脚本按 id 推断）
    - 命中敏感词：{"crisis": true, "care": "..."} —— 不上先贤，改走关怀语

数据源：references/sage_match.json（12 场景匹配表，内容创作官维护，改表即生效）
典籍引文/出处/印章字：SAGE_META（口径 = upgrade/prompts/sage_index.json v2.0，
        改题词须三处同步：本表 / sage_index.json / 01_场景先贤匹配表.md）
纯标准库实现，零依赖；匹配全程本地完成，用户原话不上传。
"""

import json
import os
import sys
import datetime

# 典籍引文、出处、印章字（按先贤 id）
# 口径已与 upgrade/prompts/sage_index.json v2.0 / 01_场景先贤匹配表.md §1 的
# 「为什么是他」对齐（2026-10-13 由团长裁定统一）。改题词必须三处同步：
#   ① 本 SAGE_META  ② upgrade/prompts/sage_index.json  ③ 01_场景先贤匹配表.md
SAGE_META = {
    "zengguofan": {"name": "曾国藩", "classic": "人而无恒，终身一无所成", "source": "《曾国藩家书》", "seal": "曾"},
    "mengzi":      {"name": "孟子",   "classic": "我善养吾浩然之气",     "source": "《孟子·公孙丑上》", "seal": "孟"},
    "taoyuanming": {"name": "陶渊明", "classic": "复得返自然",           "source": "《归去来兮辞》",     "seal": "陶"},
    "sushi":       {"name": "苏轼",   "classic": "人间有味是清欢",       "source": "《浣溪沙·细雨斜风作晓寒》", "seal": "苏"},
    "wangyangming": {"name": "王阳明", "classic": "人须在事上磨练",     "source": "《传习录》",         "seal": "王"},
    "kongzi":      {"name": "孔子",   "classic": "不患人之不己知，患不知人也", "source": "《论语·学而》", "seal": "孔"},
    "sunzi":       {"name": "孙子",   "classic": "主不可以怒而兴师，将不可以愠而致战", "source": "《孙子兵法·火攻篇》", "seal": "孙"},
    "laozi":       {"name": "老子",   "classic": "孰能安以久动之而徐生", "source": "《道德经·第十五章》", "seal": "老"},
    "zhuangzi":    {"name": "庄子",   "classic": "以无厚入有间，游刃有余", "source": "《庄子·养生主》", "seal": "庄"},
}

CRISIS_CARE = ("听起来你现在真的很累。先别急着吃什么，照顾好自己。如果你愿意，"
               "全国统一心理援助热线 12356，24 小时有人接听，免费。我在这儿，不急。")


def project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_table(root=None):
    path = os.path.join(root or project_root(), "references", "sage_match.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def contains_any(text, words):
    return any(w in text for w in words)


def match_sage(user_text, hour, table=None):
    """按 01 号文档算法匹配：情绪词 ×2 + 关键词 ×1。

    工程规则（2026-10-13 团长裁定）：
    1) 长度 <2 的词一律不计分——中文单字必然是其他词的子串
       （"气"会命中"天气"、"烦"会命中"麻烦"），单字不参与匹配。
       内容侧补词必须补多字词（好累/累死/生气/被毙/功劳）。
    2) **计分阶段不做深夜时段加成**。深夜优先由第 5 步 fallback 承担
       （全 0 分时深夜归 S01），避免 +2 加成把明确命中 S12 等场景的
       用户错分给 S01。原 time_boost 设计已废弃。
    """
    table = table or load_table()
    scenarios = table["scenarios"]

    # 0. 安全闸：命中敏感词 → 不走先贤功能
    if contains_any(user_text, table.get("sensitive_words", [])):
        return {"crisis": True, "care": CRISIS_CARE}

    # 1-3. 计分（单字词不计分，见 docstring 规则 1）
    scores = {}
    for s in scenarios:
        score = sum(2 for w in s.get("emotion_words", []) if len(w) >= 2 and w in user_text)
        score += sum(1 for w in s.get("keywords", []) if len(w) >= 2 and w in user_text)
        scores[s["id"]] = score

    # 4. 取最高分；同分取表中靠前者（表已按优先级排序）
    best = max(scores, key=scores.get)

    # 5. 兜底：全部 0 分 → 深夜 S01，其余 S04
    if scores[best] == 0:
        fb = table.get("fallback", {})
        best = fb.get("late_night", "S01") if (hour >= 22 or hour < 5) else fb.get("default", "S04")

    # 6. 组装输出
    sc = next(s for s in scenarios if s["id"] == best)
    meta = SAGE_META.get(sc["sage_id"], {})
    return {
        "id": sc["sage_id"],
        "scene": sc["id"],
        "name": meta.get("name", sc["sage_id"]),
        "quote": sc["quote"],
        "classic": meta.get("classic", ""),
        "source": meta.get("source", ""),
        "seal": meta.get("seal", ""),
        "intro": sc.get("intro", ""),
    }


def main():
    if len(sys.argv) < 2:
        print("用法：python scripts/match_sage.py \"用户原话\" [小时0-23]", file=sys.stderr)
        sys.exit(2)
    user_text = sys.argv[1]
    if len(sys.argv) > 2:
        hour = int(sys.argv[2])
    else:
        hour = datetime.datetime.now().hour
    print(json.dumps(match_sage(user_text, hour), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
