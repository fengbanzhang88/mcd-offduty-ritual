# 麦当劳 MCP 工具速查与使用纪律

配置方式（WorkBuddy 连接器）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_MCP_TOKEN" }
    }
  }
}
```

Token 申请：https://open.mcd.cn/mcp → 手机号登录 → 控制台 → 激活 → 复制

---

## 本 Skill 用到的工具（8 个）

| 工具 | 作用 | 关键入参 | 注意 |
|---|---|---|---|
| `now-time-info` | 当前真实时间 | 无 | 用来判断餐段 |
| `query-nearby-stores` | 找可点餐门店 | `beType`(1 到店 / 5 得来速)、`searchType`(2 按位置)、`city`、`keyword` | 必须把 `storeCode` 完整展示给用户选 |
| `query-meals` | 真实在售菜单 + 价格 | `storeCode`、`orderType`(1 到店 / 2 外送)、`beType` | 外送/团餐需 `beCode` |
| `list-nutrition-foods` | 真实营养 | 无 | 返回约 160 项 |
| `calculate-price` | 真实总价（含优惠） | `storeCode`、`orderType`、`beType`、`items[]` | **返回单位为「分」，展示要 ÷100** |
| `campaign-calendar` | 当月营销活动 | `specifiedDate` 可选 | 用来给文案加时效感 |
| `available-coupons` | 可领券列表 | 无 | **只展示，不代领** |
| `auto-bind-coupons` | 一键领券 | 无 | **必须用户明确说"领"才调用** |
| `query-lottery-info` | 抽奖信息/奖品 | 无 | 展示 `drawDecision.nextConsumption` |
| `draw-lottery` | 抽奖 | 无 | **必须用户明确说"抽"才调用** |

---

## 参数传递铁律

- 到店自取：`beType=1`、`orderType=1`、**不传** `beCode`
- 得来速：`beType=5`、`orderType=1`、**必须传** `beCode`
- 麦乐送：`beType=2`、`orderType=2`、**必须传** `beCode`
- 企业团餐：`beType=6`、`orderType=2`、**必须传** `beCode`

`beCode` 从 `query-nearby-stores` 或 `delivery-query-stores` 的返回结果里取。

---

## 使用纪律（硬性）

1. **确认制**：领券、抽奖、下单前，必须先把内容展示给用户，得到明确同意后执行。
2. **不主动下单**：`create-order` 只在用户明确要求且已确认价格后调用。
3. **不回显 Token**：任何输出、日志、文件中都不得出现真实 Token。
4. **金额单位**：`calculate-price` 返回「分」，展示前除以 100。
5. **不编造**：菜单、价格、营养、券一律以接口实时返回为准。
6. **门店必展示**：`storeCode` / `beCode` 必须完整展示，不能省略。

---

## 实测记录（2026-10-12，阳泉）

- `query-nearby-stores`（阳泉）返回 2 家店：
  - 麦当劳阳泉万达餐厅 `1950674`（09:00–23:00）
  - 麦当劳阳泉桃北餐厅 `1950140`（**00:00–23:59，24 小时店**）
- `query-meals`（1950140，到店）返回完整菜单与真实价格
- `list-nutrition-foods` 返回 160 项营养数据
- `campaign-calendar` 返回 10 月全部活动
- `query-lottery-info`：单次 24 积分，奖品含立减券与折扣券
