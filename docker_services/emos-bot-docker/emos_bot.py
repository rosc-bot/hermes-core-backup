#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emos Telegram 签到服务机器人 (支持多账号绑定 + 官方 Bot OAuth 授权 + 随机寄语签到)
文档参考: https://wiki.emos.best
"""

import os
import sys
import time
import random
import logging
import asyncio
import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

import emos_db

BOT_TOKEN = os.getenv("EMOS_BOT_TOKEN", "8657174527:AAH9IVAfWEsAafzjLUG2yLPQNjZXN1zVSDE")
BOT_NAME = os.getenv("EMOS_BOT_NAME", "qiandao00_bot")
EMOS_OFFICIAL_BOT = "emospg_bot"
BASE_URL = "https://api.emos.best"

# 精选签到寄语池（≤10个字符）
WISHES_POOL = [
    # 🍀 欧气玄学与暴击暴富 (冲刺5萝卜)
    "今天必出5根胡萝卜",
    "求求来个5萝卜暴击",
    "吸一口天选欧气",
    "金光一闪萝卜到手",
    "今天签到必是大吉",
    "胡萝卜自由指日可待",
    "功德加一萝卜加五",
    "财神敲门好运爆棚",
    "今天也是锦鲤本鲤",
    "财源滚滚日富一日",
    "欧气满满",
    "好运连连",
    "万事顺意",
    "心想事成",
    "平安喜乐",
    "大吉大利",
    "吉祥如意",
    "福星高照",
    "顺风顺水",
    "暴富暴美",

    # 🎬 影视与 Emby 玩家专属梗
    "今晚看片绝不转圈",
    "原画4K丝滑秒播",
    "刮削全部秒匹配",
    "网速狂飙不掉帧",
    "蓝光原盘极速起播",
    "又白嫖到快乐一天",
    "今晚必须通宵刷剧",
    "影视库常青服务器稳",
    "码率拉满原画狂飙",
    "神剧刷到停不下来",
    "音画同步震撼视听",
    "原盘直通杜比视界",

    # 🐱 俏皮可爱与治愈日常
    "今天也要元气满满鸭",
    "开心最重要啦",
    "生活明朗万物可爱",
    "向快乐出发冲冲冲",
    "喝杯奶茶快乐翻倍",
    "今天也是可爱一天",
    "保持热爱奔赴山海",
    "烦恼退散好运来",
    "愿所有温柔都被眷顾",
    "今天也是闪闪发光呢",
    "天天开心呀",
    "梦想成真",
    "笑口常开",
    "天天向上",
    "前程似锦",
    "未来可期",
    "快乐无边",
    "诸事皆宜",

    # 💻 搞机与数码极客日常
    "服务器永远不宕机",
    "延迟低到只有1毫秒",
    "跑分狂飙节点稳定",
    "脚本零报错一把过",
    "带宽跑满直接起飞",
    "白嫖快乐多又多",
    "今日无bug早点收工",
    "内存充足永不爆卡",
    "高能低耗流畅丝滑",
    "多核全开性能炸裂",
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_random_wish() -> str:
    return random.choice(WISHES_POOL)

def fetch_user_by_token(token: str):
    """验证 Token 并返回用户信息"""
    try:
        headers = {
            "Authorization": f"Bearer {token.strip()}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
        }
        resp = requests.get(f"{BASE_URL}/api/user", headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Error fetching user info: {e}")
    return None

def fetch_carrot_history(token: str, page_size: int = 6):
    """获取指定账号的萝卜收支流水记录"""
    try:
        headers = {
            "Authorization": f"Bearer {token.strip()}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
        }
        resp = requests.get(f"{BASE_URL}/api/carrot/history?page_size={page_size}", headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("items", [])
    except Exception as e:
        logger.error(f"Error fetching carrot history: {e}")
    return []

def execute_sign(token: str, content: str = None):
    """执行签到请求（携带 ≤10 字符寄语，可得最高 5 萝卜）"""
    try:
        if not content:
            content = get_random_wish()
        content = content[:10]

        headers = {
            "Authorization": f"Bearer {token.strip()}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
        }
        payload = {"content": content}
        
        resp = requests.put(f"{BASE_URL}/api/user/sign", headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return True, data, content
        elif resp.status_code in [422, 429]:
            try:
                data = resp.json()
                msg = data.get("message", "今日已签到 (重复签到)")
            except Exception:
                msg = "今日已签到 (重复签到)"
            return False, msg, content
        else:
            return False, f"HTTP {resp.status_code}", content
    except Exception as e:
        return False, str(e), content

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []
    
    # 官方 Bot 授权回调处理
    if args:
        payload = args[0]
        logger.info(f"Received start payload from user {user.id}: {payload}")
        
        if payload.startswith("emosLinkAgree-"):
            token = payload.replace("emosLinkAgree-", "").strip()
            msg_loading = await update.message.reply_text("🔄 正在向 emos 官方核验授权登录...")
            
            user_info = fetch_user_by_token(token)
            if not user_info:
                await msg_loading.edit_text("❌ 授权失败：获取用户信息异常或 Token 无效。")
                return
            
            username = user_info.get("username", "未知")
            emos_uid = user_info.get("user_id", "未知")
            carrot = user_info.get("carrot", 0)
            
            emos_db.save_user_account(
                tg_user_id=user.id,
                tg_username=user.username or user.first_name,
                token=token,
                emos_username=username,
                emos_user_id=emos_uid,
                carrot=carrot,
            )
            
            accounts = emos_db.get_user_accounts(user.id)
            reply = (
                f"🎉 *emos 账号授权并绑定成功！*\n\n"
                f"👤 当前绑定账号: `{username}` (`{emos_uid}`)\n"
                f"🥕 账号当前萝卜: `{carrot}`\n"
                f"📱 您名下共绑定账号: `{len(accounts)}` 个\n\n"
                f"✨ 已自动开启**每日 08:00 多账号自动签到与单独推送**！\n"
                f"💡 可直接发送 /sign 手动签到全部账号，或发送 /info 查看所有账号资产。"
            )
            await msg_loading.edit_text(reply, parse_mode="Markdown")
            return
            
        elif payload.startswith("emosLinkRefuse-"):
            await update.message.reply_text("⚠️ 你已取消授权登录 emos。")
            return

    # 普通欢迎面板
    accounts = emos_db.get_user_accounts(user.id)
    auth_url = f"https://t.me/{EMOS_OFFICIAL_BOT}?start=link_tg{user.id}-{BOT_NAME}"
    
    keyboard = [
        [InlineKeyboardButton("🔗 跳转 @emospg_bot 授权添加账号", url=auth_url)],
    ]
    if accounts:
        keyboard.append([
            InlineKeyboardButton("🥕 签到全部 (/sign)", callback_data="btn_sign"),
            InlineKeyboardButton("📊 资产列表 (/info)", callback_data="btn_info"),
        ])
        keyboard.append([
            InlineKeyboardButton("📜 萝卜收支流水 (/history)", callback_data="btn_history")
        ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if accounts:
        acc_list = "\n".join([f"  • *{a['emos_username']}* (`{a['emos_user_id']}`) - `{a['last_carrot']}` 🥕" for a in accounts])
        text = (
            f"👋 你好，*{user.first_name}*！\n\n"
            f"📱 **你当前共绑定了 {len(accounts)} 个 emos 账号**：\n{acc_list}\n\n"
            f"⏰ 每天早晨 **08:00 (北京时间)** 机器人会自动为每个账号执行随机寄语签到并推送结果！\n\n"
            f"👉 如需**继续绑定新账号**，请再次点击下方按钮授权即可~"
        )
    else:
        text = (
            f"👋 你好，*{user.first_name}*！欢迎使用 **emos 自动签到机器人**。\n\n"
            f"💡 **支持同时绑定多个 emos 账号**！\n"
            f"点击下方按钮跳转至 **emos 官方机器人** 进行一键授权登录：\n"
            f"授权成功后将自动开启**每日 08:00 随机寄语定时签到与结果推送**！(最高5萝卜)"
        )
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def sign_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = emos_db.get_user_accounts(user_id)
    if not accounts:
        auth_url = f"https://t.me/{EMOS_OFFICIAL_BOT}?start=link_tg{user_id}-{BOT_NAME}"
        keyboard = [[InlineKeyboardButton("🔗 立即授权绑定账号", url=auth_url)]]
        await update.message.reply_text("❌ 你尚未绑定任何 emos 账号，请先点击下方按钮完成官方授权绑定！", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    custom_wish = " ".join(context.args).strip() if context.args else None

    msg = await update.message.reply_text(f"⏳ 正在为名下的 {len(accounts)} 个账号依次执行寄语签到...")
    results = []

    for idx, acc in enumerate(accounts, 1):
        wish = custom_wish or get_random_wish()
        token = acc["token"]
        
        before_info = fetch_user_by_token(token)
        initial_carrot = before_info.get("carrot", 0) if before_info else (acc.get("last_carrot") or 0)

        success, result, used_wish = execute_sign(token, wish)
        await asyncio.sleep(1)

        latest_info = fetch_user_by_token(token)
        current_carrot = latest_info.get("carrot", initial_carrot) if latest_info else initial_carrot
        slot_remaining = latest_info.get("slot_remaining", 0) if latest_info else 0
        earned = current_carrot - initial_carrot

        sign_obj = (latest_info.get("sign") or {}) if latest_info else {}
        continuous_days = sign_obj.get("continuous_days", 0)
        sign_index = sign_obj.get("sign_index", 0)
        base_earn = sign_obj.get("earn_point", earned)

        # 签到成功时，以官方接口返回的当日实际签到奖励为准
        earned = base_earn if base_earn > 0 else (current_carrot - initial_carrot)
        real_initial_carrot = current_carrot - earned

        emos_db.update_account_sign_record(acc["id"], current_carrot)

        if success:
            detail_lines = []
            detail_lines.append(f"👤 账号 {idx}: *{acc['emos_username']}* (`{acc['emos_user_id']}`)")
            detail_lines.append(f"  💬 签到寄语: 「*{used_wish}*」")
            detail_lines.append(f"  🎉 签到结果: 签到成功！(+{earned} 🥕)")
            
            if continuous_days > 0:
                rank_str = f" (今日第 `{sign_index}` 位)" if sign_index > 0 else ""
                detail_lines.append(f"  🔥 连续签到: `{continuous_days}` 天{rank_str}")

            detail_lines.append(f"  💰 最新萝卜: `{current_carrot}` | 🎟️ 剩余卡槽: `{slot_remaining}`")
            acc_res = "\n".join(detail_lines)
        else:
            detail_lines = []
            detail_lines.append(f"👤 账号 {idx}: *{acc['emos_username']}* (`{acc['emos_user_id']}`)")
            detail_lines.append(f"  💬 提交寄语: 「*{used_wish}*」")
            detail_lines.append(f"  ℹ️ 签到反馈: {result}")
            if continuous_days > 0:
                rank_str = f" (今日第 `{sign_index}` 位)" if sign_index > 0 else ""
                detail_lines.append(f"  🔥 连续签到: `{continuous_days}` 天{rank_str}")
            detail_lines.append(f"  💰 当前萝卜: `{current_carrot}` | 🎟️ 剩余卡槽: `{slot_remaining}`")
            acc_res = "\n".join(detail_lines)
        results.append(acc_res)
        await asyncio.sleep(1)

    reply = "🐰 *emos 批量签到完成报告*\n" + "─" * 28 + "\n\n" + "\n\n".join(results)
    await msg.edit_text(reply, parse_mode="Markdown")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = emos_db.get_user_accounts(user_id)
    if not accounts:
        auth_url = f"https://t.me/{EMOS_OFFICIAL_BOT}?start=link_tg{user_id}-{BOT_NAME}"
        keyboard = [[InlineKeyboardButton("🔗 立即授权绑定账号", url=auth_url)]]
        await update.message.reply_text("❌ 你尚未绑定任何 emos 账号，请先点击下方按钮完成官方授权绑定！", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    msg = await update.message.reply_text(f"⏳ 正在查询名下 {len(accounts)} 个账号的最新资产信息...")
    cards = []

    for idx, acc in enumerate(accounts, 1):
        token = acc["token"]
        info = fetch_user_by_token(token)
        if not info:
            cards.append(f"👤 账号 {idx}: *{acc['emos_username']}*\n  ❌ 登录凭证已失效，请重新授权绑定。")
            continue

        carrot = info.get("carrot", 0)
        slot = info.get("slot_remaining", 0)
        sign_obj = info.get("sign") or {}
        last_sign_time = sign_obj.get("sign_at") or acc.get("last_sign_at") or "今日尚未签到"
        continuous_days = sign_obj.get("continuous_days", 0)
        earn_point = sign_obj.get("earn_point", 0)
        sign_index = sign_obj.get("sign_index", 0)

        emos_db.update_account_carrot(acc["id"], carrot)

        # 拉取最近 2 条收支流水精简回显
        recent_items = fetch_carrot_history(token, page_size=2)
        flow_lines = []
        if recent_items:
            for it in recent_items:
                sym = "+" if it.get("type") == "earn" else "-"
                name = it.get("trigger_type_string") or it.get("trigger_type") or "收支"
                pt = it.get("point", 0)
                t_str = (it.get("created_at") or "")[:10]
                flow_lines.append(f"`{t_str}` {name} `{sym}{pt}` 🥕")

        card = (
            f"👤 账号 {idx}: *{info.get('username')}* (`{info.get('user_id')}`)\n"
            f"  🔑 账号凭证: `{token}`\n"
            f"  🥕 可用萝卜: `{carrot}`\n"
            f"  🎟️ 剩余卡槽: `{slot}`\n"
            f"  🔥 连续签到: `{continuous_days}` 天 (第 `{sign_index}` 位)\n"
            f"  🎁 今日奖励: `+{earn_point}` 萝卜\n"
            f"  🕒 签到时间: `{last_sign_time}`\n"
        )
        if flow_lines:
            card += f"  📜 近期收支: {' ｜ '.join(flow_lines)}"
        cards.append(card)

    reply = (
        f"📊 *emos 账号资产列表 (共 {len(accounts)} 个)*\n"
        + "─" * 28 + "\n\n"
        + "\n\n".join(cards)
        + f"\n\n⏰ 自动签到: `每天 08:00 (北京时间)`\n"
        f"✨ 签到寄语: `已启用随机寄语 (最高5萝卜)`\n"
        f"💡 可发送 `/history` 查看完整的萝卜收支流水记录。"
    )
    keyboard = [
        [InlineKeyboardButton("📜 查看详细收支流水 (/history)", callback_data="btn_history")],
        [InlineKeyboardButton("🥕 立即签到 (/sign)", callback_data="btn_sign")]
    ]
    await msg.edit_text(reply, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = emos_db.get_user_accounts(user_id)
    if not accounts:
        auth_url = f"https://t.me/{EMOS_OFFICIAL_BOT}?start=link_tg{user_id}-{BOT_NAME}"
        keyboard = [[InlineKeyboardButton("🔗 立即授权绑定账号", url=auth_url)]]
        await update.message.reply_text("❌ 你尚未绑定任何 emos 账号，请先点击下方按钮完成官方授权绑定！", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    msg = await update.message.reply_text(f"⏳ 正在拉取名下 {len(accounts)} 个账号的最新萝卜收支明细...")
    cards = []

    for idx, acc in enumerate(accounts, 1):
        token = acc["token"]
        items = fetch_carrot_history(token, page_size=8)
        lines = [f"👤 账号 {idx}: *{acc['emos_username']}* (`{acc['emos_user_id']}`)"]
        if not items:
            lines.append("  ℹ️ 暂无收支流水记录。")
        else:
            for it in items:
                sym = "+" if it.get("type") == "earn" else "-"
                name = it.get("trigger_type_string") or it.get("trigger_type") or "收支"
                point = it.get("point", 0)
                created_at = (it.get("created_at") or "")[:16].replace("T", " ")
                lines.append(f"  • `{created_at}` ｜ *{name}*: `{sym}{point}` 🥕")
        cards.append("\n".join(lines))

    reply = (
        f"📜 *emos 账号萝卜收支流水明细*\n"
        + "─" * 28 + "\n\n"
        + "\n\n".join(cards)
        + f"\n\n💡 提示：实时同步官方明细（涵盖每日签到、连签大奖、片单订阅、闲聊奖励等全部账单）。"
    )
    await msg.edit_text(reply, parse_mode="Markdown")

async def bind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []
    if not args:
        auth_url = f"https://t.me/{EMOS_OFFICIAL_BOT}?start=link_tg{user.id}-{BOT_NAME}"
        keyboard = [[InlineKeyboardButton("🔗 跳转官方授权一键绑定", url=auth_url)]]
        await update.message.reply_text(
            "💡 **多账号绑定方式**：\n"
            "1. 点击下方按钮跳转官方 Bot **一键授权登录**（推荐，可重复绑定多个账号）；\n"
            "2. 或直接发送 `/bind <你的Token>` 手动追加绑定。",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    token = args[0].strip()
    msg = await update.message.reply_text("⏳ 正在校验 Token...")
    user_info = fetch_user_by_token(token)
    if not user_info:
        await msg.edit_text("❌ 绑定失败：Token 无效或已过期，请检查后重试。")
        return

    username = user_info.get("username", "未知")
    emos_uid = user_info.get("user_id", "未知")
    carrot = user_info.get("carrot", 0)

    emos_db.save_user_account(
        tg_user_id=user.id,
        tg_username=user.username or user.first_name,
        token=token,
        emos_username=username,
        emos_user_id=emos_uid,
        carrot=carrot,
    )

    accounts = emos_db.get_user_accounts(user.id)
    reply = (
        f"🎉 *绑定成功！*\n\n"
        f"👤 用户名: `{username}` (`{emos_uid}`)\n"
        f"🥕 当前萝卜: `{carrot}`\n"
        f"📱 当前名下总绑定数: `{len(accounts)}` 个账号\n\n"
        f"✨ 已全部开启每日 08:00 随机寄语自动签到与结果推送！"
    )
    await msg.edit_text(reply, parse_mode="Markdown")

async def unbind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = emos_db.get_user_accounts(user_id)
    if not accounts:
        await update.message.reply_text("ℹ️ 你名下当前没有绑定任何账号。")
        return

    # 提供全部解除绑定的确认
    emos_db.delete_all_accounts_for_user(user_id)
    await update.message.reply_text(f"🗑️ 已成功解绑名下的全部 {len(accounts)} 个 emos 账号并清空凭证。")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth_url = f"https://t.me/{EMOS_OFFICIAL_BOT}?start=link_tg{update.effective_user.id}-{BOT_NAME}"
    keyboard = [[InlineKeyboardButton("🔗 跳转官方授权绑定账号", url=auth_url)]]
    help_text = (
        f"📖 *emos 自动签到机器人使用手册*\n\n"
        f"1. **多账号支持**：支持绑定多个账号！多次点击授权按钮或执行 `/bind <Token>` 即可依次绑定多个账号。\n"
        f"2. **一键授权登录**：点击下方按钮跳转到 `@emospg_bot` 点击【同意】即可秒级自动绑定！\n"
        f"3. **一键批量签到**：发送 `/sign` 依次对所有账号执行寄语签到（最高 5 萝卜）。\n"
        f"4. **全账号资产查询**：发送 `/info` 查看名下全部账号的萝卜、卡槽、连续签到天数。\n"
        f"5. **收支流水明细**：发送 `/history` 查询最近详细的萝卜变动明细（签到、大奖、消费）。\n"
        f"6. **解除绑定**：发送 `/unbind` 一键清空名下账号。\n\n"
        f"⏰ **每日定时**：每天早晨 **08:00 (北京时间)** 自动签到所有账号并向您推送完整报告！"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "btn_sign":
        await sign_command(update, context)
    elif data == "btn_info":
        await info_command(update, context)
    elif data == "btn_history":
        await history_command(update, context)

async def auto_daily_sign_job(bot):
    """每天 08:00 定时执行所有用户的全量账号签到并分别推送"""
    logger.info("=== 触发每日定时寄语多账号签到任务 ===")
    all_accounts = emos_db.get_all_active_accounts()
    
    # 按 tg_user_id 进行分组聚类
    user_acc_map = {}
    for acc in all_accounts:
        user_acc_map.setdefault(acc["tg_user_id"], []).append(acc)

    for tg_id, accounts in user_acc_map.items():
        results = []
        for idx, acc in enumerate(accounts, 1):
            token = acc["token"]
            wish = get_random_wish()
            try:
                before_info = fetch_user_by_token(token)
                initial_carrot = before_info.get("carrot", 0) if before_info else (acc.get("last_carrot") or 0)
                
                success, result, used_wish = execute_sign(token, wish)
                await asyncio.sleep(1)
                
                latest_info = fetch_user_by_token(token)
                current_carrot = latest_info.get("carrot", initial_carrot) if latest_info else initial_carrot
                slot_remaining = latest_info.get("slot_remaining", 0) if latest_info else 0
                earned = current_carrot - initial_carrot
                
                sign_obj = (latest_info.get("sign") or {}) if latest_info else {}
                continuous_days = sign_obj.get("continuous_days", 0)
                sign_index = sign_obj.get("sign_index", 0)
                base_earn = sign_obj.get("earn_point", earned)

                # 签到成功时，以官方接口返回的当日实际签到奖励为准
                earned = base_earn if base_earn > 0 else (current_carrot - initial_carrot)
                real_initial_carrot = current_carrot - earned

                emos_db.update_account_sign_record(acc["id"], current_carrot)

                if success:
                    detail_lines = []
                    detail_lines.append(f"👤 账号 {idx}: *{acc['emos_username']}* (`{acc['emos_user_id']}`)")
                    detail_lines.append(f"  💬 签到寄语: 「*{used_wish}*」")
                    detail_lines.append(f"  🎉 签到结果: 签到成功！(+{earned} 🥕)")
                    
                    if continuous_days > 0:
                        rank_str = f" (今日第 `{sign_index}` 位)" if sign_index > 0 else ""
                        detail_lines.append(f"  🔥 连续签到: `{continuous_days}` 天{rank_str}")

                    detail_lines.append(f"  💰 萝卜变动: `{real_initial_carrot}` ➜ `{current_carrot}` | 🎟️ 剩余卡槽: `{slot_remaining}`")
                    res_text = "\n".join(detail_lines)
                else:
                    detail_lines = []
                    detail_lines.append(f"👤 账号 {idx}: *{acc['emos_username']}* (`{acc['emos_user_id']}`)")
                    detail_lines.append(f"  💬 提交寄语: 「*{used_wish}*」")
                    detail_lines.append(f"  ℹ️ 签到结果: {result}")
                    if continuous_days > 0:
                        rank_str = f" (今日第 `{sign_index}` 位)" if sign_index > 0 else ""
                        detail_lines.append(f"  🔥 连续签到: `{continuous_days}` 天{rank_str}")
                    detail_lines.append(f"  💰 当前萝卜: `{current_carrot}` | 🎟️ 剩余卡槽: `{slot_remaining}`")
                    res_text = "\n".join(detail_lines)
                results.append(res_text)
            except Exception as e:
                logger.error(f"Error signing account {acc['id']} for user {tg_id}: {e}")
            await asyncio.sleep(2)

        try:
            report = (
                f"🐰 *emos 每日定时签到总报 (共 {len(accounts)} 个账号)*\n"
                + "─" * 28 + "\n\n"
                + "\n\n".join(results)
                + f"\n\n🕒 签到时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            await bot.send_message(chat_id=tg_id, text=report, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send daily report to user {tg_id}: {e}")

async def post_init(application):
    # 自动同步注册 Telegram Bot 菜单命令列表 (set_my_commands)
    commands = [
        BotCommand("start", "🏠 欢迎面板与快捷菜单"),
        BotCommand("sign", "🥕 批量寄语签到 (最高5萝卜)"),
        BotCommand("info", "📊 查询名下所有账号资产卡片"),
        BotCommand("history", "📜 查询萝卜详细收支明细流水"),
        BotCommand("bind", "🔗 授权或手动绑定新账号"),
        BotCommand("unbind", "🗑️ 解绑清空名下全部账号"),
        BotCommand("help", "📖 查看完整使用帮助指南"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("已自动向 Telegram 官方注册并同步 Bot 底部快捷命令菜单。")
    except Exception as e:
        logger.error(f"同步 Bot 命令菜单失败: {e}")

    job_queue = application.job_queue
    if job_queue:
        t = datetime.time(hour=8, minute=0, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        job_queue.run_daily(auto_daily_sign_job_ptb, time=t, name="daily_emos_sign")
        logger.info("已注册 PTB JobQueue 每日 08:00 (北京时间) 自动寄语多账号签到任务。")

async def auto_daily_sign_job_ptb(context: ContextTypes.DEFAULT_TYPE):
    await auto_daily_sign_job(context.bot)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # 注册命令
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("sign", sign_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("bind", bind_command))
    app.add_handler(CommandHandler("unbind", unbind_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    logger.info("🤖 emos 官方 Bot OAuth 授权 + 多账号管理 + 随机寄语签到机器人已启动！")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
