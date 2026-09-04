# Remote Sync Truthfulness & Green-Batch Handoff

用于 `tg-media-submission-bot` 的分批发布、远端同步和生产重启，避免把本地成功误报成远端或生产成功。

## Green-batch sequence

当操作方要求“测试成功后先同步并重启，再继续剩余任务”时，严格按以下顺序执行：

1. 明确本批次已经通过的文件范围；只选择性暂存这些文件，禁止 `git add .`。
2. 在本地执行对应的 focused tests，并记录实际返回值。
3. 只同步本批次 intended 文件；同步前排除 `.env`、Token、Cookie、私钥、数据库导出和其他敏感文件。
4. 在目标机按同步文件范围运行 focused tests，确认部署内容确实可执行。
5. 重启 `tg-media-bot.service`，随后验证 `active/running`、新 MainPID、监听端口、认证后的 `/health` 与关键 API，以及最新 polling 日志。
6. 只有以上运行态核验完成后，才继续处理下一批未完成修改；后续修改完成后仍须执行一次独立的最终全量门禁。

不要为了形式重复已经与本批次无关的完整测试；但任何后续代码、迁移、依赖或配置变化都必须重新覆盖其影响范围。

## Three independent completion claims

- **Local commit**：用 `git status`、提交记录和 `git diff --check` 验证；只说明本地版本库已提交。
- **Remote synchronization**：使用安全的现有认证来源访问私有仓库，并读回目标 ref/commit SHA 验证；不能只依据 push/API 的成功响应。
- **Production rollout**：用 systemd、端口、健康接口、关键 API 和新鲜日志验证；不能只依据 SSH 命令退出码或 restart 命令返回。

如果私有 GitHub 仓库在没有认证时返回 `404`，应按“未完成远端同步”处理，而不是按仓库不存在或同步成功处理。没有安全认证来源时，停止在已验证的本地提交和生产状态，并明确报告远端未同步。

## Credential and reporting boundary

绝不读取、打印、复用历史中暴露的 PAT；不要把 Token 放进 URL、命令参数、日志、提交历史或报告。远端验证优先使用已登录的 `gh`、安全 credential helper 或受控 API 认证；认证缺失时不要猜凭据，也不要声称已经完成 GitHub 同步。
