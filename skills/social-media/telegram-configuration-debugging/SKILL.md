---
name: telegram-configuration-debugging
description: "排查 Telegram Hermes 配置未生效、命令权限和网关运行态问题。"
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [telegram, hermes, configuration, debugging, authorization, gateway]
    related_skills: [telegram-access-control, telegram-gateway-operations]
---

# Telegram Hermes 配置故障排查

## 适用场景

- Telegram Bot 提示用户没有管理员权限。
- `/model`、`/new`、`/sethome` 等斜杠命令被错误拒绝。
- 本地配置看似正确，但运行中的网关仍使用旧权限。
- 修改 Telegram 显示设置、菜单或访问控制后需要验证运行态。

## 标准排查流程

1. 先读取当前 Telegram 配置和网关状态，确认 profile、配置文件和运行实例。
2. 检查 `platforms.telegram.extra` 中的 `allow_admin_from` 和 `group_allow_admin_from`。私聊和群聊是两个独立权限范围；私聊管理员不自动等于群聊管理员。
3. 使用 Telegram 数字 user ID，不使用昵称、显示名或群名称。
4. 使用 `hermes config set` 写入单个 ID 时，传入裸数字：

```bash
hermes config set platforms.telegram.extra.allow_admin_from 8586984520
hermes config set platforms.telegram.extra.group_allow_admin_from 8586984520
```

5. 重新用 YAML 解析器读取配置，确认值不是字符串形式的方括号，例如 `"[8586984520]"`。这种值会被权限归一化逻辑当作一个完整字符串，而不是 ID 列表成员；结果就是管理员被判为非管理员。
6. 如果使用列表，必须让 YAML 实际解析为列表，而不是把列表字面量作为 CLI 字符串传入。单个裸数字最不容易出错。
7. 从网关进程外部重启。手动运行时使用：

```bash
hermes gateway stop
sleep 2
hermes gateway run --replace
```

若网关由 systemd 管理，则使用对应服务重启；不要在网关自身处理消息的进程中重启自己。
8. 用 `hermes gateway status` 确认只有一个实例运行。
9. 检查启动日志，确认 Telegram 已连接；再用实际命令（如 `/model` 或 `/new`）验证权限，而不是只依据配置文件。

## 权限模型要点

- `allow_admin_from` 控制私聊范围的完整斜杠命令权限。
- `group_allow_admin_from` 控制群聊范围的完整斜杠命令权限。
- `require_mention` 只控制群聊触发方式，不授予管理员权限。
- `group_policy: open` 只表示群消息允许进入适配器，不等于发送者是管理员。
- 普通聊天消息与斜杠命令门控分离；非管理员仍可能正常聊天，但会被拒绝未授权的斜杠命令。

## 验证与报告

必须区分三种状态：配置已写入、网关已加载、实际命令已通过。最终报告只能声称已由工具验证的状态。不要把“重启命令已执行”直接等同于“权限已恢复”；至少确认网关单实例运行和新的 Telegram 连接日志。

## 参考资料

- `references/telegram-admin-id-format.md`：管理员 ID 格式陷阱、源码解析规则和复现验证要点。

## 重叠技能说明

本技能与 `telegram-access-control`、`telegram-gateway-operations` 有交叉：前两者负责长期权限/运营配置，本技能聚焦配置解析错误、运行态重载和权限拒绝的诊断。