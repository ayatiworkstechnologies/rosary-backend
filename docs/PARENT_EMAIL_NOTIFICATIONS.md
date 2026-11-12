# Parent email notifications

Status: implemented but intentionally disabled until school approval, provider
credentials, recipient verification/preferences, and DNS authentication are
complete.

## Delivery model

The existing in-app `notifications` table and Parent Portal bell remain the
source of in-app messages. Email is an optional second channel. The Admin API
resolves linked parent accounts, validates and normalizes their addresses,
deduplicates by normalized email, and writes a durable database outbox.

`python -m app.workers.email_delivery_worker` processes that outbox. API
notification requests never contact SMTP directly. A failed provider call is
retried with exponential backoff, and final failures remain visible in Admin
delivery history. The authenticated verification-request endpoint sends its
single transactional message immediately so the parent receives a clear
success or failure result. It uses an independent feature gate and
database-backed per-parent cooldown/window limits, so enabling verification
does not enable automatic categories. Run one continuously supervised worker, or invoke
`--once` from a scheduled job.

## Required environment variables

Names only; secrets must remain in the server secret store:

- `EMAIL_NOTIFICATIONS_ENABLED` (automatic/outbox worker switch)
- `EMAIL_VERIFICATION_ENABLED` (independent verification switch; default `false`)
- `EMAIL_VERIFICATION_MAX_REQUESTS` (default `3`)
- `EMAIL_VERIFICATION_WINDOW_SECONDS` (default `3600`)
- `EMAIL_VERIFICATION_COOLDOWN_SECONDS` (default `60`)
- `EMAIL_TRANSPORT` (`smtp` in production, `mock` in tests)
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`
- `SMTP_MESSAGE_ID_DOMAIN`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`
- `EMAIL_BATCH_SIZE`
- `EMAIL_RATE_LIMIT_PER_SECOND`
- `EMAIL_MAX_ATTEMPTS`
- `EMAIL_RETRY_BASE_SECONDS`
- `EMAIL_WORKER_POLL_SECONDS`
- `EMAIL_PROCESSING_TIMEOUT_SECONDS`
- `EMAIL_FEE_REMINDERS_ENABLED`
- `SCHOOL_PORTAL_URL`
- `PUBLIC_API_URL` (public HTTPS API origin used by one-click unsubscribe)
- `EMAIL_VERIFICATION_EXPIRE_HOURS` (defaults to `24`)

## Parent preference API

- `GET /api/v1/parent/email-preferences` returns the authenticated parent's
  current verification and opt-in state.
- `PATCH /api/v1/parent/email-preferences` enables or disables email. Enabling
  requires a verified address; disabling is always allowed.
- `POST /api/v1/parent/email-preferences/verification/request` sends a new
  one-time verification link to the authenticated parent's saved address when
  the narrow feature gate and request rate limit allow it.
- `POST /api/v1/parent/email-preferences/verification/confirm` consumes the
  raw token in a JSON body. The parent must then opt in with the preference
  endpoint; verification alone does not enable notifications.
- `POST /api/v1/parent/email-preferences/unsubscribe?token=...` is the public,
  signed, idempotent one-click opt-out endpoint used in notification headers.

Only SHA-256 token digests are stored. Verification links expire and are
single-use. Unsubscribe tokens are bound to the current address, so changing a
parent email invalidates old links and clears verification and opt-in state.

## Production activation checklist

1. Obtain written school approval for the message types and lawful basis.
2. Verify parent addresses through the one-time verification API.
3. Record explicit opt-in through the preference API. New/existing accounts
   default to disabled.
4. Configure the approved SMTP provider and a dedicated sender address.
5. Publish and verify SPF, DKIM and DMARC for the sender domain.
6. Keep `EMAIL_FEE_REMINDERS_ENABLED=false` until separately authorized.
7. Apply `alembic upgrade head` during an approved maintenance window.
8. Start one supervised worker, for example:

   `python -m app.workers.email_delivery_worker`

9. Use Admin recipient preview. Confirm missing, invalid, unverified, opted-out
   and deduplicated counts before sending.
10. Send a single-message sandbox test to an authorized test parent before any
    bulk production send.

## Safe test mode

Set `EMAIL_TRANSPORT=mock` and `EMAIL_NOTIFICATIONS_ENABLED=true` only in the
isolated test environment. The mock transport records outcomes without network
delivery. Automated tests never load the production database.

## PM2 worker example

After approval and migration, run the worker as its own process; never replace
or restart the API process merely to operate the queue:

`pm2 start venv/bin/python --name rosary-email-worker -- -m app.workers.email_delivery_worker`

Review `pm2 logs rosary-email-worker --lines 100 --nostream` and confirm that
provider errors contain no credentials before enabling bulk email.
