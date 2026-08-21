---
name: human-chicken-free-kb
description: "检索人🐔局（执着白嫖）专属白嫖资源、免费节点、API与使用方案知识库。"
version: 1.0.0
author: Hermes Agent
---

# 人🐔局专属白嫖资源库技能

## 概述
人🐔局群聊（`-1004495899387`）沉淀了大量群友分享的免费 VPS、AI 接口、公益 Emby、开源项目及实测使用心得。本技能用于秒级调取和结构化呈现。

## 调取方式
当用户询问：
- `查白嫖 [关键词]`（如 `查白嫖 vps`、`查白嫖 api`、`查白嫖 emby`）
- `人🐔局白嫖资源`
- `群里分享过什么免费/便宜的节点/API`

在终端执行查询工具：
```bash
python3 /home/ubuntu/.hermes/telegram-monitor/query_kb.py "<关键词>"
```

并将输出的 Telegram 原生 `<details><summary>` 折叠块直接呈现给用户。
