---
name: emos-checkin-system
description: "Use when managing emos.best check-in bot and OAuth API."
version: 1.0.0
author: Hermes Agent
platforms: [linux]
metadata:
  hermes:
    tags: [emos, checkin, telegram-bot, oauth, api, carrots]
    related_skills: [human-chicken-free-kb, tg-group-summary]
---

# emos.best Check-in Bot & OAuth Integration

Use this skill when administering, troubleshooting, or enhancing the multi-account emos check-in bot (`@qiandao00_bot`), daily scheduled runs, and emos.best API integrations.

## 1. System Architecture & Components

- **Telegram Bot Service**: Docker Compose container `emos-checkin-bot` at `/home/ubuntu/emos-bot-docker` (migrated from systemd `emos-bot.service`, auto-restarts via `restart: unless-stopped`).
  - *Dependency note*: Ensure `python-telegram-bot[job-queue]` (including `apscheduler` and `pytz`) is installed in the container image to enable `app.job_queue.run_daily`.
- **Database**: SQLite mounted at `/home/ubuntu/emos-bot-docker/data/emos_users.db` (symlinked/compatible with `~/.hermes/emos_users.db`, tables: `accounts`, supporting multiple emos accounts per TG user).
- **Standalone Scripts & Old Services**: Legacy `emos_bot.py`, `emos_db.py`, `emos_sign.py`, and `emos-bot.service` have been deprecated and deleted to prevent conflicting double runs.

## 2. emos.best Official API Endpoints

All authenticated requests require `Authorization: Bearer <token>` and a standard browser `User-Agent` (to prevent Cloudflare 403 / anti-scraping blocks).

| Endpoint | Method | Purpose & Payload |
| :--- | :--- | :--- |
| `/api/user` | `GET` | Fetch profile, current carrots (`carrot`), slots (`slot_remaining`), and sign status (`sign`: `continuous_days`, `sign_index`, `earn_point`). |
| `/api/user/sign` | `PUT` | Execute daily sign-in. JSON body: `{"content": "<wish_string>"}`. **Wish string must be ≤10 chars** for a chance to win up to 5 carrots. |
| `/api/carrot/history?page_size=N` | `GET` | Retrieve carrot transaction ledger (`items`: `trigger_type_string`, `type` [`earn`/`cost`], `point`, `created_at`). |

## 3. Telegram OAuth Workflow & Troubleshooting

### 签到寄语池多样化与字数规范
- **硬性字数限制**：寄语必须 `<= 10` 个字符（代码中必须强制执行 `content[:10]` 截断保护），超出无法冲击每日最高 5 根胡萝卜。
- **内容风格多样化**：避免使用单一传统的四字成语，应涵盖：
  1. 欧气玄学/暴击（如 `今天必出5根胡萝卜`、`求求来个5萝卜暴击`、`功德+1 萝卜+5`）；
  2. 观影/Emby玩家梗（如 `今晚看片绝不转圈`、`原画4K丝滑秒播`、`刮削全部秒匹配`）；
  3. 搞机/运维日常（如 `服务器永远不宕机`、`延迟低到只有1毫秒`、`今日无bug早点收工`）；
  4. 俏皮可爱与治愈（如 `今天也要元气满满鸭`、`生活明朗万物可爱`）。

1. **Authorization Redirection URL**:
   `https://t.me/emospg_bot?start=link_tg<telegram_user_id>-<bot_name>`
2. **Callback Agreement / Rejection**:
   - Agreement: `https://t.me/<bot_name>?start=emosLinkAgree-<user_token>`
   - Rejection: `https://t.me/<bot_name>?start=emosLinkRefuse-<telegram_user_id>`
3. **Common Error: `link用户ID错误` (Link User ID Error)**:
   - **Symptom**: User clicks the OAuth button in `@qiandao00_bot`, jumps to `@emospg_bot`, but the official bot says `link用户ID错误`.
   - **Root Cause**: The user's Telegram account has not yet been linked to an emos account in the emos web portal or official database.
   - **Fix**: Direct the user to log in at [https://emos.best](https://emos.best) -> Settings -> Bind Telegram, or send `/login` to `@emospg_bot` first, then retry OAuth authorization.

## 4. Carrot Rewards & Milestone Breakdown

emos gives bonus carrots for continuous streaks on top of the daily random wish reward:
- **Base Sign-in Reward**: 1 ~ 5 carrots (`sign.earn_point`).
- **Weekly Milestone (7 Days)**: `+10` carrots (`sign_week`).
- **Monthly Milestone (30/90 Days)**: `+50` carrots (`sign_month`).
- **Yearly Milestone (365 Days)**: `+3000` carrots.

**Calculation Rule**:
- **NEVER** calculate daily rewards by naive cache delta (`current_carrot - cached_initial_carrot`), which yields `+0` if cache was pre-synced or out-of-order.
- **ALWAYS** extract actual earned points directly from `sign.earn_point`.
- For total milestone surges, compute `real_initial_carrot = current_carrot - earned` so reports show `real_initial ➜ current_carrot (+earned)`.

## 5. Single Source of Truth for Daily Broadcasts (Deduplication)

Never configure both a Telegram bot background job (like `job_queue.run_daily`) AND an external cron job (like Hermes Cron or system crontab) to trigger the same user sign-ins at 08:00:
- Double execution triggers official API `422/429` "今日已签到 (重复签到)".
- The user receives duplicate notifications: one successful summary and one subsequent "重复签到" error message.
- **Enforcement**: Run daily multi-account sign-in ONLY inside `emos-bot.service` (`job_queue.run_daily`), sending directly via the bot. Keep Hermes Cron free of duplicate check-in jobs.

## 6. Telegram Bot Command Synchronization & UI Standards

1. **Automatic Menu Synchronization (`set_my_commands`)**:
   - Whenever new commands are introduced (e.g. `/history`, `/info`, `/bind`), they **MUST** be registered automatically during the bot's `post_init` hook using `await application.bot.set_my_commands(commands)` with clear Chinese descriptions.
   - Never require manual command registration via BotFather when adding bot features.
2. **Account Token Visibility in `/info`**:
   - In `/info` account asset cards, always display the account's authorization `token` enclosed in backticks (`` `token` ``) so users can tap-to-copy their credentials directly from Telegram.
3. **CRITICAL WORKFLOW PRINCIPLE: Ask Before Applying**:
   - For all bot features, DB schema changes, or config updates, always present proposed changes, options, and trade-offs to the user first. Obtain explicit approval before modifying production scripts or restarting services.

