---
name: telegram-user-monitor
description: "Use when monitoring Telegram groups via Telethon user acct."
category: social-media
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [telegram, telethon, monitoring, group-chat, sqlite, message-archive]
---

# Telegram User-Account Group Monitor

Telethon 用户账号监听群聊消息并存入 SQLite，支持按需查询和总结。

## When to Use

- User wants to passively monitor Telegram group chats without a bot (e.g., groups the user is already in)
- User wants to store group messages in a local database for later recall, search, or summarization
- Bot cannot be added to the group, or the user wants to see messages before the bot joins
- User asks "summarize what was said in group X" — run tg_query.py then feed output to the agent

## Scripts

This skill ships with two runnable scripts under `scripts/`:
- `scripts/tg_monitor.py` — the daemon listener (run `--test` for first auth, then background daemon)
- `scripts/tg_query.py` — query tool to retrieve messages from database

Both use placeholder credentials. **Replace `API_ID`, `API_HASH`, `PHONE` with real values from https://my.telegram.org/apps before running.**

## 为什么用用户账号而不是 Bot？

- Bot 无法看到群聊消息，除非被添加为管理员
- Bot 看不到加入之前的消息
- 用户账号能看到用户能看到的一切

## 目录结构

```
~/.hermes/telegram-monitor/
├── .venv/                  # Python venv (Telethon)
├── tg_monitor.py           # 守护进程监听器
├── tg_query.py             # 查询/总结工具
├── tg_monitor.session      # Telethon 会话文件（持久化认证）
└── tg_messages.db          # SQLite 数据库（自动创建）
```

## 初始化

```bash
cd ~/.hermes/telegram-monitor
uv venv
uv pip install telethon
```

**前置条件**：从 https://my.telegram.org/apps 获取 `API_ID` 和 `API_HASH`。

## 首次认证（交互式）

```bash
cd ~/.hermes/telegram-monitor
.venv/bin/python tg_monitor.py --test
```

Telegram 会发送验证码到手机号。输入验证码完成登录。会话保存到 `tg_monitor.session` 自动复用。

如账号启用了两步验证，输入验证码后还会要求输入密码。

## 数据库 Schema（自动创建）

```sql
CREATE TABLE chats (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    kind TEXT DEFAULT 'group',
    last_seen_at REAL
);
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    chat_title TEXT,
    message_id INTEGER,
    sender_id INTEGER,
    sender_name TEXT,
    text TEXT,
    date REAL,
    is_reply INTEGER DEFAULT 0,
    reply_to_msg_id INTEGER,
    UNIQUE(chat_id, message_id)
);
```

## 后台运行

```bash
cd ~/.hermes/telegram-monitor
nohup .venv/bin/python tg_monitor.py > tg_monitor.log 2>&1 &
```

## 查询消息（供总结使用）

```bash
# 列出所有监听的群聊
.venv/bin/python tg_query.py --chats

# 最近24小时指定群聊的消息
.venv/bin/python tg_query.py --chat "群名" --hours 24

# 搜索关键词
.venv/bin/python tg_query.py --chat "群名" --search "关键词"

# 查询某天的消息
.venv/bin/python tg_query.py --chat "群名" --date "2026-08-12"

# 数据库统计
.venv/bin/python tg_query.py --stats
```

## 脚本实现要点

### tg_monitor.py
- 使用 `TelegramClient` + `events.NewMessage()` 监听所有新消息
- `INSERT OR IGNORE` 在 `(chat_id, message_id)` 联合唯一键上实现去重
- 媒体消息存为 `[媒体消息] MediaTypeName`
- 发送者名称异步解析（先存后补）
- `--test` 参数列出用户所在的所有对话

### tg_query.py
- `--chats`: 列出所有群聊及消息数
- `--chat NAME`: 按名称筛选
- `--hours N`: 最近 N 小时
- `--since/--until`: 日期范围（北京时间 YYYY-MM-DD）
- `--date`: 单日查询
- `--search`: 关键词搜索
- `--sender`: 按发送者筛选
- `--stats`: 数据库统计
- `--count N`: 最大返回条数（默认 50）

## 发送者别名与身份归一化

群聊查询时，数据库里的 `sender_name` 可能只显示为“用户+数字”，也可能没有保存 Telegram username。因此：

- 优先使用数据库实际返回的 sender_name、sender_id 和消息文本，不要把未命中的 username 推断成“没有发言”。
- 用户明确提供的稳定称呼映射应作为别名层使用：`@wangekunleo` 叫“挽歌”；`@lin2553_2` 叫“红猫”；`@jpnsmzx`、`@xxxanxin`、`@Joshua Chen` 是同一人，统一叫“浮生”。
- 汇报时可将原始标识与别名并列，例如“用户1558880868（挽歌）”，但不要仅凭昵称或相似内容断言身份；多个账号只有在用户明确确认后才合并。
- 按 username 查询无结果时，改用别名、sender_id、关键词和最近消息范围交叉查询；仍无记录只能报告“当前记录未命中”，不能断言对方正在潜水或没有活动。

## 注意事项

- **会话文件敏感**：`tg_monitor.session` 包含认证令牌，不要提交到 git
- **Telegram 限流**：大量消息处理可能触发限制，脚本只存文本和元数据，不下载媒体
- **账号风险**：程序化使用用户账号违反 Telegram ToS，建议使用小号
- **守护进程保活**：nohup 方式运行，生产环境建议用 systemd 或 cron 健康检查重启