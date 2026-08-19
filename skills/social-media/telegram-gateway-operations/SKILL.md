---
name: telegram-gateway-operations
description: "配置 Telegram 网关、菜单、静默回复和中文 Rich Message 工作流。"
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [telegram, gateway, bot-menu, rich-message, chinese, tool-progress]
    related_skills: [telegram-user-monitor, tg-group-summary, telegram-access-control]
---

# Telegram 网关运营与消息呈现

## When to Use

- 用户要求修改 Telegram Bot 命令菜单
- 用户要求 Telegram 只显示最终正文、不显示工具调用或中间状态
- 用户要求中文、可展开 Rich Message、来源链接的群聊总结
- 用户要求配置 Telegram 网关行为、重启后验证或检查菜单是否生效
- 用户要求设置群聊触发规则（@提及/回复门控）
- 配置群聊不对主页频道提示

## 核心用户偏好

- **硬性要求：除代码本身外，所有回复、说明、状态、错误信息、模型切换提示、系统通知必须使用中文。严禁直接输出任何英文内容。** 用户只看得懂中文，这是最高优先级规则。
- Telegram Bot 直接发送最终正文；不显示工具调用、工具参数、思考过程、处理中间消息、运行状态或心跳。
- 群聊总结按话题组织，使用相互独立的 `<blockquote expandable>` 折叠块；每条重要信息附原始 Telegram 消息来源；`最终总结：` 或 `📋 结论与行动` 必须放在最后。
- 不使用 Markdown 表格、代码框、标题符号、粗体或斜体作为总结正文的额外格式。
- 定时任务和后台任务不固定模型，动态跟随运行时当前默认模型。
- 所有时间报告使用北京时间（Asia/Shanghai, +08:00）。

## Telegram 静默正文配置

通过 Hermes 配置设置 Telegram 平台级显示选项：

```yaml
display:
  platforms:
    telegram:
      tool_progress: false
      interim_assistant_messages: false
      long_running_notifications: false
      busy_ack_detail: false
      live_status: false
```

使用 `hermes config set` 写入配置后，重启网关：

```bash
hermes config set display.platforms.telegram.tool_progress off
hermes config set display.platforms.telegram.interim_assistant_messages false
hermes config set display.platforms.telegram.long_running_notifications false
hermes config set display.platforms.telegram.busy_ack_detail false
hermes config set display.platforms.telegram.live_status off
hermes gateway stop
hermes gateway run   # 应使用后台进程或服务方式运行
```

注意：`tool_progress: off` 只关闭工具调用进度；要实现"只发最终正文"，还必须关闭 `interim_assistant_messages` 和 `long_running_notifications`。`live_status` 独立于工具进度，也要关闭。

## 自定义 Telegram Bot 菜单

用户要求菜单只显示指定命令时，使用 Telegram Bot API 的 `setMyCommands` 立即设置，并在 Hermes 网关的 Telegram 配置中持久化自定义菜单。配置结构应位于 Telegram 平台的 `extra` 中（旧版本可能要求 `telegram:` 配置通过插件桥接到 `extra`）：

```yaml
telegram:
  extra:
    custom_menu:
      - command: start
        description: 开始新的对话
      - command: new
        description: 开始新对话（清除记忆）
      - command: compact
        description: 压缩对话记忆
      - command: clear
        description: 清除对话历史
      - command: history
        description: 查看对话历史
      - command: model
        description: 查看或切换AI模型
      - command: stop
        description: 停止当前任务
```

如果当前 Hermes 版本的插件配置接受扁平 Telegram 键，也可使用等价的 `telegram.custom_menu`，但必须确认加载路径；不要把 `custom_menu` 错放在顶层 `timezone` 后面导致 YAML 层级错误。

注册后验证：

```bash
TOKEN=$(grep TELEGRAM_BOT_TOKEN ~/.hermes/.env | cut -d= -f2-)
curl -s "https://api.telegram.org/bot${TOKEN}/getMyCommands"
```

验证结果必须只包含用户指定的命令。网关重启后再次验证，因为网关的 post-connect housekeeping 可能重新调用 `set_my_commands` 并覆盖手工菜单。

## Rich Message 总结规范

模型输出应类似：

```text
📊 {群聊名称} 群聊总结 — {时间范围}

话题：{具体话题}
<blockquote expandable>
• 关键事实、讨论和结果。[来源](https://t.me/...)
• 另一条信息或观点。[来源](https://t.me/...)
</blockquote>

重要互动：
<blockquote expandable>
• 重要互动内容。[来源](https://t.me/...)
</blockquote>

零散信息：
<blockquote expandable>
• 零散信息。[来源](https://t.me/...)
</blockquote>

时间线梳理：
<blockquote expandable>
• 时间线事件。[来源](https://t.me/...)
</blockquote>

最终总结：
<blockquote expandable>
总结和行动建议。
</blockquote>
```

每个栏目都必须有自己的折叠块，不能把所有栏目包在一个总块中。优先使用 Telegram 原生 Rich Message；失败时按 Rich Message → HTML → 纯文本顺序回退。私密群无法生成公开 `t.me/username/message_id` 链接时，明确标注群名和消息 ID，不伪造链接。

## 群聊触发规则

群聊需要配置为只在 @机器人或回复机器人消息时响应：

```yaml
telegram:
  require_mention: true
  guest_mode: false
  exclusive_bot_mentions: true
  mention_patterns: []
```

同时需要配置管理员权限边界：

```yaml
platforms:
  telegram:
    extra:
      allow_admin_from:
        - 8586984520
      group_allow_admin_from:
        - 8586984520
```

详细配置参见 `telegram-access-control` 技能，包括群聊身份称呼、唯一最高权限用户和抗诱导要求。

## 群聊主页频道提示

群聊首次响应时，Hermes 网关会检查"是否设置了主页频道"，如果未设置则发送提示。群聊、超级群组和论坛话题不应收到此提示。

修复方法：修改网关源码 `gateway/run.py` 中的首次消息处理逻辑，在检查主页频道时排除 `chat_type` 为 `group`、`forum` 或 `channel` 的来源。

```python
# 在判断是否显示主页频道提示的逻辑中，添加：
if getattr(source, "chat_type", "dm") not in {"group", "forum", "channel"}:
    # 只有私聊才显示主页频道提示
```

修改后执行 Python 语法检查，并从网关外部重启。

## 验证与故障排查

1. 使用 YAML 解析器验证配置能正常加载，重点检查 `telegram`、`display`、`timezone` 的缩进。
2. 重启网关后运行 `hermes gateway status`，确认只有一个实例在运行。
3. 调用 `getMyCommands` 验证菜单实际值，而不是只查看本地 YAML。
4. 若菜单被恢复为默认大量命令，检查网关 post-connect 注册逻辑是否读取自定义菜单；必要时在 Telegram 插件中让 `custom_menu` 进入 `PlatformConfig.extra`，并重启后复验。
5. 不要向用户展示工具调用过程；工具输出只用于内部验证，最终回复简明说明完成状态和验证结果。
6. 所有面向用户的输出必须使用中文。如果框架自带的系统消息（如模型选择菜单、配置提示）是英文的，不要直接转发给用户，而是先翻译或用命令绕过。
7. 排查英文系统提示时，先用 `hermes config get display.language` 验证语言配置；即使返回 `zh-CN`，`Session reset`、`Switched to fallback model` 等核心状态提示仍可能是未本地化的固定文案。应明确区分“模型/助手回复语言”和“框架生成的系统 UI 文案”，不要误称个人设置失效；向用户解释时直接给出中文含义。
8. **内部技能维护通知（如"Self-improvement review: Skill created"）也是英文固定文案，同样不受 `display.language` 控制。** 用户明确要求此类内部维护/自我改进结果不要主动发到聊天里，若无法完全静默抑制，必须第一时间将其翻译为中文并给出简明说明。
9. **`hermes update` 后 Telegram 菜单被默认全量英文命令覆盖的根因与修复：**
   - 官方最新 Telegram 适配器在连接建立时，默认调用 `telegram_menu_commands(max_commands=60)` 获取全量 60 个内置英文命令并执行 `set_my_commands` 覆盖所有 scopes。
   - 必须在 `plugins/platforms/telegram/adapter.py` 的 post-connect 逻辑中加入对 `platforms.telegram.extra.custom_menu` 的显式判断与转换，若存在自定义菜单则优先注册自定义 `BotCommand` 列表。
   - 代码修补后可使用独立 Python 脚本通过 `telegram.Bot(token).set_my_commands` 针对 `BotCommandScopeDefault`、`BotCommandScopeAllPrivateChats`、`BotCommandScopeAllGroupChats` 立即同步并复验。

## 安装为 systemd 系统服务

### 安装步骤

```bash
sudo hermes gateway install --system --run-as-user ubuntu --start-now
```

### 已知陷阱：旧手动进程阻塞

如果之前已经手动运行过 `hermes gateway run`（例如通过启动脚本或直接执行），该旧进程仍在监听端口，会导致新安装的 systemd 服务启动失败。日志中会出现：

```
❌ Gateway already running (PID 135502).
```

**⚠️ 重要：`hermes gateway stop` 无法从网关内部执行。** 如果在 Hermes 会话中尝试停止网关，系统会拦截并报错 `Blocked: command cannot restart or stop the gateway from inside the gateway process`。必须使用独立终端或 SSH 会话执行以下操作。

**解决方法**：在独立终端中先终止旧进程，再让 systemd 接管：

```bash
# 1. 找到旧进程 PID
ps aux | grep 'hermes.*gateway run'

# 2. 终止旧进程
kill <PID>

# 3. 重置 systemd 服务的失败计数（避免 Auto-restart loop）
sudo systemctl reset-failed hermes-gateway.service

# 4. 启动 systemd 服务
sudo systemctl restart hermes-gateway.service

# 5. 验证
sudo hermes gateway status --system
```

安装后，systemd 服务会以 `enabled` 状态开机自启，不再需要 systemd linger 或手动登录。`journalctl -u hermes-gateway.service -f` 可查看实时日志。

## 相关技能

- `telegram-access-control`：群聊触发门控、管理员权限、身份称呼和抗诱导配置。
- `telegram-user-monitor`：Telethon 用户账号监听、SQLite 归档和查询。
- `tg-group-summary`：群聊消息查询和中文总结模板；该技能可能是用户拥有的旧版规范，修改前先确认其所有权。