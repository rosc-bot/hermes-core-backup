import sqlite3
import re
import urllib.parse
from datetime import datetime

DB_PATH = "/home/ubuntu/.hermes/telegram-monitor/tg_messages.db"
CHAT_ID = -1004495899387

URL_REGEX = re.compile(r'https?://[^\s<>"\')]+', re.IGNORECASE)

# 过滤无实质意义的 URL (贴纸包链接、短链群邀请、抖音/微博/新闻热搜、无效搜索链接等)
IGNORE_DOMAINS = [
    't.me/addstickers', 't.me/c/', 't.me/joinchat', 't.me/+',
    't.me/setlanguage', 't.me/socks?', 't.me/proxy?',
    'douyin.com', 'weibo.com', 'zhihu.com', 'bilibili.com/video/BV',
    'google.com/search', 'baidu.com', 'bing.com'
]

def clean_url(url):
    url = url.rstrip('.,;!?:')
    return url

def guess_category_and_info(url, text, context_texts):
    full_text = text + " " + " ".join(context_texts)
    url_lower = url.lower()
    
    cat = "实用工具与脚本"
    title = ""
    free_tier = ""
    usage_guide = ""
    
    # 1. GitHub 源码
    if "github.com" in url_lower:
        cat = "源码与项目"
        parts = url.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            repo_name = f"{parts[0]}/{parts[1]}"
            title = f"GitHub: {repo_name}"
        else:
            title = "GitHub 开源仓库"
        free_tier = "开源免费自托管"
        usage_guide = text.strip() if len(text.strip()) > 5 else "群友分享的开源项目/部署工具"
        
    # 2. VPS / 节点 / 机场 / 订阅
    elif any(k in full_text.lower() or k in url_lower for k in ['vps', '流量', '服务器', '开机', '轻量', 'host', 'cloud', 'sub', '节点', '机场', '订阅', 'cf', '优选', 'dgn', 'ovh']):
        cat = "VPS与网络节点"
        if "dgnlinks.com" in url_lower or "dng" in full_text.lower():
            title = "DNG Cloud 免费 4 个月香港 VPS"
            free_tier = "免费 4 个月 (2核/2G/20G/1T流量)"
            usage_guide = "最低配开机可用4个月，需在网络中手动创建 1T 流量包方可点亮创建按钮。"
        elif "sub.ehb.cc.cd" in url_lower:
            title = "Cloudflare 实时优选 IP 与订阅池"
            free_tier = "全免费无门槛公开接口"
            usage_guide = "直连拉取移动/电信/联通优选IP，配合 CloudflareSpeedTest 自动测速或填入节点 Server 地址。"
        elif "404.do/lhgroup" in url_lower or "腾讯云" in full_text:
            title = "腾讯云轻量服务器限时秒杀"
            free_tier = "¥139/1年 (2核4G5M/500G流量)"
            usage_guide = "单账号限购1台，适合建站或轻量挂机测试。"
        elif "ovheco.com" in url_lower or "ovh" in full_text.lower():
            title = "OVH 官方特价独服/VPS 监控与下单"
            free_tier = "低价特价机监控 (€9.99/月)"
            usage_guide = "实时监控法国/加拿大高性价比独服与低价机房补货。"
        else:
            domain = urllib.parse.urlparse(url).netloc
            title = f"{domain} 节点/VPS 资源"
            free_tier = "群友实测分享"
            usage_guide = text.strip()

    # 3. AI / API / 模型 / 中转
    elif any(k in full_text.lower() or k in url_lower for k in ['api', 'token', '中转', 'gpt', 'claude', 'gemini', 'qwen', '倍率', '模型', '对话', 'true-sota']):
        cat = "AI模型与中转"
        if "true-sota.com" in url_lower:
            title = "True-SOTA AI 聚合/模型平台"
            free_tier = "邀请注册/白嫖测试额度"
            usage_guide = "群友 L 分享的 AI 平台注册与接入渠道。"
        else:
            domain = urllib.parse.urlparse(url).netloc
            title = f"{domain} AI API/中转资源"
            free_tier = "注册赠额度 / 低倍率调用"
            usage_guide = text.strip()

    # 4. Emby / 影视服
    elif any(k in full_text.lower() or k in url_lower for k in ['emby', 'jellyfin', '公益服', '电影', '影视', '开号', '保号']):
        cat = "公益影视Emby"
        domain = urllib.parse.urlparse(url).netloc
        title = f"{domain} 公益 Emby/影视服务"
        free_tier = "公益免保号/开放注册"
        usage_guide = text.strip()

    else:
        domain = urllib.parse.urlparse(url).netloc
        title = f"{domain} 实用工具"
        free_tier = "免费工具/资源"
        usage_guide = text.strip()
        
    return cat, title, free_tier, usage_guide

def run():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM free_resources WHERE chat_id=?", (CHAT_ID,))
    
    rows = c.execute("""
    SELECT id, message_id, sender_name, text, date
    FROM messages
    WHERE chat_id=? AND text LIKE '%http%'
    ORDER BY id ASC
    """, (CHAT_ID,)).fetchall()
    
    print(f"找到人🐔局含 URL 的历史消息: {len(rows)} 条")
    
    inserted = 0
    for idx, (db_id, msg_id, sender, text, date) in enumerate(rows):
        urls = URL_REGEX.findall(text)
        if not urls:
            continue
            
        # 获取前后上下文
        context_rows = c.execute("""
        SELECT text FROM messages
        WHERE chat_id=? AND id BETWEEN ? AND ?
        """, (CHAT_ID, db_id - 3, db_id + 3)).fetchall()
        context_texts = [r[0] for r in context_rows if r[0]]
        
        for u in urls:
            u_clean = clean_url(u)
            if any(ign in u_clean.lower() for ign in IGNORE_DOMAINS):
                continue
                
            cat, title, free_tier, usage = guess_category_and_info(u_clean, text, context_texts)
            source_url = f"https://t.me/c/4495899387/{msg_id}"
            
            try:
                c.execute("""
                INSERT INTO free_resources(chat_id, chat_title, message_id, category, title, url, free_tier, usage_guide, sharer, date, source_url)
                VALUES (?, '人🐔局（执着白嫖）', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, message_id, url) DO UPDATE SET
                    category=excluded.category,
                    title=excluded.title,
                    free_tier=excluded.free_tier,
                    usage_guide=excluded.usage_guide,
                    sharer=excluded.sharer
                """, (CHAT_ID, msg_id, cat, title, u_clean, free_tier, usage, sender, date, source_url))
                inserted += 1
            except Exception as e:
                pass
                
    conn.commit()
    
    count = c.execute("SELECT count(*) FROM free_resources WHERE chat_id=?", (CHAT_ID,)).fetchone()[0]
    print(f"人🐔局高价值白嫖资源库构建完毕，共收录精选资源: {count} 条")
    
    # 打印各分类数量
    for r in c.execute("SELECT category, count(*) FROM free_resources GROUP BY category"):
        print(f"  📁 {r[0]}: {r[1]} 条")
        
    print("\n精选样例展示：")
    sample = c.execute("SELECT category, title, url, free_tier, sharer, usage_guide FROM free_resources WHERE category != '实用工具与脚本' LIMIT 5").fetchall()
    for s in sample:
        print(f"[{s[0]}] {s[1]} | 分享人: {s[4]}")
        print(f"  🔗 {s[2]}")
        print(f"  🎁 白嫖方案: {s[3]}")
        print(f"  💡 实测心得: {s[5]}")
        print("-" * 50)
        
    conn.close()

if __name__ == "__main__":
    run()
