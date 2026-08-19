# Telegram Bot 自定义命令菜单维护

## 问题：custom_menu 在 hermes update 后被覆盖

Hermes 的 Telegram 适配器（`plugins/platforms/telegram/adapter.py`）在启动时默认调用 `telegram_menu_commands()` 从注册表生成 60 个内置命令，**覆盖**用户通过 `config.yaml` 配置的 `custom_menu`。

这导致用户每次在面板里自定义的精简中文菜单被官方一大串英文命令覆盖。

## 双重修复方案

### 1. 代码级修复（patch adapter.py）
在 `adapter.py` 的 `set_my_commands` 逻辑中，优先检查 `custom_menu` 配置。关键代码段：

```python
# adapter.py 中 set_my_commands 逻辑：先检查 custom_menu
custom_menu = self.config.extra.get("custom_menu")  # 从 platforms.telegram.extra.custom_menu 读取

if custom_menu and isinstance(custom_menu, list):
    # 从 custom_menu 构建 BotCommand 列表
    bot_commands = [BotCommand(item['command'], item['description']) for item in custom_menu]
    menu_commands = [(c.command, c.description) for c in bot_commands]
    hidden_count = 0
else:
    # 回退到注册表自动生成的 60 个命令
    menu_commands, hidden_count = telegram_menu_commands(max_commands=max_commands)
    bot_commands = [BotCommand(name, desc) for name, desc in menu_commands]
```

### 2. 手动同步（不用重启也能恢复）
如果已经更新完、菜单已变，可以运行一次 Python 脚本立即重置：

```python
import os, asyncio
from telegram import Bot, BotCommand, BotCommandScopeDefault, \
    BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from hermes_cli.config import load_config, get_env_value

cfg = load_config()
tg_cfg = cfg.get("platforms", {}).get("telegram", {})
custom_menu = tg_cfg.get("extra", {}).get("custom_menu", [])
token = os.environ.get("TELEGRAM_BOT_TOKEN") or get_env_value("TELEGRAM_BOT_TOKEN")

async def update():
    bot = Bot(token=token)
    bot_commands = [BotCommand(item['command'], item['description']) for item in custom_menu]
    for scope in (BotCommandScopeDefault(), BotCommandScopeAllPrivateChats(), BotCommandScopeAllGroupChats()):
        await bot.set_my_commands(bot_commands, scope=scope)
    # 验证
    current = await bot.get_my_commands()
    for c in current:
        print(f"/{c.command} - {c.description}")

asyncio.run(update())
```

## 配置示例（config.yaml）
```yaml
platforms:
  telegram:
    extra:
      custom_menu:
        - command: start
          description: 开始新的对话
        - command: new
          description: 开始新对话（清除记忆）
        - command: compact
          description: 压缩对话记忆
        - command: clear
          description: 清除对话历史
        - command: history
          description: 查看对话历史
        - command: model
          description: 查看或切换AI模型
        - command: stop
          description: 停止当前任务
```

## 验证方法
```python
from telegram import Bot
import os
from hermes_cli.config import get_env_value

token = os.environ.get("TELEGRAM_BOT_TOKEN") or get_env_value("TELEGRAM_BOT_TOKEN")
import asyncio
async def check():
    bot = Bot(token=token)
    cmds = await bot.get_my_commands()
    print(f"当前注册命令数: {len(cmds)}")
    for c in cmds[:10]:
        print(f"/{c.command} - {c.description}")
asyncio.run(check())
```

## 注意事项
- 适配器每次启动（gateway 重启）都会重新注册命令，代码级修复是持久方案。
- 手动同步脚本是一次性的，配合代码级修复效果最佳。
- 三个 scope（Default、AllPrivateChats、AllGroupChats）都必须设置，Telegram 按最窄匹配。
- 更新 Hermes 后，`adapter.py` 的 patch 可能需要重新应用（`git log --oneline` 确认是否有冲突）。