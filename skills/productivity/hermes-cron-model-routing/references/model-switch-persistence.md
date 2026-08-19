# /model 切换持久化（persist_switch_by_default）实录

## 背景（2026-08-14）

爸爸要求："每次切换模型都设为永久保存而不是本次会话。" 

Hermes 默认行为：不带标志的 `/model <name>` 仅会话级。官方文档（providers-and-models.md）只提到
`/model fav — session-scoped; add --global to persist as default`，**没有**提及持久化配置键。

实现：

```bash
hermes config set model.persist_switch_by_default true
```

写入 `~/.hermes/config.yaml`：

```yaml
model:
  default: ...
  provider: ...
  persist_switch_by_default: true   # ← 新增
```

## 源码事实（hermes_cli/model_switch.py）

`resolve_persist_behavior(is_global, is_session, is_once=False, explicit_provider="")` 解析顺序：

1. `--once` → `False`（仅下一次对话）
2. `--session` → `False`（仅本会话）
3. `--global` → `True`（强制持久化）
4. 显式 `--provider` 且无持久化标志 → `False`（会话级，探索性切换，`--global` 仍可强制）
5. 其余情况 → 读 `model.persist_switch_by_default`（默认 `False`；`model` 是字符串而非 dict 时回退默认）

配置文件防御性读取：fresh install 时 `model` 可能为扁平字符串，此时内置默认 `False` 生效。

## 验证片段

```bash
cd ~/.hermes/hermes-agent && python3 -c "
from hermes_cli.model_switch import resolve_persist_behavior
print('plain /model x     →', resolve_persist_behavior(False, False))   # 配置后应 True
print('/model x --global  →', resolve_persist_behavior(True, False))    # True
print('/model x --session →', resolve_persist_behavior(False, True))    # False
"
```

## 备查

- 内置别名（sonnet/opus/haiku/claude/gpt5/gpt/codex/o3/o4/gemini/deepseek/grok/llama/qwen/minimax/nemotron/kimi/glm/step/mimo/trinity）走同一解析流程。
- 权威参考：`tests/hermes_cli/test_model_switch_persist_default.py`、`tests/gateway/test_model_picker_persist.py`。
- 用户别名（`model_aliases` / `model.aliases`）也受同一持久化规则控制。