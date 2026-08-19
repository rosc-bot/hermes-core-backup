#!/usr/bin/env python3
"""
tg_query.py — 查询 Telegram 群聊消息记录，供 Hermes Agent 总结使用。

调用方式（给 Hermes 内部用）：
  python3 tg_query.py --chats                          # 列出所有群聊
  python3 tg_query.py --chat "群名" --hours 24          # 最近24小时的消息
  python3 tg_query.py --chat "群名" --since "2026-08-10" --until "2026-08-12"
  python3 tg_query.py --chat "群名" --count 50          # 最近50条消息
  python3 tg_query.py --chat "群名" --search "关键词"    # 搜索关键词
  python3 tg_query.py --stats                            # 数据库统计
"""
import argparse
import sqlite3
import sys
import os
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "tg_messages.db")

BEIJING = timezone(timedelta(hours=8))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_chats():
    conn = get_db()
    rows = conn.execute(
        "SELECT chat_id, title, kind, last_seen_at, (SELECT COUNT(*) FROM messages WHERE chat_id=c.chat_id) as msg_count "
        "FROM chats c ORDER BY last_seen_at DESC"
    ).fetchall()
    conn.close()
    if not rows:
        print("⚠️ 数据库中没有群聊记录")
        return
    print(f"{'群聊名称':<30} {'ID':<15} {'类型':<10} {'消息数':<8} {'最后活跃'}")
    print("-" * 80)
    for r in rows:
        ts = datetime.fromtimestamp(r["last_seen_at"], tz=BEIJING).strftime("%m-%d %H:%M") if r["last_seen_at"] else "?"
        print(f"{r['title'][:28]:<30} {r['chat_id']:<15} {r['kind']:<10} {r['msg_count']:<8} {ts}")


def query_messages(chat_name=None, chat_id=None, hours=None, since=None, until=None, count=50, search=None, date=None, sender=None):
    conn = get_db()
    where = []
    params = []

    if chat_name:
        where.append("(c.title LIKE ? OR c.chat_id = ?)")
        params.extend([f"%{chat_name}%", chat_name])
    if chat_id is not None:
        where.append("m.chat_id = ?")
        params.append(chat_id)
    if hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        where.append("m.date >= ?")
        params.append(cutoff.timestamp())
    if since:
        dt = datetime.fromisoformat(since).replace(tzinfo=BEIJING)
        where.append("m.date >= ?")
        params.append(dt.timestamp())
    if until:
        dt = datetime.fromisoformat(until).replace(tzinfo=BEIJING)
        where.append("m.date <= ?")
        params.append(dt.timestamp())
    if date:
        dt = datetime.fromisoformat(date).replace(tzinfo=BEIJING)
        start = dt.timestamp()
        end = (dt + timedelta(days=1)).timestamp()
        where.append("m.date >= ? AND m.date < ?")
        params.extend([start, end])
    if search:
        where.append("m.text LIKE ?")
        params.append(f"%{search}%")
    if sender:
        where.append("m.sender_name LIKE ?")
        params.append(f"%{sender}%")

    if not where:
        # default: last 24 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        where.append("m.date >= ?")
        params.append(cutoff.timestamp())

    sql = f"""
        SELECT m.*, c.title as chat_title, c.kind as chat_kind
        FROM messages m
        JOIN chats c ON m.chat_id = c.chat_id
        WHERE {' AND '.join(where)}
        ORDER BY m.date DESC
        LIMIT ?
    """
    params.append(count)
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    if not rows:
        print("⚠️ 没有找到匹配的消息记录")
        return

    results = []
    for r in reversed(rows):  # chronological order
        ts = datetime.fromtimestamp(r["date"], tz=BEIJING).strftime("%m-%d %H:%M")
        sender = r["sender_name"] or f"用户{r['sender_id']}" or "未知"
        text = r["text"] or ""
        results.append(f"[{ts}] [{r['chat_title']}] {sender}: {text}")

    print(f"📝 共 {len(results)} 条消息记录\n")
    for line in results:
        print(line)
    print(f"\n📝 共 {len(results)} 条消息")


def stats():
    conn = get_db()
    total_msgs = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    total_chats = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
    oldest = conn.execute("SELECT MIN(date) FROM messages").fetchone()[0]
    newest = conn.execute("SELECT MAX(date) FROM messages").fetchone()[0]
    per_chat = conn.execute(
        "SELECT c.title, COUNT(*) as cnt FROM messages m JOIN chats c ON m.chat_id=c.chat_id GROUP BY m.chat_id ORDER BY cnt DESC LIMIT 20"
    ).fetchall()
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    conn.close()

    print(f"📊 Telegram 消息数据库统计")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  数据库大小:    {db_size/1024:.1f} KB")
    print(f"  总消息数:      {total_msgs}")
    print(f"  监听的群聊:    {total_chats}")
    if oldest:
        print(f"  最早记录:      {datetime.fromtimestamp(oldest, tz=BEIJING).strftime('%Y-%m-%d %H:%M')}")
    if newest:
        print(f"  最新记录:      {datetime.fromtimestamp(newest, tz=BEIJING).strftime('%Y-%m-%d %H:%M')}")
    print(f"\n📈 各群聊消息数 TOP 20:")
    for r in per_chat:
        print(f"  {r['title'][:35]:<35} {r['cnt']} 条")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram 群聊消息记录查询工具")
    parser.add_argument("--chats", action="store_true", help="列出所有群聊")
    parser.add_argument("--chat", help="群聊名称或ID")
    parser.add_argument("--hours", type=int, help="最近N小时")
    parser.add_argument("--since", help="起始时间 YYYY-MM-DD 或 YYYY-MM-DD HH:MM")
    parser.add_argument("--until", help="结束时间")
    parser.add_argument("--date", help="指定日期 YYYY-MM-DD")
    parser.add_argument("--count", type=int, default=50, help="返回条数")
    parser.add_argument("--search", help="搜索关键词")
    parser.add_argument("--sender", help="按发送者筛选")
    parser.add_argument("--stats", action="store_true", help="数据库统计")
    parser.add_argument("--id", dest="chat_id", type=int, help="按chat_id查询")

    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print("⚠️ 数据库不存在，请先运行 tg_monitor.py")
        sys.exit(1)

    if args.stats:
        stats()
    elif args.chats:
        list_chats()
    elif args.chat or args.chat_id or args.hours or args.since or args.until or args.date or args.search or args.sender:
        query_messages(
            chat_name=args.chat,
            chat_id=args.chat_id,
            hours=args.hours,
            since=args.since,
            until=args.until,
            date=args.date,
            search=args.search,
            sender=args.sender,
            count=args.count,
        )
    else:
        parser.print_help()