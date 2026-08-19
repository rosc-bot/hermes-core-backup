# Telegram 网关本次会话验证要点

## 已验证的静默回复配置

`display.platforms.telegram` 下关闭以下五项，可让 Telegram 只显示最终正文：

- `tool_progress: false`
- `interim_assistant_messages: false`
- `long_running_notifications: false`
- `busy_ack_detail: false`
- `live_status: false`

其中 `live_status` 独立于 `tool_progress`；只关闭工具进度并不足以隐藏所有中间状态。

## 菜单持久化的实现要点

Telegram 的 Bot API `setMyCommands` 可立即验证，但 Hermes 网关启动后的 post-connect housekeeping 会再次注册菜单。因此持久化配置必须被 Telegram 插件加载到 `PlatformConfig.extra`，否则重启后可能恢复默认菜单。

本次实现为 Telegram adapter 增加了 `custom_menu` 分支：如果 `self.config.extra["custom_menu"]` 存在，则使用它取代中央 `COMMAND_REGISTRY` 生成的菜单；同时在 `_apply_yaml_config` 的 Telegram extra 透传键中加入 `custom_menu`。这类修改后要清除相关 `__pycache__`、重启网关，并通过 `getMyCommands` 验证。

## YAML 层级陷阱

`custom_menu` 必须位于 `telegram` 配置块内部，不能追加在顶层 `timezone` 行之后。错误缩进会造成重复 `telegram` 键或把 `custom_menu` 置于错误层级；写入后务必用 YAML 解析读取 `telegram` 节点确认结构。