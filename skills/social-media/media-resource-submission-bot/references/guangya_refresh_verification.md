# 光鸭 Refresh Token 恢复与验证流程

用于排查 `401 Unauthorized`、`400 invalid_grant` 和“用户明明发过 refresh_token 但数据库没有”的情况。本文不保存任何真实 Token。

## 1. 先核对来源，不要凭数据库反推用户没发过

`cloud_configs.auth_token` 只代表当前保存值，可能被后续 `/setcloud`、迁移脚本或旧逻辑覆盖。数据库里只剩 JWT，不能证明用户没有提供过 `gy.` 刷新令牌。应先核对当前会话/Telegram 原始消息（如可检索），再检查数据库当前格式，并向用户准确说明“当前库里没有”，不要说“你没发过”。

## 2. 支持的保存格式

`GuangyaTransferAdapter.parse_auth_tokens()` 支持：

- JSON：`{"access_token":"...","refresh_token":"gy...."}`；
- 两段空格分隔的 access/refresh；
- 单独 JWT（只作 access_token）；
- 单独 `gy.` 字符串（只作 refresh_token）。

单独收到 `gy.` 时，解析结果应为 `(access_token=None, refresh_token=<value>)`，不能把它当作 JWT。

## 3. 正确的续期调用与持久化

`refresh_access_token` 是类方法，只接受字符串参数：

```python
access_token, refresh_token = GuangyaTransferAdapter.parse_auth_tokens(raw)
renewed = await GuangyaTransferAdapter.refresh_access_token(refresh_token)
```

不要把 `AsyncSession` 当作第一个参数传入；错误调用会出现 `'AsyncSession' object has no attribute 'strip'`。

续期成功后必须立即把返回的 access/refresh 成对保存为 JSON，提交事务，然后回读校验。刷新令牌可能轮换或一次性消费，不能在失败后无脑重复调用旧值，也不能只保存新的 access_token。

## 4. 最小真实验证闭环

1. 查询光鸭 `CloudConfig`，解析并确认存在 refresh_token；
2. 调用 `POST https://account.guangyapan.com/v1/auth/token`，payload 使用当前项目的 `client_id`、`grant_type=refresh_token` 和 refresh_token；
3. 成功后立刻提交新的 token pair；
4. 回读数据库，只比较是否一致、长度和是否存在，禁止打印完整凭证；
5. 用新 access_token 调用 `https://account.guangyapan.com/v1/user/me`，期望 HTTP 200；
6. 检查 `tg-media-bot.service` 为 `active`，再报告“续期链路正常”。

本流程已在生产 Oracle 主机上实测通过：续期返回 access/refresh，数据库回读一致，`/v1/user/me` 返回 HTTP 200，服务保持 active。测试输出不得泄露 Token。

## 5. 浏览器并发风险

光鸭网页端与 Bot 使用同一账号时，普通页面刷新是否有影响取决于前端是否调用刷新接口：

- 若只是读取页面、继续使用尚未过期的 access_token，通常不会影响 Bot；
- 退出登录、重新登录，或浏览器 access_token 过期后自动调用 SSO refresh，可能消费/轮换 refresh_token，使 Bot 保存的旧值失效；
- 因此不能向用户保证“刷新网页绝对不会影响”。Bot 续期成功后，应避免在网页端退出/重登录；若再次出现 `400 invalid_grant`，优先判断为浏览器或其他进程已刷新/轮换，而不是直接认定用户没有发送凭证。

## 6. 安全要求

真实 access_token、refresh_token 只能从数据库安全读取并在内存中使用；日志、测试输出、提交记录和技能文档只能输出布尔值、长度、前缀的极短脱敏信息，绝不写入完整 Token。