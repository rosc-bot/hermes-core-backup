---
name: hermes-cron-model-routing
description: "Use for Hermes cron jobs and dynamic model routing."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, cron, scheduler, model-routing, provider, timezone, telegram]
---

# Hermes 定时任务与动态模型路由

## When to Use

Use this skill when configuring, diagnosing, or repairing Hermes scheduled tasks, especially when jobs should follow the current model/provider dynamically.

- 创建、检查或修复 Hermes 定时任务；
- 要求任务动态跟随当前默认模型/提供商；
- 定时任务因模型或提供商变化而失败；
- 定时任务因限流（429）、额度耗尽（403）或服务端错误（500）而失败；
- 配置备用模型链让任务自动切换；
- 手动强制运行卡住的定时任务；
- 验证任务时间、执行状态、Token 消耗与 Telegram 投递。
- 配置 `/model` 切换的持久化行为（每次切换永久保存 vs 仅本次会话）；

## 核心原则

1. 用户希望动态跟随时，任务的 `model` 和 `provider` 必须保持为空值；不要擅自固定模型。
2. Hermes 对未固定任务会保存创建时的 `provider_snapshot` 和 `model_snapshot`。全局推理配置发生变化后，安全保护会跳过任务，避免意外扣费；这不是模型调用失败，而是故意的 fail-closed 行为。
3. 修复动态任务时，应先确认当前全局模型和提供商，再同步任务快照，同时保持 `model: null`、`provider: null`。
4. 不要把"同步快照"误做成永久固定模型；固定模型会违背动态跟随要求。
5. 不要把任务显示为 `active` 当作最近执行成功；必须查看 `last_status` 和执行记录。
6. 所有面向用户的说明、状态、错误和报告使用中文；代码、命令和原始字段名保持原样。

## 标准检查流程

1. 检查任务列表、执行记录和调度器状态：
   ```bash
   hermes cron list
   hermes cron runs --limit 50
   hermes cron status
   ```
2. 查看 `~/.hermes/cron/jobs.json`，重点核对：
   - `model`、`provider` 是否为空；
   - `model_snapshot`、`provider_snapshot` 是否与当前全局配置一致；
   - `last_status`、`last_error`、`next_run_at`；
   - `fire_claim` 是否卡住（长时间 `claimed` 状态）；
   - 交付目标和时区偏移。
3. 检查当前全局配置：
   ```bash
   hermes config get model
   hermes config get timezone
   ```
4. 若错误包含 `global inference config drifted`、`unintended spend` 或 `unpinned`，确认没有实际模型调用，然后同步快照：
   ```bash
   hermes cron edit <JOB_ID> --model <当前模型> --provider <当前提供商>
   hermes cron edit <JOB_ID> --model '' --provider ''
   ```
   第一条更新使快照捕获当前路由；第二条清除显式固定，恢复动态跟随。完成后重新检查 `jobs.json` 和 `hermes cron list`。
5. 用 `hermes cron run <JOB_ID>` 或等待下一个计划时间验证真实执行；确认 `hermes cron runs` 出现新的成功记录，而不是只看任务仍显示 active。

## 备用模型链（fallback）

当默认模型提供商限流或不可用时，可配置备用模型链，让定时任务自动切换：

```yaml
fallback_providers:
  - provider: "custom:备用提供商A"
    model: "模型A"
  - provider: "custom:备用提供商B"
    model: "模型B"
```

配置方法：

```bash
hermes config set fallback_providers '[{"provider":"custom:备用A","model":"模型A"},{"provider":"custom:备用B","model":"模型B"}]'
```

注意：`hermes config set` 会以 JSON 字符串形式写入 YAML。如果后续解析失败（`get_fallback_chain` 返回空列表），需要手动编辑配置文件，将 `fallback_providers` 改为 YAML 列表格式：

```yaml
fallback_providers:
  - provider: "custom:ooioo.work"
    model: gpt-5.6-luna
  - provider: "custom:日日新"
    model: deepseek-v4-flash
```

## 备用链触发条件

默认情况下，备用链只在 `AuthError`（认证失败）时触发。HTTP 429（限流）、403（额度耗尽）、500（服务端错误）等非认证错误不会触发备用链，任务会直接失败。

要修复这个问题，需要修改调度器源码，将 `run_job` 函数中的异常处理从"仅 AuthError 触发备用链"改为"所有异常都尝试备用链"：

```
except AuthError:   → 记录错误，标记尝试备用链
except Exception:   → 同样标记尝试备用链（原代码直接报错退出）
else:               → 不尝试备用链
if _try_fallback:   → 遍历备用链，尝试各提供商
```

修改文件：`/home/ubuntu/.hermes/hermes-agent/cron/scheduler.py`

修改后执行 Python 语法检查：

```bash
python3 -m py_compile /home/ubuntu/.hermes/hermes-agent/cron/scheduler.py
```

## 手动强制运行任务

手动运行应使用 `hermes cron run <JOB_ID>`。当前源码已修复手动运行路径：它会在当前命令生命周期内同步执行，不再把任务交给短命的异步委派线程，因此不会永久卡在 `claimed` 状态。

```bash
hermes cron run <JOB_ID>
```

命令可能运行数分钟，应设置较长超时；只有返回 `succeeded`，并且 `hermes cron runs` 出现 `completed`、输出目录生成新报告，才算真正成功。

如果任务此前已经卡在 `fire_claim`，先清除占用再运行：

```bash
python3 -c "
import json
p='/home/ubuntu/.hermes/cron/jobs.json'
d=json.load(open(p))
for j in d['jobs']:
    j['fire_claim']=None
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
"
```

## 重要陷阱

- `hermes cron run` 显示 "Ran now: failed" 时，实际是异步委派已分发，任务仍在后台排队，不是真正失败。查看 `hermes cron runs` 的 `claimed` 状态可确认。
- 多次执行 `hermes cron run` 会产生多个 `claimed` 记录，但只有最新一次会实际执行。
- 卡在 `claimed` 状态的旧记录不会自动清除，需要手动清空 `fire_claim` 字段。
- 修改默认模型后，即使 `model_drift_guard` 已关闭，之前的异步委派调用仍可能使用旧模型。需要清除 `fire_claim` 后重新通过调度器勾子运行。
- 所有面向用户的说明、状态、错误和报告使用中文；代码、命令和原始字段名保持原样。

## 动态跟随而不重复同步

当用户明确授权接受模型切换带来的费用风险时，可关闭漂移保护：

```bash
hermes config set cron.model_drift_guard false
hermes config get cron.model_drift_guard
hermes config check
```

关闭后，保持任务的 `model: null`、`provider: null`，任务会在每次执行时直接解析当前全局模型和提供商；全局配置变化不再因 `provider_snapshot` / `model_snapshot` 不一致而跳过，也不需要重新同步快照。这会牺牲"模型变化时 fail-closed 防止意外扣费"的保护，只有用户明确要求"动态跟随且不重新同步"时才这样做。

- 所有 cron 表达式按北京时间解释；报告中的下一次运行时间也必须显示 `+08:00` 或明确写"北京时间"。
- 若任务记录仍显示 `+00:00`，先重新编辑同一个 cron 表达式，使调度器按当前 Hermes 时区重新计算 `next_run_at`，然后复核原始 JSON。
- 不要把系统底层 UTC/RTC 显示误报为用户任务使用 UTC；只要 Hermes 配置和调度记录为 `Asia/Shanghai`/`+08:00`，任务即按北京时间运行。

## Token 与可靠性注意事项

- 动态模型不等于动态预算。任务仍会消耗当前模型的输入/输出 Token；长 Telegram 会话不应被任务复用为上下文。
- 优先让定时任务使用独立、简短、自包含的提示；能用 `--no-agent` 脚本完成的固定检查，避免不必要的模型调用。
- 发生 provider drift 时，先报告"未发起推理调用"，再修复，不要声称任务已成功执行。

## Telegram 投递规范

- 任务投递目标应明确，例如 `telegram:8586984520`。
- 用户只看中文；不要直接把 Hermes 的英文错误原文作为唯一说明，应翻译并保留必要的代码字段/命令。
- 运行结果应明确列出：北京时间、任务名称、是否真正执行、模型路由、是否投递成功、失败原因和修复状态。

## 交互式 /model 切换的持久化语义

`/model <name>` 默认只在当前会话生效；要让普通切换也永久保存为全局默认模型，配置：

```bash
hermes config set model.persist_switch_by_default true
```

解析顺序（源码 `hermes_cli/model_switch.py::resolve_persist_behavior`）：

| 操作 | 效果 |
|---|---|
| `/model 某模型`（不带标志） | `persist_switch_by_default: true` → 永久保存；否则仅本次会话 |
| `/model 某模型 --global` | 始终永久保存（最高优先） |
| `/model 某模型 --session` / `--once` | 始终临时切换（显式退出持久化） |
| `/model 某模型 --provider X`（无持久化标志） | 仅本次会话（探索性切换） |

要点：

- `--global`、`--session`、`--once` 显式标志优先于配置键；只有不带标志的普通切换受 `persist_switch_by_default` 控制。
- 本机已设为 `true`（爸爸要求"每次切换模型都永久保存"）。动态跟随的定时任务会在下次执行时解析到切换后的新全局默认模型，无需重同步快照。
- 内置别名（sonnet/opus/haiku/claude/gpt5 等）走同一持久化规则。

验证方法与源码细节见 `references/model-switch-persistence.md`。

## 参考资料

- `references/provider-drift-and-dynamic-follow.md`：动态模型任务失败的真实诊断与恢复记录。
- `references/model-switch-persistence.md`：`persist_switch_by_default` 配置键的解析顺序、验证方法与本机设置实录。