# Telegram 原生 Rich Message 折叠总结规范与排障指南

## 1. 为什么必须使用 `<details><summary>` 原生富文本？
在 Telegram Bot API 10.1+ 体系中，要在 Telegram 客户端呈现带灰色引用线及原生下拉折叠箭头（`∨` / `⌃`）的独立折叠块容器，必须使用 HTML `<details><summary>` 标签结构：

```html
📊 近50条群聊总结（时间范围，共50条）

<details>
<summary>🤖 话题标题一</summary>

• 事实描述要点一。[来源](https://t.me/c/4495899387/104873) [来源](https://t.me/c/4495899387/104876)
• 事实描述要点二。[来源](https://t.me/c/4495899387/104881)
</details>

<details>
<summary>⚙️ 话题标题二</summary>

• 事实描述要点。[来源](https://t.me/c/4495899387/104884)
</details>

<details>
<summary>最终总结</summary>

• 全局主线归纳与总结。
</details>
```

---

## 2. 严禁混用的错误语法与避坑陷阱
- ❌ **严禁使用 `||` 闭合符**：`||` 在 Telegram 语义中仅代表局部文字剧透涂层（Spoiler），会导致排版平铺展开并在末尾裸露 `||` 字符。
- ❌ **严禁使用 `**>` 或 `>`**：这种旧式引用前缀容易在多行中文或特殊标点时导致 MarkdownV2 解析器转义失败。
- ❌ **严禁省略 `[来源]` 链接**：每条事实后方必须附带真实 Telegram 消息超链接，格式固定为 `[来源](https://t.me/c/{chat_id去-100}/{msg_id})`。

---

## 3. 网关底层分发要点
1. **CJK 放行**：必须开启 `platforms.telegram.extra.rich_messages: true` 与 `platforms.telegram.extra.rich_messages_allow_cjk: true`，并在网关适配器中放行中文 CJK 检查，防止自动降级为纯文本。
2. **完整下发**：长篇总结必须在后台组织完毕后直接通过 `sendRichMessage` (`rich_message: {markdown: text}`) 单次完整下发，严禁通过流式切片编辑导致标签被截断破坏。
