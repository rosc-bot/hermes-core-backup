# Provider 漂移与动态跟随诊断记录

## 现象

定时任务列表仍显示 `[active]`，但最近执行记录为 `failed`。错误指出全局推理配置从任务创建时的提供商/模型变更为当前配置，且任务未固定，因此任务被跳过；日志明确说明没有发起推理调用。

## 关键字段

`~/.hermes/cron/jobs.json` 中：

- `model: null`、`provider: null`：任务动态跟随；
- `model_snapshot`、`provider_snapshot`：创建或更新时记录的路由快照；
- `last_status`、`last_error`：最近执行结果；
- `next_run_at`：下次执行时间，使用 Hermes 配置时区。

## 恢复方法

先读取当前全局路由，再对每个受影响任务执行两步更新：

```bash
hermes cron edit <JOB_ID> --model <当前模型> --provider <当前提供商>
hermes cron edit <JOB_ID> --model '' --provider ''
```

第一步刷新快照，第二步清除显式固定。复核：

```bash
hermes cron list
hermes cron runs --limit 50
```

不要只看到任务为 `active` 就判定成功；必须等到下一次执行或手动运行并检查新执行记录。

## 用户环境约定

用户要求所有时间使用北京时间；配置为 `Asia/Shanghai`，任务表达式和 `next_run_at` 应显示 `+08:00`。所有面向用户的解释必须使用中文，命令、配置键和原始错误字段可保留代码形式。
