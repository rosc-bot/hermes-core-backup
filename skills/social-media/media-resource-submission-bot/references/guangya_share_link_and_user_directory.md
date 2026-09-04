# Guangya Share-Link and `/user` Directory Reference

## Guangya link protocol

The current Guangya web client treats the complete path segment after `/s/` as an opaque string `shareId`.

Example shape:

```text
https://www.guangyapan.com/s/<numeric-id>_<short-code>_<final-segment>
```

The backend must send the complete `<numeric-id>_<short-code>_<final-segment>` to both `get_share_summary` and `get_share_access_token`. It must not strip the final underscore component merely because it looks like a four-character extraction code. A `#/share/` fragment is client routing metadata and should be ignored by `urlsplit`, while the path segment remains unchanged.

Explicit `?code=...` / `?pwd=...` query parameters, or adjacent text such as `提取码: XXXX`, may supply a separate code. Do not infer a code from an opaque path unless an independently verified legacy API contract requires a bounded fallback.

### Safe reproduction

1. Call `extract_share_id_and_code()` with a complete `/s/<composite>` URL and with the same URL followed by `#/share/`.
2. Assert that both calls return the identical complete share ID and an empty code.
3. Mock `urllib.request.urlopen` for summary, access-token, and file-list responses; inspect request JSON and assert every `shareId` equals the complete path segment.
4. Treat an HTTP 200 response with `code=200` and `data=null` as a business failure, not as a successful authorization. Require a dictionary `data`, and require a non-empty `accessToken` for the token response.
5. For a no-write live probe, report only `is_valid`, video count, formatted size, and error; never print access tokens, cookies, file URLs, or private share contents. Do not invoke transfer APIs.

The regression fixture belongs in `tests/test_stage_w_user_directory_and_link_fix.py`; keep the actual user-provided URL out of logs and reusable fixtures.

## `/user` directory contract

- `/user` is admin-only and lists every account represented by the `users` table.
- Split the rows using the dynamically parsed configured administrator IDs; render `👑 管理员` first and `👤 普通用户` second.
- Include total counts, a bounded page size, and inline previous/next/refresh controls. Keep `/user <numeric-id/@username>` profile lookup and point-operation syntax unchanged.
- Escape stored display names and usernames at the final Telegram HTML boundary. Numeric IDs, counts, and validated point balances can be formatted numerically.

## Green-batch release cadence

For a related repair batch, use this order: failing regression tests → implementation → focused/full tests → explicit selective staging → one local commit → one REST API synchronization with read-back verification → one production service restart → runtime PID/WebUI/polling verification. Do not repeatedly restart for small edits, and retain the long-lived API credential in its mode-600 deployment location.