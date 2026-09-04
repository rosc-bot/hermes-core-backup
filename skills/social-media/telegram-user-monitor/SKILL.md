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

## 生产运行环境（Docker Compose 容器部署）

目前已将用户监听全面迁移至 Docker Compose 容器管理，避免与系统 Python 环境冲突并实现开机自启：

- **容器工程目录**：`/home/ubuntu/telegram-monitor-docker`
- **容器专属名称**：`telegram-group-monitor` (`container_name: telegram-group-monitor`)
- **数据持久化挂载**：
  - 宿主机 `./data/` 挂载至容器内部 `/app/data/`
  - 核心数据库：`/home/ubuntu/telegram-monitor-docker/data/tg_messages.db`
  - 宿主机查询软链接保持兼容：`~/.hermes/telegram-monitor/tg_messages.db -> /home/ubuntu/telegram-monitor-docker/data/tg_messages.db`
- **管理命令**：
  ```bash
  cd /home/ubuntu/telegram-monitor-docker
  sudo docker compose logs -f telegram-group-monitor
  sudo docker compose restart telegram-group-monitor
  ```

## 目录结构（宿主机兼容查询层）

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
- **个人与多成员轨迹画像规范**：
  - 查询特定成员（或对比多个成员）动态时，必须展示完整且对应的 Telegram ID（包括主号、摸奖小号、渡劫备用号等），并严格对照花名册。
  - 严禁偏袒或单方面详述某一人而略过其他成员；对并列查询的成员必须保持同等颗粒度的深度还原与轨迹梳理。
  - **输出格式**：查单个成员“在干什么”时使用**紧凑纯文本列表**（`📍 人物名 动态 — 时间范围` 开头，按 `【时间｜群名】事件` 逐条列出，可一眼扫完），**严禁套用群聊总结的 `<details>` 折叠格式**（用户明确纠正过此点）；只有总结群聊消息本身才用折叠块。
- **同名群匹配**：同名/近名群可能有多个（如“拾光”主群与“拾光𝑬𝒎𝒃𝒚”）。执行“总结XX N h”前先 `tg_query.py --chats` 列出所有候选，按用户语境选定正确 chat_id，再按 `--hours N` 严格拉取，禁止串群或擅自改条数。
- 按 username 查询无结果时，改用别名、sender_id、关键词和最近消息范围交叉查询；仍无记录只能报告“当前记录未命中”，不能断言对方正在潜水或没有活动。

## 身份核实权威方法（防认错人）

**严禁仅凭昵称或历史发言关联猜测身份**（昵称可改、不同人可同名，本类事故曾把 J佬误认成凯哥、把路人 Jimmy 误认成小新）。唯一可靠来源是 Telethon 会话实体库：

```python
import sqlite3, os
# Telethon session 本身是 SQLite，entities 表保存 username→id 权威映射
scon = sqlite3.connect(os.path.expanduser("~/.hermes/telegram-monitor/tg_monitor.session"))
rows = scon.execute("SELECT id, username, name, date FROM entities WHERE username=?", (username,)).fetchall()
# 列：id / hash / username / phone / name / date
```

流程：以 `username` 匹配 entities 表拿到 `id` → 再以 `id` 反查 `tg_messages.db` 的 messages 表确认发言 → 两个 ID 对上了才认定身份。

维护 `~/.hermes/telegram-monitor/user_alias.py`：`ALIAS_MAP`（用户名/昵称→称呼）+ `ID_MAP`（id→称呼）。发现纠正后**同步更新长期记忆花名册**，避免下次再错。已核实完整映射见 `references/roster-id-map.md`。

## 注意事项

- **会话文件敏感**：`tg_monitor.session` 包含认证令牌，不要提交到 git
- **Telegram 限流**：大量消息处理可能触发限制，脚本只存文本和元数据，不下载媒体
- **账号风险**：程序化使用用户账号违反 Telegram ToS，建议使用小号
- **守护进程保活**：nohup 方式运行，生产环境建议用 systemd 或 cron 健康检查重启