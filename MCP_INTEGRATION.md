# MCP 集成说明

本 Skill 基于**麦当劳中国官方 MCP Server**（`mcd-mcp`）开发，共编排 **8 个**原子工具形成业务闭环。

---

## 一、使用的 Server 与 Tool

**Server**：麦当劳中国 MCP Server
- 类型：`streamablehttp`
- 地址：`https://mcp.mcd.cn`
- 鉴权：`Authorization: Bearer <MCP Token>`（Token 由 https://open.mcd.cn/mcp 申请）
- 工具总数：35（本 Skill 编排其中 8 个）

| # | Tool | 类型 | 在本项目中的作用 | 是否必用 |
|---|---|---|---|---|
| 1 | `now-time-info` | 只读 | 取当前真实时间，判断餐段（早/午/下午茶/夜市/宵夜） | 必用 |
| 2 | `query-nearby-stores` | 只读 | 查可点餐门店，识别 24 小时店，拿 `storeCode` | 必用 |
| 3 | `query-meals` | 只读 | 取真实在售菜单与价格 | 必用 |
| 4 | `list-nutrition-foods` | 只读 | 取真实营养（热量/蛋白/脂肪/钠/钙） | 必用 |
| 5 | `calculate-price` | 只读 | 计算含优惠的真实总价 | 必用 |
| 6 | `campaign-calendar` | 只读 | 取当月营销活动，给文案加时效感 | 可选 |
| 7 | `available-coupons` | 只读 | 展示用户可领券 | 确认制 |
| 8 | `auto-bind-coupons` | **写入** | 一键领券（用户确认后） | 确认制 |

> 另有 `query-lottery-info` / `draw-lottery`（积分抽奖彩蛋，确认制）、
> `delivery-query-stores`（外送场景）、`calculate-price` 用于真实结算。

---

## 二、调用流程图

```
用户说："下班了，今天好累"
        │
        ▼
[0] 接住情绪（LLM，无工具）——复述状态，问清时段与调性
        │
        ▼
[1] now-time-info ───────────► 取真实时间 → 判断餐段
        │
        ▼
[2] query-nearby-stores ─────► 找门店（深夜优先 24h 店）→ 用户选 storeCode
        │
        ▼
[3] query-meals ─────────────► 取真实在售菜单 + 价格
        │
        ├──► list-nutrition-foods ──► 取真实营养 → 按调性筛选（犒劳/清淡/提神/夜归）
        │
        ▼
[4] calculate-price ─────────► 算含优惠的真实总价（单位：分 → 元）
        │
        ▼
[5] 渲染卡片 scripts/generate_ritual_card.py ──► output/*.png（750×1080）
        │
        ▼
[6] 展示 available-coupons ──► 用户说"领" ──► auto-bind-coupons（确认制）
        │
        └──► query-lottery-info ──► 用户说"抽" ──► draw-lottery（确认制）
```

---

## 三、参数传递关键点

- 到店自取：`beType=1`、`orderType=1`、**不传** `beCode`
- 得来速：`beType=5`、`orderType=1`、**必传** `beCode`
- 麦乐送：`beType=2`、`orderType=2`、**必传** `beCode`
- 企业团餐：`beType=6`、`orderType=2`、**必传** `beCode`
- `calculate-price` 返回金额单位为**分**，展示前须 ÷100

---

## 四、业务价值

1. **对用户**：把"下班吃啥"这个每天发生的小决策，变成一次有温度的仪式；
2. **对 McDonald's**：
   - 真实菜单/营养接口 → 提升点单转化与客单；
   - `available-coupons` → `auto-bind-coupons` 闭环，把"看得见的优惠"变成"领到手的券"，直接促单；
   - 24h 门店优先 → 拉高深夜时段订单；
   - 情绪文案 → 天然的社交传播，降低获客成本；
3. **对生态**：给出一个"情绪价值 + 真实数据"的 Skill 范式，可复用到其他品牌 MCP。

---

## 五、安全与合规

- 领券、抽奖、下单**均为确认制**，先展示、用户同意才执行；
- **不主动下单**，不调用支付；
- 关键写入操作（`auto-bind-coupons` / `draw-lottery`）前必须展示服务端
  `drawDecision.nextConsumption` 等消耗信息；
- 全仓库不含真实 Token / 密钥（配置示例仅用 `YOUR_MCP_TOKEN` 占位）；
- 营养数据仅供参考，不构成医疗或营养建议。
