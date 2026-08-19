---
name: tg-group-summary
description: "总结 Telegram 群聊消息时用它查询消息数据库并生成高信息密度中文报告。"
version: 6.0.0
author: Hermes Agent
---

# Telegram 群聊消息监听与总结（深度干货版）

## 总结核心准则：高信息密度、拒绝偷懒一笔带过

总结群聊时，必须具备**充分的深度与信息量**：
1. **多话题细分**：根据讨论内容，提炼出 3~6 个细分话题，不把所有事情揉成一两个泛泛的大块。
2. **要点充实（每个话题 3~6 条）**：
   - 必须包含**具体技术参数、服务器配置、商家/产品名称、价格、测试结果、报错原因、解决方案**；
   - 还原关键人物的观点、态度与有价值的交流互动；
   - 严禁只写“讨论了某事”等空话套话，必须写清楚“具体讨论了什么、结论是什么”。
3. **精准溯源**：每一条重要事实末尾均附带对应消息的 `[来源](https://t.me/c/...)` 链接。
4. **指令识别**：
   - 指令含 `Nh` / `某某h`（如 2h, 3h, 24h）代表查询最近 N 小时（`--hours N`）；
   - 指令含 `N条` 代表查询最近 N 条（`--count N`）；
   - 指令指定群名时，精确定向查询该群。

## 输出格式（绝对死规则，严禁违背）

必须全量输出原生 HTML `<details>` 折叠结构，严禁输出任何 `**>`、`>`、`||` 或裸文本！

### 完整标准模板：

```html
📊 {群聊名称} 群聊总结 — {时间范围}

<details>
<summary>emoji 话题名称一</summary>

• 事实描述要点一（包含具体参数/方案/人物观点）。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
• 事实描述要点二（包含踩坑细节/解决办法）。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
• 事实描述要点三。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
</details>

<details>
<summary>emoji 话题名称二</summary>

• 事实描述要点一。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
• 事实描述要点二。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
</details>

<details>
<summary>其他零散</summary>

• 零散信息记录一。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
• 零散信息记录二。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
</details>

<details>
<summary>📋 结论与行动</summary>

• 归纳核心结论、群内达成的共识及后续待办事项。
</details>
```
