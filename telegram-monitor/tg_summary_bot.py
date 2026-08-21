#!/usr/bin/env python3
"""Telegram 群聊总结标准库与格式生成器。"""

def make_link(chat_id: int, message_id: int) -> str:
    """生成标准可点击链接"""
    clean_id = str(chat_id).replace("-100", "")
    return f"https://t.me/c/{clean_id}/{message_id}"

def build_topic_block(title: str, items: list) -> str:
    """
    生成单个话题折叠块：
    title: "🎟️ 享境月卡与注册"
    items: [("第一条要点", "https://..."), ("第二条要点", "https://...")]
    """
    lines = [title]
    for i, item in enumerate(items):
        text, link = item
        link_str = f" [来源]({link})" if link else ""
        # 最后一条结尾加上 || 闭合折叠
        suffix = "||" if i == len(items) - 1 else ""
        lines.append(f" • {text}。{link_str}{suffix}")
    return "\n".join(lines)
