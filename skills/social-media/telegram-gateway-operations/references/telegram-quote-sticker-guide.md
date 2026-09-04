# Telegram Q 版引用贴纸 (Quote Sticker) 完整实现与避坑指南

## 1. 业务流程与架构

```text
[群聊] 用户回复消息发送 "q" (或 "q 自定义文字")
   │
   ▼
[Hermes 网关拦截] 提取被回复消息的 text/caption、发送者 user_id 与群名
   │
   ▼
[私聊推送确认] 向发 q 用户私聊推送待生成文字预览 + [✅确认生成] [❌取消] 按钮
   │ (用户可在私聊发送 "q 新文字" 实时修改)
   ▼
[点击确认] 网关通过 get_user_profile_photos 获取作者真实头像 URL
   │
   ▼
[本地 quote-api (4888)] 生成纯净透明背景 WebP 贴纸 ("type": "quote")
   │
   ▼
[发回群聊] send_sticker 贴纸发回群聊被回复位置，自动删除群内原始 "q" 与私聊面板
   │
   ▼
[60秒超时清扫] 超过 60 秒无动作自动取消并清理消息
```

## 2. 关键技术配置与避坑

### ① 私聊确认消息必须使用 `ParseMode.HTML`
* **原因**：群友 Telegram 昵称及原消息中常带有 `_`、`*`、`[`、`]` 等字符，Markdown 解析会抛出 `Can't parse entities` 异常，导致私聊推送失败，网关会误判用户未发起过私聊。
* **写法**：使用 `<b>`、`<code>` 格式化，完全规避特殊字符报错。

### ② 管理员身份、自定义头衔与 Telegram 会员小表情 (Custom Emoji) 识别
* **触发机制守则**：严格遵循用户原始习惯，保持群内回复发送纯字母 `q`（或 `q 自定义内容`）触发，禁止随意更改为 `/q`。
* **身份与头衔识别 (`senderTag`)**：
  - 拦截回复消息时，优先提取 `sender_chat`（频道为 `频道`）或 `author_signature` / 真实群成员 `custom_title`；群主若无专属头衔默认显示 `群主`，管理员默认显示 `管理员`。
  - 将 `senderTag` 注入消息体传给 `quote-api`，贴纸右上角将自动渲染出身份标签胶囊。
* **会员动态/静态小表情支持 (`custom_emoji`)**：
  - 被回复消息中若含有 Telegram Premium 自定义表情，从 `msg.entities` / `msg.caption_entities` 提取 `type == "custom_emoji"` 实体及 `custom_emoji_id`，并存入待处理结构。
  - 请求 `quote-api` 时，必须附带 `botToken` 并在消息体中传入 `entities` 数组，由 `quote-api` 内部自动调用 `getCustomEmojiStickers` 下载并高清渲染会员表情。

### ③ 本地渲染 `quote-api` 配置
* **端口**：`4888`
* **请求体**：
  ```json
  {\n    \"botToken\": \"123456:ABC-DEF...\",\n    \"backgroundColor\": \"#FFFFFF\",\n    \"type\": \"quote\",\n    \"messages\": [{\n      \"text\": \"文字内容\",\n      \"from\": {\n        \"id\": 12345678,\n        \"name\": \"用户昵称\",\n        \"photo\": { \"url\": \"https://api.telegram.org/file/bot...\" }\n      },\n      \"avatar\": true,\n      \"senderTag\": \"群主\",\n      \"entities\": [\n        { \"type\": \"custom_emoji\", \"offset\": 0, \"length\": 2, \"custom_emoji_id\": \"5368324170671202286\" }\n      ]\n    }]\n  }
  ```
* **注意**：`type: \"quote\"` 产生无壁纸、无多余黑边的纯净透明气泡；`type: \"image\"` 会带上 Telegram 蓝色壁纸矩形底图。

### ④ 真实头像获取
通过 `get_user_profile_photos(user_id, limit=1)` 获取大图 `file_id`，再通过 `get_file` 换取真实下载路径传给 `quote-api`，防止退化为名字首字母占位符。
