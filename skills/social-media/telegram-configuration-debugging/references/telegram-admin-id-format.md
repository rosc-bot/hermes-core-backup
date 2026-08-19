# Telegram 管理员 ID 格式与运行态验证

## 已验证的实现细节

Hermes 的斜杠命令权限解析会将管理员配置归一化为字符串 ID 集合：真正的 YAML 列表、单个数字和逗号分隔字符串都可被解析；但 CLI 传入的 `"[8586984520]"` 可能被保存为一个完整字符串。此时集合成员是 `"[8586984520]"`，而实际 Telegram 来源用户 ID 是 `"8586984520"`，两者不相等。

权限范围按聊天类型分离：私聊使用 `allow_admin_from`，群聊使用 `group_allow_admin_from`。因此两个字段都需要按需求设置。

## 复现与修复

错误形态：

```yaml
allow_admin_from: "[8586984520]"
```

推荐修复：

```bash
hermes config set platforms.telegram.extra.allow_admin_from 8586984520
hermes config set platforms.telegram.extra.group_allow_admin_from 8586984520
```

修复后检查 YAML 得到数字值或真正的列表，不应得到带方括号的字符串。

## 运行态验证

配置文件改变不会自动更新已有网关进程。重启后至少检查：

```bash
hermes gateway status
tail -n 80 ~/.hermes/logs/gateway.log
```

成功启动日志应包含 Telegram 已连接；随后使用之前被拒绝的命令进行实际验证。仅看到 `set_my_commands OK` 只能证明菜单注册成功，不能证明管理员权限成功。