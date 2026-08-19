User prefers cron jobs to NOT pin a specific model/provider — they should dynamically follow the currently configured default model at runtime (model: null, provider: null in cron job config).
§
User's server timezone is set to Asia/Shanghai (Beijing time, UTC+8) — both system and Hermes config. Use Beijing time when reporting times.
§
User runs Hermes on a Linux server (Ubuntu/AWS), gateway connected to Telegram (user 如昔, id 8586984520). Prefers Hermes replies in Chinese via Telegram.
§
User has daily cron jobs: 01:00 security check+update, 02:00 junk cleanup — both deliver reports to Telegram chat 8586984520.
§
Telegram user account monitor running: ✨Echo (@sjdhdhdhdhddhdhd) listens to 54 group chats via Telethon + systemd service (tg-monitor.service). DB at ~/.hermes/telegram-monitor/tg_messages.db. Query tool: tg_query.py. Skill: tg-group-summary.
§
User 要求 /model 切换默认永久保存（已配置 model.persist_switch_by_default: true）；--session/--once 仍为单次临时切换。
§
服务器 156.245.245.172（香港🐔，Debian 13/2核/2G内存/79G盘，主机名 serBnTOjmSJtG），root 密码 ysvgYWFA2615，已配置本机 ed25519 密钥免密登录，ssh root@156.245.245.172 直连。
§
服务器 199.47.241.137（荷兰🐔，公网，SSH 端口 20022，root 密码 EowWxF#051ByrME5，Debian 13/1核/488M内存/1.3G盘，主机名 u5799-n9166lm9），已配置本机 ed25519 免密登录，ssh -p 20022 root@199.47.241.137 直连。已部署 TG SOCKS5 代理（端口 30810，账号 tgsocks / tgpass888，xray 统一托管自启）。
§
香港🐔 (156.245.245.172) 已部署 TG SOCKS5 代理（端口 443，账号 tgsocks / tgpass888，xray 统一托管自启）。
§
服务器 161.33.147.125（joey🐔，端口 14895，规格 256M/512M/0.5核，映射 14896->80, 14897->443, 14898->8080, 14899->8443），当前状态 stopped。
§
Telegram 群聊人物花名册及全账号ID映射：
- 爸爸：如昔 (ID: 8586984520)
- 红猫：@lin2553_2 (ID: 6893069075)、@ailinda_2026 (ID: 8885279934)
- 五哥：@zjw120 (ID: 7996620779)、@zmz1008 (ID: 8903499998)
- 浮生：@jpnsmzx (ID: 8816894819)、@Joshua Chen (ID: 8450994308)、@xxxanxin (ID: 8490151918)、@muyuanan (ID: 8702625769)
- Blue：@YvZhen (ID: 8836652620)、@Blue_OvO (ID: 6811476464)
- J佬：@kaydenloo (ID: 7898049885)
- L：@mumu1864 (ID: 8933275763)
- 阿昔：@axixiansheng (ID: 5301711218)
- 挽歌：@wangekunleo (ID: 1558880868)
- 汤姆：@jiamian555 (ID: 8710426674)
- 小新：@sudo_chmod_x (ID: 5603531305)