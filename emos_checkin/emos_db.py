import sqlite3
import os
import datetime

DB_PATH = os.path.expanduser("~/.hermes/emos_users.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 创建支持多账号的 accounts 表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER NOT NULL,
            tg_username TEXT,
            token TEXT NOT NULL,
            emos_username TEXT,
            emos_user_id TEXT,
            last_sign_at TEXT,
            last_carrot INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tg_user_id, token)
        )
    """)
    # 迁移旧数据 (如果 users 表存在)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cur.fetchone():
        try:
            cur.execute("""
                INSERT OR IGNORE INTO accounts (tg_user_id, tg_username, token, emos_username, emos_user_id, last_sign_at, last_carrot, is_active)
                SELECT tg_user_id, tg_username, token, emos_username, emos_user_id, last_sign_at, last_carrot, is_active FROM users
            """)
        except Exception:
            pass
    conn.commit()
    conn.close()

def save_user_account(tg_user_id: int, tg_username: str, token: str, emos_username: str, emos_user_id: str, carrot: int):
    """保存或更新单个账号（以 tg_user_id + token 为唯一键，支持同TG绑定多账号）"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO accounts (tg_user_id, tg_username, token, emos_username, emos_user_id, last_carrot, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(tg_user_id, token) DO UPDATE SET
            tg_username = excluded.tg_username,
            emos_username = excluded.emos_username,
            emos_user_id = excluded.emos_user_id,
            last_carrot = excluded.last_carrot,
            is_active = 1
    """, (tg_user_id, tg_username, token, emos_username, emos_user_id, carrot))
    conn.commit()
    conn.close()

def get_user_accounts(tg_user_id: int):
    """获取某个 Telegram 用户绑定的所有账号列表"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, tg_user_id, tg_username, token, emos_username, emos_user_id, last_sign_at, last_carrot, is_active
        FROM accounts
        WHERE tg_user_id = ? AND is_active = 1
        ORDER BY id ASC
    """, (tg_user_id,))
    rows = cur.fetchall()
    conn.close()
    accounts = []
    for row in rows:
        accounts.append({
            "id": row[0],
            "tg_user_id": row[1],
            "tg_username": row[2],
            "token": row[3],
            "emos_username": row[4],
            "emos_user_id": row[5],
            "last_sign_at": row[6],
            "last_carrot": row[7],
            "is_active": row[8],
        })
    return accounts

def get_all_active_accounts():
    """获取所有处于激活状态的账号列表（供每日自动签到遍历）"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, tg_user_id, tg_username, token, emos_username, emos_user_id, last_sign_at, last_carrot
        FROM accounts
        WHERE is_active = 1
        ORDER BY id ASC
    """)
    rows = cur.fetchall()
    conn.close()
    accounts = []
    for row in rows:
        accounts.append({
            "id": row[0],
            "tg_user_id": row[1],
            "tg_username": row[2],
            "token": row[3],
            "emos_username": row[4],
            "emos_user_id": row[5],
            "last_sign_at": row[6],
            "last_carrot": row[7],
        })
    return accounts

def update_account_sign_record(account_id: int, carrot: int, sign_time: str = None):
    """更新某个具体账号的最新萝卜和签到时间"""
    if sign_time is None:
        sign_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE accounts SET last_carrot = ?, last_sign_at = ? WHERE id = ?", (carrot, sign_time, account_id))
    conn.commit()
    conn.close()

def update_account_carrot(account_id: int, carrot: int):
    """更新某个账号的萝卜数量"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE accounts SET last_carrot = ? WHERE id = ?", (carrot, account_id))
    conn.commit()
    conn.close()

def delete_account_by_id(account_id: int, tg_user_id: int):
    """删除指定的账号"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM accounts WHERE id = ? AND tg_user_id = ?", (account_id, tg_user_id))
    conn.commit()
    conn.close()

def delete_all_accounts_for_user(tg_user_id: int):
    """清空某个用户的所有账号"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM accounts WHERE tg_user_id = ?", (tg_user_id,))
    conn.commit()
    conn.close()
