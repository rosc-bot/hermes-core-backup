# 案例：gemini-3.7-flash-high 间歇性 400 INVALID_ARGUMENT（2026-08-31）

## 背景

Hermes 报 "The model provider failed after retries"。请求链路：Hermes → 本地 CPA(8317, 7.2.146) → Google Antigravity OAuth 账号（`daily-cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse`）。

- Hermes 侧 provider 配置（`~/.hermes/config.yaml`）：`name: gemini`，`base_url: http://127.0.0.1:8317/v1`，`api_mode: chat_completions`，模型如 `gemini-3.7-flash-high`。
- CPA routing: `round-robin`，`max-retry-credentials: 0`（失败不会自动换账号重试）。

## 失败请求的特征（从 error log 提取）

顶层参数：`messages / model / max_tokens=65536 / stream / stream_options{include_usage} / tools(24个)`。
消息序列：system(23675字符) → user → assistant(tool_calls) → tool → assistant(tool_calls) → tool。

## 排查流程与关键结论

1. 单测各参数（max_tokens=65536、stream+include_usage、单个 tool、组合）→ 全部 200。
2. 原样重放失败请求 → 复现 400。
3. 二分：删 tools→200；删 assistant.tool_calls（保留 tool 消息）→200；删 tool 消息（保留 tool_calls）→400 —— **tool_calls 与 tool 消息不配对时上游必 400，属正常行为**。
4. 最小两轮 tool_calls 结构 → 200；最小 + 原 24 tools → 200；最小 + 原 system → 200；最小 + 原消息 → 200；原样但 user 换 "hi" → 200。
5. 原样请求连续 9 次重放（18:31 后）→ 全部 200。**结论：参数全部合规，400 是上游（Google Antigravity）间歇性抖动**，18:25~18:31 窗口期故障，之后自行恢复。

## 教训（下次直接套用）

- **间歇性 400 的判定法**：同一失败请求连续重放 3~6 次，全 200 即上游抖动，重试即可，勿改配置。
- 升级 CPA 二进制后首个时间段出现的偶发 400，优先怀疑上游/账号状态，不要先怀疑请求参数。
- `user` 消息若含图片（image_url）等多媒体内容，是 400 的高危嫌疑，先换纯文本验证。

## Antigravity auth 文件字段（auths/antigravity-<email>.json）

```json
{"access_token": "...", "refresh_token": "...", "email": "...",
 "timestamp": 1788172021307,   // ⚠ 毫秒，不是秒！
 "expires_in": 3599,           // 秒
 "expired": "2026-08-31T19:27:00+08:00", "disabled": false,
 "project_id": "...", "type": "oauth"}
```

到期时间 = `timestamp(ms) + expires_in * 1000`。`disabled: true` 可临时剔除嫌疑账号（改前需用户确认）。

## 本机现状（2026-08-31）

- CPA 二进制 7.2.146（备份 `cli-proxy-api.bak-7.2.132`），`cpa.service` systemd + `cpa-wrapper.sh`。
- 两个 Antigravity OAuth 账号 round-robin：`ranxin74@gmail.com`、`queen.bry.91277@gmail.com`（均 OAuth type，token 小时级过期自动刷新）。
- `main.log` 在升级后出现 "bind: address already in use" 循环噪音：wrapper/systemd 瞬时竞争，端口在监听且 `/v1/models` 200 即忽略。
