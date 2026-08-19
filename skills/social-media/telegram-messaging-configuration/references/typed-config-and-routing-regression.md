# Typed Config and Routing Regression

## Failure Pattern

A CLI write changed `platforms.telegram.extra` from a YAML mapping into a serialized JSON-looking string. The adapter then saw an empty or incomplete `config.extra`, so mention gating and custom-menu lookup did not run. A similar mistake stored an admin list as the literal string `"[8586984520]"`; the ID comparison failed because the parser does not interpret bracket syntax inside a string.

## Reliable Diagnosis

1. Parse the file with YAML and print only the Telegram subtree and Python types.
2. Confirm `platforms.telegram.extra` is a dictionary.
3. Read the adapter's lookup methods and the config bridge to confirm the actual runtime path.
4. Inspect startup logs for Telegram connection and `set_my_commands` success in default, private, and group scopes.
5. Check for routing bypasses: free-response chat/topic lists, guest mode, observation of unmentioned messages, and exclusive mention behavior.

## Known-Good Routing Values

```yaml
platforms:
  telegram:
    extra:
      require_mention: true
      exclusive_bot_mentions: true
      guest_mode: false
      observe_unmentioned_group_messages: false
      free_response_chats: []
      free_response_topics: []
```

## Menu Verification

Do not rely on a one-time Bot API update. Gateway startup can overwrite it. Verify the requested command names and count after restart for every relevant scope. For custom menu handling, place `custom_menu` in the runtime adapter's `platforms.telegram.extra` mapping when that is the path read by the adapter; keep any top-level user-facing mirror only if the local adapter bridge explicitly supports it.

## Reporting

When a user reports a regression, state the specific malformed type/path, repair it, restart the actual gateway process, and report only verified checks. Do not say that the end-to-end group behavior was tested unless a real group message was exercised.
