# upgrade/illustrations —— 先贤插画交付目录（运行目录）

> 「时空饭搭子」插画落地处（位置与命名依据 `00_团长拍板对齐纪要` §3）。
> 插画设计师定稿后，把 PNG 放进本目录即可被 `scripts/generate_ritual_card.py`
> 自动发现，**无需改任何代码**。完整规范见 `03_技术落地方案.md` 第 3 节。

## 文件命名

```
sage_<先贤id>.png        一位先贤一张通用形象，跨场景 12 场景复用
```

先贤 id（9 位）：`zengguofan` `mengzi` `taoyuanming` `sushi` `wangyangming`
`kongzi` `sunzi` `laozi` `zhuangzi`

例：`sage_zengguofan.png`、`sage_sushi.png`

## 交付规格

- 尺寸 **1260×600**（2×，21:10 横幅），PNG
- 顶部 15%、左下 12% 留素净区（题词/落款位），人物主体偏右
- 原创扁平国风、先贤不画正脸、画面内无任何文字/商标/水印
- 完整规范以 `02_插画体系与生图prompt.md` + `upgrade/prompts/sage_index.json` 为准

## 缺失时的行为（自动降级，不会报错）

文件不存在 → 卡片退回原版纯文字版式（字节级一致），stdout JSON 里
`"illustration": false`；Pillow 缺失 → 降级 `.md` 文本卡片（贴心话以文字保留）。
