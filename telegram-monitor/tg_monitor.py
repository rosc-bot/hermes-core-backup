#!/usr/bin/env python3
"""
Telegram Monitor — user-account group chat listener.
Stores all messages from chats the user participates in into SQLite.
Usage:
  python tg_monitor.py           # run daemon (listens for new messages)
  python tg_monitor.py --test    # quick self test (connect + report chats)
"""
import asyncio
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

from telethon import TelegramClient, events
from telethon.tl.types import Message, MessageService, User

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_ID = 35237979
API_HASH = "84025fe4f2a8b8af2e6a85635b2fe23a"
PHONE = "+85247341128"
PASSWORD = "ranran666"
SESSION = os.path.join(BASE_DIR, "tg_monitor.session")
DB_PATH = os.path.join(BASE_DIR, "tg_messages.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    kind TEXT DEFAULT 'group',
    last_seen_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
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
CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, date);
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def upsert_chat(conn, chat_id, title, kind="group"):
    conn.execute(
        """INSERT INTO chats (chat_id, title, kind, last_seen_at) VALUES (?,?,?,?)
           ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title, last_seen_at=excluded.last_seen_at""",
        (chat_id, title or str(chat_id), kind, time.time()),
    )
    conn.commit()


def save_message(conn, chat_id, chat_title, msg: Message):
    if msg.id is None:
        return
    sender_id = None
    sender_name = None
    try:
        if msg.sender_id:
            sender_id = msg.sender_id
        if getattr(msg, "sender", None):
            fn = getattr(msg.sender, "first_name", "") or ""
            ln = getattr(msg.sender, "last_name", "") or ""
            un = getattr(msg.sender, "username", "") or ""
            sender_name = " ".join([fn, ln]).strip() or un or None
    except Exception:
        pass
    text = msg.text or msg.message or ""
    if not text and getattr(msg, "media", None):
        text = f"[媒体消息] {msg.media.__class__.__name__}"
    date_ts = msg.date.timestamp() if msg.date else time.time()
    is_reply = 1 if getattr(msg, "reply_to", None) else 0
    reply_to = None
    try:
        if msg.reply_to and getattr(msg.reply_to, "reply_to_msg_id", None):
            reply_to = msg.reply_to.reply_to_msg_id
    except Exception:
        pass
    conn.execute(
        """INSERT OR IGNORE INTO messages
           (chat_id, chat_title, message_id, sender_id, sender_name, text, date, is_reply, reply_to_msg_id)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (chat_id, chat_title, msg.id, sender_id, sender_name, text, date_ts, is_reply, reply_to),
    )
    conn.commit()


async def resolve_sender_names(client, conn, chat_id, msg):
    """Best-effort: resolve sender name via client cache."""
    try:
        if msg.sender_id:
            sender = await client.get_entity(msg.sender_id)
            name = getattr(sender, "first_name", "") or ""
            last = getattr(sender, "last_name", "") or ""
            username = getattr(sender, "username", "") or ""
            full = " ".join([name, last]).strip()
            if not full:
                full = username or str(msg.sender_id)
            conn.execute(
                "UPDATE messages SET sender_name=? WHERE chat_id=? AND message_id=? AND sender_name IS NULL",
                (full, chat_id, msg.id),
            )
            conn.commit()
    except Exception:
        pass


async def main(test_mode=False):
    init_db()
    client = TelegramClient(SESSION, API_ID, API_HASH)

    if test_mode:
        await client.start(phone=PHONE, password=PASSWORD)
        me = await client.get_me()
        print(f"[OK] 已登录: {me.first_name} (@{me.username or '无'})")
        dialogs = await client.get_dialogs()
        groups = [d for d in dialogs if d.is_group or d.is_channel]
        print(f"[OK] 共 {len(dialogs)} 个对话, 其中群组/频道 {len(groups)} 个:")
        for d in groups[:30]:
            print(f"  - {d.id}\t{d.title}")
        await client.disconnect()
        print("[TEST] 连接测试完成 ✓")
        return

    @client.on(events.NewMessage())
    async def handler(event):
        msg = event.message
        chat = await event.get_chat()
        chat_id = event.chat_id
        chat_title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(chat_id)
        kind = "group"
        if getattr(chat, "broadcast", False):
            kind = "channel"
        elif getattr(chat, "first_name", None):
            kind = "private"
        conn = get_db()
        upsert_chat(conn, chat_id, chat_title, kind)
        save_message(conn, chat_id, chat_title, msg)
        asyncio.get_event_loop().create_task(resolve_sender_names(client, conn, chat_id, msg))
        # 实时自动提取人🐔局白嫖资源并入库
        if chat_id == -1004495899387 and msg.text and ("http://" in msg.text or "https://" in msg.text):
            try:
                import backfill_kb
                urls = backfill_kb.URL_REGEX.findall(msg.text)
                for u in urls:
                    u_clean = backfill_kb.clean_url(u)
                    if not any(ign in u_clean.lower() for ign in backfill_kb.IGNORE_DOMAINS):
                        cat, title, free_tier, usage = backfill_kb.guess_category_and_info(u_clean, msg.text, [])
                        source_url = f"https://t.me/c/4495899387/{msg.id}"
                        conn.execute("""
                        INSERT INTO free_resources(chat_id, chat_title, message_id, category, title, url, free_tier, usage_guide, sharer, date, source_url)
                        VALUES (?, '人🐔局（执着白嫖）', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(chat_id, message_id, url) DO UPDATE SET
                            category=excluded.category,
                            title=excluded.title,
                            free_tier=excluded.free_tier,
                            usage_guide=excluded.usage_guide,
                            sharer=excluded.sharer
                        """, (-1004495899387, msg.id, cat, title, u_clean, free_tier, usage, getattr(msg.sender, "first_name", None), msg.date.timestamp() if msg.date else time.time(), source_url))
                        conn.commit()
            except Exception as e:
                print(f"[KB-AutoIngest Error] {e}")
        conn.close()

    me = await client.start(phone=PHONE, password=PASSWORD)
    me = await client.get_me()
    print(f"[MONITOR] 已启动 ✓ 账号: {me.first_name} (@{me.username or '无'})")
    print(f"[MONITOR] 监听所有群聊消息，存入 {DB_PATH}")
    print(f"[MONITOR] 按 Ctrl+C 停止")
    await client.run_until_disconnected()


if __name__ == "__main__":
    test = "--test" in sys.argv
    try:
        asyncio.run(main(test_mode=test))
    except KeyboardInterrupt:
        print("\n[STOP] 已停止")