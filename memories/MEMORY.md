环境：Linux AWS，UTC+8；常州(电信宽带+联通/电信双卡)；定时任务: 01:00安全检查, 01:30 Hermes更新, 02:00清理；系统更新备份策略已固化: updates.backup_keep=1 (仅保留最新一个 pre-update 备份)；严肃写大项目必须首选 gemini-pro-agent (High) 绝不取巧忽悠。
§
Telegram user account monitor running: ✨Echo (@sjdhdhdhdhddhdhd) listens to 54 group chats via Docker Compose (telegram-group-monitor, /home/ubuntu/telegram-monitor-docker). DB at ./data/tg_messages.db. Query tool: tg_query.py. Skill: tg-group-summary.
§
User要求/model默认永久生效(--session/--once临时)。kiss(ID:8205552469,小号:8147345662)。
§
TG Q图贴纸过塑(/q-api 4888): Docker Compose (quote-api-service, /home/ubuntu/quote-api). 严守原版纯q触发(严禁擅加斜杠/), 支持群聊回复q私聊确认生成。已支持管理员身份/自定义头衔标签识别与TG会员Custom Emoji表情渲染。未授权严禁私自修改已有行为。
§
GitHub API：用户的私有仓库同步优先使用安全 REST API；Oracle `~/.config/github/token`（权限 600）为长期配置，同步后保留，不删除、不清理、不要求重复配置；不复用已暴露 PAT。
§
Server SSH: TW(45.207.153.154:58085 root), HK(156.245.245.172:22 root), NL(199.47.241.137:20020/22), Oracle(168.107.67.72); ed25519免密。Swap: 2GB。已删除日本小鸡(161.33.147.125)。台湾专线: TG S5(29759), VLESS-Reality(36709)。
§
自学习与技能维护：群聊总结格式已固化为10大要素结构化Details版，反思与自学习严禁擅改退化。
§
Surfing/Mihomo配置规范: 强制redir-host(保证黑白名单有效), 禁ipv6防转圈, tolerance:50, sniffer覆盖Claude/OpenAI防403, 阿里+腾讯DoH, Emby严格排除港日。未授权绝不擅改。
§
emos.best 公益服签到系统：TG 机器人 @qiandao00_bot 已迁移至 Docker Compose 容器运行 (emos-checkin-bot, /home/ubuntu/emos-bot-docker)，对接官方 @emospg_bot OAuth 回跳授权，支持每日 08:00 随机寄语签到(content<=10字冲最高5萝卜)并私聊推送。DB挂载: ./data/emos_users.db。
§
Telegram Bot 开发与维护规范：新增/修改机器人命令时，必须通过 set_my_commands 自动将命令列表同步注册至 Telegram 官方底部命令菜单，确保用户端输入/时自动补全并回显中文说明。
§
影视资源投稿Bot(@zhuancun001_bot, tg-media-bot.service): Oracle(168.107.67.72)。库rosc-bot/tg-media-submission-bot。光鸭(-1004387965244),移动(-1004410413711)。WebUI(12082):严禁setInterval自动刷新导致DOM闪缩/状态丢失; 需精准校验真实网盘folder_id才确认为已转存; 移动端防flex截断关键信息; 使用动态二级分类(如华语电影)筛选。群(@shangpian888)静默仅推榜。管理员:8586984520。
§
质量严谨与端口铁律：必须真实运行态端到端验证(查依赖/路由/日志)。工具执行策略: approvals.mode=off 全自动免审批放行。AWS已放行端口: TCP[22(SSH), 80(空闲), 443(空闲), 2082(MediaBot WebUI), 3000(空闲), 8317(CPA), 8648(HermesUI), 12666(OpenList), 35087(Xray), 39637(空闲)]; UDP[29657, 61242, 35087]。新服务严禁新开端口，必须直接从空闲端口选用。
§
用户偏好：代码修复集中成批完成，在工具调用接近上限前统一测试、提交、同步并重启一次，避免每个小修复重复部署；已运行且未变化的服务无需重复重启。