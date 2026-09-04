# Transfer Notification Reconciliation

Use this reference when a cloud transfer completes after a timeout/restart and Telegram surfaces disagree about the result.

## Why this is a separate state problem

A submission can have three independent Telegram representations:

1. the cloud-only channel publication;
2. the administrator review/approval card; and
3. the submitter-facing bot notification.

Persisting `ChannelPublication` is sufficient to edit the channel post, but it does not identify the other two messages. A recovery job that edits only the channel can therefore produce the exact symptom: the channel says “transfer succeeded” while the bot still says “transfer incomplete”. This is a notification consistency defect, not proof that the cloud transfer failed.

## Durable data to capture

When the administrator approves an auto-transfer submission, create/update the explicit recovery job before the remote side-effect boundary and persist:

- `review_chat_id` and `review_message_id` for the approval card;
- the original trusted `review_html` (do not HTML-escape it a second time);
- `review_admin_tg_id` and the awarded points needed to rebuild the card;
- `notification_chat_id`, `notification_message_id`, and the exact rendered `notification_text` returned/sent to the submitter; and
- a boolean such as `bot_messages_synced` for idempotent retry after a process crash.

Capture the notification message ID from the `send_message` response. Do not try to discover it later by scanning arbitrary Telegram message IDs.

## Safe success order

1. Submit the recovery fence before `restore_share`; once `RESTORE_SUBMITTED` or `restore_started_at` is persisted, never replay `restore_share` automatically.
2. Reconcile the exact target directory read-only. Verify every expected file and, for approved movie repairs, verify the final name by file ID after any official rename.
3. Update the resource and persist the verified transfer result.
4. Update the saved `ChannelPublication` in place; never send a duplicate channel post.
5. Edit the saved administrator card and submitter notification in place using their persisted coordinates. Use the exact rendered message returned by the Telegram edit API as the verification target; when HTML is used, Telegram may return parsed plain text, so compare semantic/normalized content rather than raw markup.
6. Mark `bot_messages_synced` only after every available persisted reference has been edited successfully. If an edit fails, leave the cloud/resource success intact and retry the notification reconciliation on the next startup.

Notification edits are best-effort relative to already verified cloud success, but they must be observable in logs and retryable; an edit failure must not cause a second cloud restore.

## Historical messages without coordinates

Telegram Bot API does not provide a general history query for arbitrary outgoing bot messages. If a legacy recovery job has no persisted bot message IDs, do not guess IDs, overwrite an unrelated message, or claim that the old message was edited. Send exactly one clearly labeled correction to the known submitter chat, containing the verified final status and explaining that the prior warning was a stale intermediate state. This is preferable to a duplicate transfer or an unsafe edit.

## Regression coverage

Keep tests for all of the following:

- recovery-job creation stores review and notification references;
- a verified recovery success calls the notification reconciler after the cloud path and never calls `restore_share` again;
- both review and submitter messages are edited with success text and the returned Telegram text is checked;
- an existing `RESTORE_SUBMITTED` job can be retried read-only after a timeout; and
- a legacy job with no message coordinates is not treated as editable history.

The channel, bot notification, resource, and recovery-job states should be queried independently during production verification. Never infer bot-message success merely from a successful channel edit.
