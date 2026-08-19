# Telegram 访问控制会话参考

## 本次验证到的关键实现

- Telegram 适配器已有 `_should_process_message()`：群聊在 `require_mention` 开启时接受 @机器人、回复机器人消息或配置的 mention pattern。
- `guest_mode` 会让非白名单群通过直接 @提及绕过聊天白名单；若目标是严格权限边界，应关闭它。
- `_is_user_authorized_from_message()` 会分别读取群聊的 `group_allow_from` 与私聊的 `allow_from`。
- `allow_admin_from` 和 `group_allow_admin_from` 是管理员/斜杠命令权限边界，不等价于普通消息触发门控。
- 当前源码允许 `custom_menu` 通过 Telegram adapter 的 `config.extra` 持久化，并由 post-connect housekeeping 注册。

## 重启陷阱

若当前 shell 就是网关进程的执行上下文，执行 `hermes gateway restart` 会被保护逻辑拦截，避免父进程杀死自身。必须从网关外部执行重启，例如单独 SSH/shell、systemd 服务或独立管理会话。

因此报告状态时分为：

1. 配置文件已写入；
2. 配置检查通过；
3. 网关是否已重新加载；
4. 运行态是否只有一个实例。

不要把第 1、2 项冒充第 3 项。
