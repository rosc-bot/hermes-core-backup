# Restart-Safe Auto-Transfer Recovery Runbook

适用于 Telegram 投稿审核后触发云盘自动转存的服务。核心原则：**Telegram 文案是展示状态，数据库 TransferJob 才是恢复事实；restore_share 前的持久化栅栏决定重启后能否重放。**

## Durable state contract

为每个 `submission_group_id` 建立唯一 `transfer_jobs` 行，至少保存：

- `task_id`、`cloud_name`、`status`、`attempt_count`、`last_error`；
- `target_folder_id` 与标准目录名；
- 精确的 `expected_file_names`；
- `remote_task_id`、`restore_started_at`、创建/更新时间。

建议状态：

| 状态 | 启动后的动作 |
| --- | --- |
| `PENDING` | 领取并重新执行完整的目录/分享检查；只允许受控的副作用前重试。 |
| `RUNNING` | 视为上次进程中断，重新领取；必须依靠数据库锁避免并发执行。 |
| `RESTORE_SUBMITTED` | 禁止再次调用 `restore_share`；只读列目标目录并尝试核验/收尾。 |
| `SUCCEEDED` | 跳过，不产生任何云端副作用。 |

## Required ordering

1. 审核通过后，先提交 `PENDING` job，再编辑“正在转存”进度卡。
2. 目标媒体目录确认后，提交 `target_folder_id` 与标准目录名。
3. 从分享列表得到精确筛选结果后，在调用 `restore_share` **之前**提交 `RESTORE_SUBMITTED`、目标目录 ID 和完整预期文件名集合。
4. 调用云端转存；接口成功、任务 ID 或 HTTP 响应都不能单独证明完成。
5. 轮询目标目录，确认每个预期文件实际出现，且没有把错误 season/episode 当作本投稿成功。
6. 在同一数据库事务链中更新精确的 `ACCEPTED` Resource 行并标记 job `SUCCEEDED`。
7. 仅在数据库提交后，编辑已持久化且能唯一对应投稿组的频道原消息；找不到引用时不猜消息 ID、不补发重复消息。

## Startup recovery algorithm

- 在 bot 初始化后、`start_polling` 前执行一次恢复扫描，保证不会和新收到的审核回调并发争抢启动中的任务。
- 只查询有明确 job 行且状态为 `PENDING`、`RUNNING` 或 `RESTORE_SUBMITTED` 的任务。
- 不要把所有“`ACCEPTED` 且 `transferred_folder_id IS NULL`”的历史资源自动变成任务；那会把旧投稿或后来打开自动转存配置的记录误当成新任务。
- 对 `PENDING`/`RUNNING` 调用原有受控转存入口，并传入恢复标记；对 `RESTORE_SUBMITTED` 调用只读 reconciliation 入口，绝不能走普通转存入口。
- 若恢复失败但尚未越过 restore 边界，保留可恢复状态和错误；若已经越过边界，保留 `RESTORE_SUBMITTED`，等待下一次只读核验或人工处理。

## Regression and live gates

必须覆盖以下测试：

- 持久化 `PENDING` job 会恢复并只更新该投稿组；
- 没有 job 的历史 `ACCEPTED` 资源不会被启动扫描自动转存；
- 远程调用前回调/事务已提交 `RESTORE_SUBMITTED` 栅栏；
- `RESTORE_SUBMITTED` 恢复会调用只读核验而不是第二次 `restore_share`；
- 验证成功后资源字段、job 状态和频道原消息更新顺序正确。

上线前后还要分别读取：Alembic head 与表结构、容器 `running/healthy`、新 PID/启动时间、WebUI 认证行为、恢复扫描摘要、Telegram polling 日志、非取消类 traceback，以及目标目录/数据库的精确回读。若是历史旧卡，先做无写预检，再取得用户明确授权后定向重试。