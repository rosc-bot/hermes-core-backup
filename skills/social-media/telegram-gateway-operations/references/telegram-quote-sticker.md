# Telegram 群聊 Q 版引用贴纸功能 (Quote Sticker) 实现与运维指南

## 架构概览

```
[群聊用户回复消息发 'q'] 
        │
        ▼ (Telegram Adapter 拦截)
[向发 'q' 用户发送私聊确认消息: 预览 + ✅确认 / ❌取消 按钮]
        │
   ┌────┴───────────────────────────────┐
   ▼                                    ▼
[点击 ✅确认生成]                 [点击 ❌取消 或 60s 超时]
   │                                    │
   ▼                                    ▼
[调用 Telegram Bot API 获取原作者真实头像]   [删除群聊 'q' 消息 + 删除私聊确认消息 + 清空 pending]
   │
   ▼
[POST http://127.0.0.1:4888/generate.webp (quote-api)]
   │
   ▼
[调用 send_sticker 发送 WebP 贴纸到原群回复位]
   │
   ▼
[删除群聊 'q' 消息 + 删除私聊确认消息]
```

## 组件部署与配置

### 1. quote-api 本地服务
- **目录**: `/home/ubuntu/quote-api`
- **运行端口**: `4888`
- **Systemd 服务**: `quote-api.service`
- **配置要点**:
  - 白底黑字无水印（移除 `@QuotLyBot` 和 frosted-glass 边框）。
  - 支持 `image/webp` 格式直接输出 buffer。
  - 支持接收 `photo.url` 渲染真实 Telegram 用户头像。

### 2. Telegram Adapter 接入关键要点
- **拦截时机**: `_handle_text_message` 和 `_handle_media_message` 最前置拦截。
- **真实头像解析**:
  ```python
  photos = await self._bot.get_user_profile_photos(user_id=from_id, limit=1)
  if photos and photos.photos:
      file_obj = await self._bot.get_file(photos.photos[0][-1].file_id)
      photo_url = file_obj.file_path
  ```
- **超时清扫任务**: 启动周期性后台协程（每 30 秒清扫超过 60 秒无操作的 pending 队列）。
- **必须依赖**: `import httpx` 进行异步 HTTP 请求。
