# Telegram Q 图贴纸生成机制 (Quote Sticker Pipeline)

## 1. 业务流程与交互机制

在 Telegram 机器人平台实现“群聊回复 `q` 生成 Q 版引用贴纸”功能，包含以下核心链路：

1. **群聊拦截 (`q` 触发)**：
   - 监听群聊消息，当用户**回复某条消息**并发送 `q`（或 `q 自定义文字`）时，拦截该消息，不进入 LLM 对话管道。
   - 读取被回复消息的文本内容（text/caption），提取被回复用户的 `user_id` 与昵称。
   - 若被回复消息无文字（纯图片/贴纸/文件/语音），允许文字为空并引导用户在私聊输入。

2. **私聊确认面板 (`Inline Keyboard`)**：
   - 机器人向发起人发送私聊消息（DM），展示待生成的文字预览及原作者昵称。
   - 附带两个 Inline Button：`✅ 确认生成` (`callback_data: quote_confirm`) 和 `❌ 取消` (`callback_data: quote_cancel`)。
   - **关键避坑**：私聊消息必须使用 `ParseMode.HTML` 发送，严禁使用 `Markdown`。因为用户昵称和文字常含有 `_`、`*`、`[` 等特殊字符，Markdown 解析失败会导致 `Can't parse entities` 异常，进而误判为“用户未私聊 /start”。

3. **私聊动态改字**：
   - 用户在私聊直接发送 `q 新文字`，自动更新 pending 中的文字并用 `edit_message_text` 刷新私聊确认面板。

4. **真实头像抓取与渲染 (quote-api)**：
   - 确认生成时，调用 Telegram Bot API 的 `get_user_profile_photos(user_id, limit=1)` 获取用户最新头像的 `file_id`，再通过 `get_file` 获得真实下载 URL（`https://api.telegram.org/file/bot<token>/...`）。
   - 将文字、作者名及头像 URL 提交给本地 `quote-api`（`POST /generate.webp`）。
   - **透明气泡规范**：请求参数中使用 `"type": "quote"` 与 `"backgroundColor": "#FFFFFF"`，生成纯净透明背景、带圆角与真实圆形头像的 WebP 贴纸，避免生成带 Telegram 蓝色壁纸底图的矩形图片。

5. **贴纸回传与自动清理**：
   - 将生成的 WebP 二进制数据通过 `send_sticker` 发送到原群聊（指定 `reply_to_message_id` 为被引用的消息）。
   - 成功后自动调用 `delete_message` 删除群聊里的原始 `q` 消息和私聊确认面板。
   - **60 秒超时自愈**：后台启动异步清理协程，超过 60 秒未操作的 pending 自动销毁并清理群内 `q` 消息。
