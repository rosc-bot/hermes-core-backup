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

- **Telegram Bot Service**: `emos-bot.service` (systemd unit running `/home/ubuntu/emos_bot.py`).
- **Database**: SQLite at `/home/ubuntu/.hermes/emos_users.db` (tables: `accounts`, supporting multiple emos accounts per TG user).
- **Standalone Cron Script**: `/home/ubuntu/.hermes/scripts/emos_sign.py`.
- **Official Bot**: `@emospg_bot`.
- **API Base URLs**: `https://api.emos.best` / `https://emos.best`.

## 2. emos.best Official API Endpoints

All authenticated requests require `Authorization: Bearer <token>` and a standard browser `User-Agent` (to prevent Cloudflare 403 / anti-scraping blocks).

| Endpoint | Method | Purpose & Payload |
| :--- | :--- | :--- |
| `/api/user` | `GET` | Fetch profile, current carrots (`carrot`), slots (`slot_remaining`), and sign status (`sign`: `continuous_days`, `sign_index`, `earn_point`). |
| `/api/user/sign` | `PUT` | Execute daily sign-in. JSON body: `{"content": "<wish_string>"}`. **Wish string must be ≤10 chars** for a chance to win up to 5 carrots. |
| `/api/carrot/history?page_size=N` | `GET` | Retrieve carrot transaction ledger (`items`: `trigger_type_string`, `type` [`earn`/`cost`], `point`, `created_at`). |

## 3. Telegram OAuth Workflow & Troubleshooting

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

**Calculation Rule**: Total earned = `current_carrot - initial_carrot`. When `earned > base_earn`, the milestone bonus is `earned - base_earn`. Display both base reward and milestone badge in reports.
