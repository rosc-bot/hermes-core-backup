User env: Linux server (AWS, UTC+8/Beijing), TG (如昔, 8586984520, replies in Chinese). Cron jobs dynamically follow default model (model/provider: null). Daily cron: 01:00 update, 02:00 cleanup, 08:00 emos check-in (to TG 8586984520).
§
Telegram user account monitor running: ✨Echo (@sjdhdhdhdhddhdhd) listens to 54 group chats via Telethon + systemd service (tg-monitor.service). DB at ~/.hermes/telegram-monitor/tg_messages.db. Query tool: tg_query.py. Skill: tg-group-summary.
§
User 要求 /model 切换默认永久保存（已配置 model.persist_switch_by_default: true）；--session/--once 仍为单次临时切换。
§
人🐔局专属白嫖知识库：自动监听入库群-1004495899387含URL消息，分类为AI中转/VPS节点/公益影视Emby/实用工具/源码项目，存储于tg_messages.db的free_resources表(FTS5)。支持“查白嫖 <关键词>”指令本地秒查(0 Token)。
§
Telegram 群聊人物花名册及全账号ID映射：
- 爸爸：如昔 (ID: 8586984520)
- J佬：@kaydenloo / jobr wu (ID: 7898049885)
- 凯哥：@kai202606 / 🔥凯 (ID: 874691304)
- 红猫：@lin2553_2 (ID: 6893069075)、@ailinda_2026 (ID: 8885279934)
- 五哥：@zjw120 (ID: 7996620779)、@zmz1008 (ID: 8903499998)
- 浮生：@jpnsmzx (ID: 8816894819)、@Joshua Chen (ID: 8450994308)、@xxxanxin (ID: 8490151918)、@muyuanan (ID: 8702625769)
- Blue：@YvZhen (ID: 8836652620)、@Blue_OvO (ID: 6811476464)
- L：@mumu1864 (ID: 8933275763)
- 阿昔：@axixiansheng (ID: 5301711218)
- 挽歌：@wangekunleo (ID: 1558880868)
- 汤姆：@jiamian555 (ID: 8710426674)
- 小新：@sudo_chmod_x / 𝙜𝙤 (ID: 1911121963)
§
GitHub: rosc-bot (1399373278@qq.com), repo: rosc-bot/hermes-core-backup. Server: 2GB Swap.
§
HK/NL/DEG Servers: ed25519 direct access configured. Default SOCKS/Reality ports. tgsocks/tgpass888.
§
自学习与技能维护原则：群聊总结格式已固化为10大要素结构化大档案版（<details><summary>主题N｜具体事件），后台自我反思与自学习程序严禁擅自修改或退化此格式。
§
User expects the AI to NEVER proactively add unrequested domains/servers to config files. Only add what is explicitly requested.
§
emos.best 公益服签到系统：TG 机器人 @qiandao00_bot (systemd emos-bot.service)，对接官方 @emospg_bot OAuth 回跳授权，支持每日 08:00 随机寄语签到(content<=10字冲最高5萝卜)并私聊推送。DB: ~/.hermes/emos_users.db，脚本: ~/.hermes/scripts/emos_sign.py。
§
Telegram Bot 开发与维护规范：新增/修改机器人命令时，必须通过 set_my_commands 自动将命令列表同步注册至 Telegram 官方底部命令菜单，确保用户端输入/时自动补全并回显中文说明。