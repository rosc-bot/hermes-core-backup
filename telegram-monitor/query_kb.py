import sqlite3
import sys

DB_PATH = "/home/ubuntu/.hermes/telegram-monitor/tg_messages.db"
CHAT_ID = -1004495899387

def search_resources(query="", category="", limit=5):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if query:
        # FTS5 全文搜索
        sql = """
        SELECT r.id, r.category, r.title, r.url, r.free_tier, r.usage_guide, r.sharer, r.source_url
        FROM free_resources r
        JOIN free_resources_fts f ON r.id = f.rowid
        WHERE r.chat_id = ? AND free_resources_fts MATCH ?
        ORDER BY r.id DESC LIMIT ?
        """
        # 转义 FTS5 特殊字符
        clean_q = f'"{query}"' if " " in query else f"{query}*"
        try:
            rows = c.execute(sql, (CHAT_ID, clean_q, limit)).fetchall()
        except Exception:
            rows = c.execute("""
            SELECT id, category, title, url, free_tier, usage_guide, sharer, source_url
            FROM free_resources
            WHERE chat_id = ? AND (title LIKE ? OR usage_guide LIKE ? OR url LIKE ?)
            ORDER BY id DESC LIMIT ?
            """, (CHAT_ID, f"%{query}%", f"%{query}%", f"%{query}%", limit)).fetchall()
    elif category:
        rows = c.execute("""
        SELECT id, category, title, url, free_tier, usage_guide, sharer, source_url
        FROM free_resources
        WHERE chat_id = ? AND category = ?
        ORDER BY id DESC LIMIT ?
        """, (CHAT_ID, category, limit)).fetchall()
    else:
        rows = c.execute("""
        SELECT id, category, title, url, free_tier, usage_guide, sharer, source_url
        FROM free_resources
        WHERE chat_id = ?
        ORDER BY id DESC LIMIT ?
        """, (CHAT_ID, limit)).fetchall()
        
    conn.close()
    return rows

def format_html_summary(rows, keyword=""):
    if not rows:
        return f"⚠️ 在人🐔局白嫖知识库中未找到与「{keyword}」相关的资源方案。"
        
    output = []
    output.append(f"<b>🎁 人🐔局专属白嫖知识库 — 检索结果</b>\n")
    
    for i, (rid, cat, title, url, free_tier, usage, sharer, source_url) in enumerate(rows, 1):
        sharer_text = f"（由 <b>{sharer}</b> 分享）" if sharer and sharer != "None" else ""
        item_html = (
            f"<details>\n"
            f"<summary>方案{i}｜{title}</summary>\n\n"
            f"<b>分类：</b> {cat}\n"
            f"<b>白嫖/优惠：</b> {free_tier}\n"
            f"<b>核心链接：</b> {url}\n\n"
            f"<b>实测方案与说明</b>\n"
            f"{usage}\n\n"
            f"<b>真实来源：</b> <a href=\"{source_url}\">[来源]</a> {sharer_text}\n"
            f"</details>\n"
        )
        output.append(item_html)
        
    return "\n".join(output)

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "vps"
    results = search_resources(query=q, limit=3)
    print(format_html_summary(results, q))
