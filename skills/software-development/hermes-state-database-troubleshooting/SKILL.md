---
name: hermes-state-database-troubleshooting
description: "排查并验证 Hermes 会话数据库完整性、权限与检索链路。"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, sqlite, sessions, database, troubleshooting, permissions]
    related_skills: [systematic-debugging, hermes-agent]
---

# Hermes 会话数据库排查与修复

## 适用场景

当 Hermes 报告会话数据库损坏、只读、索引异常，或修复后需要确认是否真正恢复时使用。本技能覆盖三层状态：SQLite 数据完整性、运行用户写权限、Hermes 应用层会话检索。

## When to Use

Use when Hermes session search reports database corruption, read-only access, index errors, or when a repaired session database needs an end-to-end verification.

## 核心原则

“数据库能读”不等于“数据库已修复”。必须分别验证完整性、权限和应用层检索，最后才向用户报告修复结果。

## 标准流程

1. **定位范围**
   - 确认实际 Hermes 主目录和正式库，通常是 `~/.hermes/state.db`。
   - 同时列出修复副本、WAL/SHM 文件和相关日志；不要凭文件名直接覆盖正式库。

2. **建立可重复的健康检查**
   - 对正式库和候选副本执行 `PRAGMA integrity_check`，期望结果为 `ok`。
   - 查询表结构和关键表记录数，至少确认 `sessions`、`messages` 及 FTS 表存在且可读。
   - 对候选副本核对大小、时间戳和 SHA-256；内容未确认前不要替换正式库。

3. **核对进程身份与权限**
   - 检查实际运行 Hermes 网关的用户，以及 `state.db` 的 owner/mode。
   - 若修复命令由 root 执行，数据库可能变成 root-owned，导致普通用户可以读取但无法维护索引。
   - 将数据库交还给 Hermes 运行用户，并设置最小必要权限（通常为 owner 可读写、其他用户无权限，例如 `0600`）。仅在用户明确要求时扩大权限。

4. **验证可写性但不改业务数据**
   - 使用 SQLite `BEGIN IMMEDIATE` 后立即 `ROLLBACK` 作为写权限探针。
   - 这比只检查 Unix mode 更可靠，因为还会暴露锁、只读挂载或 SQLite 打开问题。

5. **端到端验证**
   - 通过 Hermes 自身的会话检索或浏览功能查询最近会话/已知关键词。
   - 只有 SQLite 检查、没有应用层检索成功时，只能报告“数据库文件完整”，不能报告“会话功能已恢复”。

6. **报告分层结果**
   - 数据完整性：`ok` 或具体错误。
   - 写权限：事务性写探针是否通过，owner/mode 是什么。
   - 应用层：Hermes 会话检索是否成功。
   - 若三项都通过，才可称为已修复；若只有前两项通过，应明确说明剩余链路。

## 常见陷阱

- `PRAGMA integrity_check = ok` 不证明 Hermes 的 FTS/会话检索链路可用。
- 修复工具以 root 运行后留下 root-owned 数据库，是“能读但不能正常维护索引”的典型假修复状态。
- 不要把修复副本与正式库相同的大小或哈希误当作权限已经正确；权限必须单独核验。
- 不要在修复前重启或停止正在运行的 Hermes 网关；先完成只读诊断，涉及服务生命周期时使用 Hermes 官方命令并遵守当前运行环境的限制。

## 修复过程中的注意事项

### 当当前会话由 Hermes 网关托管时

停止网关会同时中断当前会话，导致修复操作无法继续。此时有两种方式在独立终端执行修复：

1. **使用 `systemd-run` 启动一次性维护单元**（推荐）：
   ```bash
   sudo systemd-run --unit=hermes-db-repair --collect \
     --property=Type=oneshot \
     /path/to/repair_script.sh
   ```
   该单元在独立 cgroup 中运行，不受网关进程树影响。

2. **使用 `delegate_task` 分派给子代理**：
   子代理有独立的终端会话，但需注意父代理的数据库也处于损坏状态时，子代理可能继承相同错误。

### 修复后的权限修正

以 `sudo` 或 `systemd-run` 执行的修复命令，产物通常由 `root:root` 持有，导致 Hermes 运行用户（通常为 `ubuntu`）虽然能读取数据库，但无法写入 FTS 索引，造成会话检索功能不可用。修复后必须执行：

```bash
sudo chown <运行用户>:<运行用户> state.db
sudo chmod 600 state.db
```

然后通过 `session_search()` 浏览或搜索验证应用层检索功能真正恢复。

## 已验证的参考记录

- `references/hermes-state-db-repair.md`：SQLite 完整性、root-owned 修复产物、事务写探针和 Hermes 会话检索的验证要点。
- `scripts/recover_sqlite.py`：当 `sqlite3` CLI 命令不可用时，用 Python 替代执行 SQLite `.recover` 的脚本。

## 完整修复工作流

当数据库确认损坏时，按以下步骤执行修复：

1. **停止网关**（如果当前会话由网关托管，使用独立终端或 systemd-run 执行）
2. **备份原库**：`cp -a state.db "state.db.before-repair-$(date +%Y%m%d_%H%M%S)"`
3. **使用 SQLite 的 `.recover` 命令重建**：
   ```bash
   sqlite3 state.db ".recover" | sqlite3 recovered.db
   ```
   （如果系统没有 `sqlite3` 命令，可用 `python3 -c "import sqlite3; ..."` 替代）
4. **验证修复副本**：
   - `PRAGMA integrity_check` → `ok`
   - 比较表结构、表数量、记录数与原库一致
   - 比较 SHA-256 哈希（修复后内容应不同，说明数据被真正重建了）
5. **替换正式库**：`mv recovered.db state.db`
6. **修复权限**：`chown <运行用户>:<运行用户> state.db && chmod 600 state.db`
   - 修复由 root 或 sudo 执行时，产物拥有者会变成 root，导致 Hermes 能读但无法维护索引
7. **重启网关**，然后用 `session_search()` 浏览或搜索验证会话检索功能

## 完成标准

必须有真实工具输出支撑，至少包括：`integrity_check`、权限/owner、写探针、Hermes 会话检索四项结果。禁止用“看起来正常”替代验证。
