---
name: telegram-messaging-configuration
description: "Use when troubleshooting Hermes Telegram bot routing."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [telegram, hermes, gateway, configuration, permissions, mentions, command-menu]
    related_skills: [hermes-agent, systematic-debugging, tg-group-summary]
---

# Telegram Messaging Configuration

## When to Use

Use this skill when a Hermes Telegram bot has unexpected group replies, missing mention/reply gating, incorrect admin or pairing behavior, changed command menus, missing typing indicators, or tool/progress messages that should be hidden.

## Core Invariants

Preserve these user-facing invariants unless the user explicitly changes them:

- Group chats respond only when the bot is explicitly mentioned or the incoming message replies to the bot.
- Ordinary unmentioned group chatter is neither dispatched nor injected into agent context.
- The Telegram command menu is verified against the requested exact command set, including scope-specific registrations.
- Typing indicators may remain enabled while tool previews, interim assistant messages, live status text, and long-running notices remain disabled.
- Admin IDs and allowlists are typed values, not serialized representations of lists.

## Workflow

1. Inspect the raw YAML and the merged/runtime configuration. Assert types, especially `platforms.telegram.extra`.
2. Trace the config bridge into `PlatformConfig.extra` and inspect the adapter's exact lookup keys. Do not infer behavior from a successful `hermes config set` message alone.
3. Check for bypasses before editing routing: `free_response_chats`, `free_response_topics`, guest mode, observation of unmentioned messages, mention patterns, and bot-exclusion settings.
4. Make one typed, scoped change at a time. Never replace a whole mapping section with a scalar or serialized JSON string.
5. Restart the manually managed gateway using the repository's working restart method. A service restart may fail when user linger is disabled; verify the actual process instead.
6. Verify live startup logs show Telegram connected and command registration for default, private, and group scopes.
7. Exercise the exact behavior: an unmentioned group message must be ignored; a mention and a reply-to-bot must dispatch. Confirm the menu count, names, and descriptions from Telegram's current registration when credentials/tools permit.
8. Report only observed results, and explicitly call out any behavior that could not be end-to-end tested.

## Known Configuration Shape

Use a mapping for the platform extra block:

```yaml
platforms:
  telegram:
    typing_indicator: true
    extra:
      require_mention: true
      exclusive_bot_mentions: true
      guest_mode: false
      observe_unmentioned_group_messages: false
      free_response_chats: []
      free_response_topics: []
      allow_admin_from: "123456789"
      group_allow_admin_from: "123456789"
```

A numeric scalar or a YAML list is parsed as an ID value; a string such as `"[123456789]"` is not equivalent to a list. If a CLI writes a nested block as a JSON-looking string, repair the YAML structure directly through a safe structured editor or a supported mapping-aware command.

## Pitfalls

- `telegram.require_mention` in a separate top-level section may not reach the adapter if the adapter reads `platforms.telegram.extra.require_mention`.
- A successful config write can still have the wrong type or wrong path.
- `group_policy: open` controls authorization, not whether every group message should trigger a response; mention gating must be checked separately.
- One-time `setMyCommands` calls can be overwritten on gateway startup. Verify all Telegram command scopes after restart.
- Private-chat admin status and group-chat admin status are separate policies; configure both when that is intended.
- Do not use personality instructions as the only routing control. Routing must be enforced by the adapter/gateway.

## Verification Checklist

- [ ] `platforms.telegram.extra` parses as a mapping
- [ ] `require_mention` is true at the runtime adapter path
- [ ] `exclusive_bot_mentions` is true when only direct bot mentions should wake it
- [ ] unmentioned-message observation and free-response bypasses are disabled
- [ ] admin IDs are parsed as IDs, not bracketed strings
- [ ] gateway process is running after restart
- [ ] Telegram is connected
- [ ] command menu is registered in all relevant scopes with the expected entries
- [ ] an actual unmentioned group message is ignored
- [ ] an actual mention and reply-to-bot are handled

## Session Detail

See `references/typed-config-and-routing-regression.md` for the concrete failure mode and verification recipe from a Telegram gateway incident.
