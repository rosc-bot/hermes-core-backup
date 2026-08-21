import sqlite3
import re
import os

DB_PATH = "/home/ubuntu/.hermes/telegram-monitor/tg_messages.db"

def init_kb():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. 结构化白嫖知识库主表
    c.execute("""
    CREATE TABLE IF NOT EXISTS free_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER DEFAULT -1004495899387,
        chat_title TEXT DEFAULT '人🐔局（执着白嫖）',
        message_id INTEGER,
        category TEXT,             -- AI模型与中转 | VPS与网络节点 | 公益影视Emby | 实用工具与脚本 | 源码与项目
        title TEXT,                -- 资源名称
        url TEXT,                  -- 核心链接
        free_tier TEXT,            -- 白嫖/优惠方式 (如: 免费4个月、0.1x倍率、注册送额度)
        usage_guide TEXT,          -- 实测使用方案与群友心得
        sharer TEXT,               -- 分享群友
        date REAL,                 -- 消息时间戳
        source_url TEXT,           -- t.me 原始消息直链
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(chat_id, message_id, url)
    )
    """)
    
    # 2. 全文检索引擎 FTS5 表
    c.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS free_resources_fts USING fts5(
        title, url, free_tier, usage_guide, category, sharer,
        content='free_resources', content_rowid='id'
    )
    """)
    
    # 3. 触发器：自动同步更新 FTS5
    c.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_free_resources_ai AFTER INSERT ON free_resources BEGIN
        INSERT INTO free_resources_fts(rowid, title, url, free_tier, usage_guide, category, sharer)
        VALUES (new.id, new.title, new.url, new.free_tier, new.usage_guide, new.category, new.sharer);
    END;
    """)
    c.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_free_resources_ad AFTER DELETE ON free_resources BEGIN
        INSERT INTO free_resources_fts(free_resources_fts, rowid, title, url, free_tier, usage_guide, category, sharer)
        VALUES('delete', old.id, old.title, old.url, old.free_tier, old.usage_guide, old.category, old.sharer);
    END;
    """)
    c.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_free_resources_au AFTER UPDATE ON free_resources BEGIN
        INSERT INTO free_resources_fts(free_resources_fts, rowid, title, url, free_tier, usage_guide, category, sharer)
        VALUES('delete', old.id, old.title, old.url, old.free_tier, old.usage_guide, old.category, old.sharer);
        INSERT INTO free_resources_fts(rowid, title, url, free_tier, usage_guide, category, sharer)
        VALUES (new.id, new.title, new.url, new.free_tier, new.usage_guide, new.category, new.sharer);
    END;
    """)
    
    conn.commit()
    conn.close()
    print("白嫖知识库数据库与 FTS5 引擎初始化完成 ✓")

if __name__ == "__main__":
    init_kb()
