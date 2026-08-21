---
name: tg-group-summary
description: "总结 Telegram 群聊消息时生成可核验的主题档案式折叠报告。"
version: 13.0.0
author: Hermes Agent
---

# Telegram 群聊折叠总结｜原生 Details 独立折叠规范

## 一、核心折叠容器标准（绝不动摇）

群聊总结**必须且只能使用 Telegram 原生 Rich Message 的 `<details><summary>` 独立块**！
- 每个主题各自独立包裹为一个 `<details>` 块；
- 标题写在 `<summary>` 中；
- 严禁使用 `<blockquote expandable>`、`**>`、`>`、`||` 或纯文本裸露！

---

## 二、单主题 10 模块固定结构

每个独立主题必须完整包含以下 10 个模块，严格依序展开：

```html
<details>
<summary>主题一｜具体事件名称</summary>

<b>分类：</b> AI工具与监控
<b>重要程度：</b> 高
<b>时间范围：</b> 2026-08-21 12:22 ~ 12:41

<b>核心结论</b>
一整段流畅连贯的总结长句，交代事件起因、发展脉络、核心分歧与最终现状。

<b>事件时间线</b>
◦ 12:22｜<b>林弈浅（红猫_夺舍版）✨:</b> 发起首轮测试。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
◦ 12:26｜<b>玛卡巴卡白推车:</b> 解释相关机制。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
◦ 当前：事件推进现状。[来源](https://t.me/c/{chat_id去-100}/{msg_id})

<b>参与方及具体发言</b>
◦ <b>林弈浅（红猫_夺舍版）✨:</b> 具体观点、行动或反馈。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
◦ <b>如昔：</b> 关注指标与下达指令。[来源](https://t.me/c/{chat_id去-100}/{msg_id})

<b>已确认事实</b>
◦ 消息中能直接证实的数据、配置、功能或处理结果。[来源](https://t.me/c/{chat_id去-100}/{msg_id})

<b>未确认事项与争议</b>
◦ 证据不足、尚无实测或存在分歧的内容。[来源](https://t.me/c/{chat_id去-100}/{msg_id})

<b>当前进展</b>
◦ 仅描述已经发生的结果，不把计划当完成。[来源](https://t.me/c/{chat_id去-100}/{msg_id})

<b>影响评估</b>
◦ 对服务稳定性、成本、用户体验或后续决策的实际影响。[来源](https://t.me/c/{chat_id去-100}/{msg_id})

<b>负责人</b>
◦ 仅在消息明确指定时写具体人；否则写“历史消息未明确负责人”。

<b>待办清单</b>
◦ 聊天中实际提出的后续测试或待跟进操作。[来源](https://t.me/c/{chat_id去-100}/{msg_id})
</details>
```

---

## 三、整体报告输出模板

```html
📊 {群聊名称} 群聊总结 — {时间范围}

<details>
<summary>主题一｜事件名称一</summary>
...
</details>

<details>
<summary>主题二｜事件名称二</summary>
...
</details>

<details>
<summary>📋 总体结论与行动</summary>

• 归纳跨主题核心结论与明确待办事项。
</details>
```
