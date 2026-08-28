#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emos 自动签到脚本 (支持随机寄语，最高可得 5 萝卜)
文档来源: https://wiki.emos.best
适用平台: Linux / Windows / macOS / 青龙面板 / 云函数
"""

import os
import sys
import json
import time
import random
import requests

# ----------------- 配置区域 -----------------
EMOS_TOKENS = [
    "6265_HW0tl7SprkQcfSL8",  # 账号 1 (ranran)
    "6297_4GP3LnyEM91xpPpl",  # 账号 2 (rosc)
]

ENV_TOKENS = os.getenv("EMOS_TOKENS", "").strip()
if ENV_TOKENS:
    EMOS_TOKENS = [t.strip() for t in ENV_TOKENS.replace("\n", ",").split(",") if t.strip()]

BASE_URL = "https://api.emos.best"

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "8657174527:AAH9IVAfWEsAafzjLUG2yLPQNjZXN1zVSDE")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "8586984520")

# 精选签到寄语池（≤10个字符）
WISHES_POOL = [
    "天天开心呀",
    "万事顺意",
    "心想事成",
    "今天也要加油",
    "好运连连",
    "元气满满",
    "平安喜乐",
    "欧气满满",
    "日富一日",
    "岁岁平安",
    "未来可期",
    "暴富暴美",
    "前程似锦",
    "快乐无边",
    "诸事皆宜",
    "大吉大利",
    "财源滚滚",
    "吉祥如意",
    "福星高照",
    "天天向上",
    "顺风顺水",
    "笑口常开",
    "梦想成真",
    "锦鲤附体",
]
# --------------------------------------------

def get_random_wish() -> str:
    return random.choice(WISHES_POOL)

def send_telegram(msg: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"[-] Telegram 推送失败: {e}")

class EmosCheckIn:
    def __init__(self, token: str):
        self.token = token.strip()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
        })

    def get_user_info(self):
        try:
            resp = self.session.get(f"{BASE_URL}/api/user", timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                print("[-] Token 已失效，请前往 emos.best 重新获取！")
                return None
            else:
                print(f"[-] 获取用户信息失败 (状态码: {resp.status_code}): {resp.text}")
                return None
        except Exception as e:
            print(f"[-] 网络请求异常: {e}")
            return None

    def do_sign(self, wish: str):
        try:
            payload = {"content": wish[:10]}
            resp = self.session.put(f"{BASE_URL}/api/user/sign", json=payload, timeout=15)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except:
                    data = resp.text
                return True, data
            elif resp.status_code in [422, 429]:
                try:
                    data = resp.json()
                    msg = data.get("message", "今日已签到 (重复签到)")
                except:
                    msg = "今日已签到 (重复签到)"
                return False, msg
            else:
                return False, f"HTTP {resp.status_code}: {resp.text}"
        except Exception as e:
            return False, f"异常: {e}"

    def run(self):
        print("=" * 45)
        masked_token = self.token[:4] + "****" + self.token[-4:] if len(self.token) > 8 else "****"
        print(f"🚀 开始测试账号 Token: {masked_token}...")
        user_info = self.get_user_info()
        if not user_info:
            return "❌ 登录鉴权失败，Token 无效。"

        username = user_info.get("username", "未知用户")
        user_id = user_info.get("user_id", "未知ID")
        initial_carrot = user_info.get("carrot", 0)
        slot_remaining = user_info.get("slot_remaining", 0)

        wish = get_random_wish()
        print(f"👤 用户名: {username} (ID: {user_id})")
        print(f"💬 随机寄语: 「{wish}」")
        print(f"🥕 签到前萝卜: {initial_carrot} | 🎟️ 剩余卡槽: {slot_remaining}")

        success, result = self.do_sign(wish)
        time.sleep(1)

        latest_info = self.get_user_info()
        current_carrot = latest_info.get("carrot", initial_carrot) if latest_info else initial_carrot
        earned = current_carrot - initial_carrot

        if success:
            sign_msg = f"🎉 签到成功！本次获得: +{earned} 🥕 (最高5🥕)\n🥕 当前萝卜总量: {current_carrot}"
            print(f"[+] {sign_msg}")
        else:
            sign_msg = f"ℹ️ 签到反馈: {result}\n🥕 当前萝卜总量: {current_carrot}"
            print(f"[*] {sign_msg}")

        summary = (
            f"🐰 *emos 每日签到报告*\n"
            f"👤 用户: `{username}` (`{user_id}`)\n"
            f"💬 签到寄语: 「*{wish}*」\n"
            f"📢 结果: {result if not success else '签到成功'}\n"
            f"🥕 萝卜变动: `{initial_carrot}` ➜ `{current_carrot}` (+{max(0, earned)})\n"
            f"🎟️ 卡槽状态: `{slot_remaining}`"
        )
        return summary

def main():
    if not EMOS_TOKENS or not any(EMOS_TOKENS):
        print("❌ 错误: 未配置任何 EMOS_TOKENS！")
        sys.exit(1)

    reports = []
    for idx, token in enumerate(EMOS_TOKENS, 1):
        print(f"\n[{idx}/{len(EMOS_TOKENS)}] 正在处理第 {idx} 个账号...")
        bot = EmosCheckIn(token)
        report = bot.run()
        reports.append(report)
        time.sleep(2)

    full_report = "\n\n".join(reports)
    send_telegram(full_report)
    print("\n✨ 所有账号处理完毕！")

if __name__ == "__main__":
    main()
