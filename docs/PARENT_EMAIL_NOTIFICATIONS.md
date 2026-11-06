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
requests never contact SMTP directly. A failed provider call is retried with
exponential backoff, and final failures remain visible in Admin delivery
history. Run one continuously supervised worker, or invoke `--once` from a
scheduled job.

## Required environment variables

Names only; secrets must remain in the server secret store:

- `EMAIL_NOTIFICATIONS_ENABLED`
- `EMAIL_TRANSPORT` (`smtp` in production, `mock` in tests)
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`
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

## Production activation checklist

1. Obtain written school approval for the message types and lawful basis.
2. Verify parent addresses and set `users.email_verified_at` only from an
   authoritative process.
3. Set `users.email_notifications_enabled` from an approved preference or
   documented lawful-basis process. New/existing accounts default to disabled.
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
