# Automatic email notifications

Automatic email delivery reuses the parent email outbox. A business request
creates its domain record, in-app notifications, `EmailNotificationBatch`, and
`EmailDelivery` rows in one transaction. The background worker sends queued
deliveries later; request handlers never connect to SMTP.

## Supported event matrix

| Event | Recipients | Local implementation |
| --- | --- | --- |
| Homework created | Active linked parents of active students in the assigned class | In-app + email outbox; one delivery per unique eligible address |
| Homework updated | — | No homework update endpoint exists; not invented |
| Attendance marked absent | Active linked parents of the affected active student | In-app + email outbox |
| Attendance correction | Active linked parents of the affected active student | In-app + email outbox when the stored status changes |
| Exam schedule published | — | Schedules have create/update operations but no publication state/action |
| Results published | Active linked parents for classes scheduled for the exam | In-app + email outbox only on unpublished-to-published transition |
| Circular published | Active linked parents for `ALL`, `PARENT`, or `CLASS` audience | Active circular creation queues in-app + email; teacher-only circulars remain in-app for teachers |
| School event published | Active linked parents for `ALL`, `PARENT`, or `CLASS` audience | Active event creation queues in-app + email |
| Admin announcement | Admin-selected linked parents | Existing preview/send API and outbox retained |
| Fee reminder | Admin-selected linked parents | Existing authorized admin action retained; separate flag required |
| Fee payment confirmation | — | No payment transaction/confirmation workflow exists |
| Parent account activation | — | No explicit activation-completed workflow exists |
| Password reset | — | No password-reset workflow exists |
| Teacher announcement email | — | Teacher circular in-app notification exists; email outbox is parent-specific and no verified teacher-email preference workflow exists |

An inactive parent, missing/invalid address, unverified address, opt-out, or
duplicate normalized address never receives a queued delivery.

## Configuration

All automatic triggers default to disabled:

```env
EMAIL_NOTIFICATIONS_ENABLED=true
EMAIL_TRANSPORT=mock

EMAIL_HOMEWORK_NOTIFICATIONS_ENABLED=false
EMAIL_ATTENDANCE_NOTIFICATIONS_ENABLED=false
EMAIL_RESULTS_NOTIFICATIONS_ENABLED=false
EMAIL_CIRCULAR_NOTIFICATIONS_ENABLED=false
EMAIL_EVENT_NOTIFICATIONS_ENABLED=false
EMAIL_FEE_REMINDERS_ENABLED=false
```

Safe test mode filters recipients after normal parent eligibility checks. It
does not replace parent identities, verification, active status, or opt-in.
When test mode is enabled, a blank or invalid allowlist sends to nobody.

```env
EMAIL_AUTOMATION_TEST_MODE=true
EMAIL_HOMEWORK_TEST_RECIPIENTS=rubankumar@ayatiworks.com,msriramya333@gmail.com
EMAIL_ATTENDANCE_TEST_RECIPIENTS=
EMAIL_RESULTS_TEST_RECIPIENTS=
EMAIL_CIRCULAR_TEST_RECIPIENTS=
EMAIL_EVENT_TEST_RECIPIENTS=
```

## Local mock testing

The test bootstrap forces an isolated SQLite database, mock transport, blank
allowlists, and disabled automatic triggers regardless of local SMTP settings.

```powershell
.\venv\Scripts\python.exe -m pytest `
  tests\test_automatic_homework_email.py `
  tests\test_automatic_event_email.py `
  tests\test_parent_email_notifications.py -q
```

The mock worker can be exercised in an isolated development environment with:

```bash
EMAIL_TRANSPORT=mock python -m app.workers.email_delivery_worker --once
```

Never run a worker against a production database during local testing.

## Controlled real SMTP test

1. Confirm the database URL points to an isolated non-production database.
2. Use verified, opted-in synthetic parent accounts linked to synthetic students.
3. Set `EMAIL_AUTOMATION_TEST_MODE=true` and a non-empty event allowlist.
4. Set only the event under test to `true`; leave every other event disabled.
5. Configure SMTP through environment secrets and call the protected
   `/api/v1/admin/notifications/email-health` endpoint.
6. Create one synthetic event, inspect the batch/delivery records, and run the
   worker once.
7. Confirm inbox delivery before considering a wider staging test.

SMTP acceptance is not proof of inbox delivery. The outbox prevents duplicate
queue rows, but SMTP cannot provide an exactly-once guarantee: a worker can
rarely be interrupted after provider acceptance but before the database commit.

## Database status

No new schema is required by automatic triggers. They reuse the tables created
by Alembic revision `e4a1b2c3d4e5`. Production must already be at or beyond that
revision before any automatic flag is enabled.

## Future production checklist

1. Rotate any exposed SMTP and JWT credentials; store them outside Git.
2. Back up the database and verify the current Alembic revision.
3. Deploy backend code with every new automatic trigger still `false`.
4. Verify API health, email status, and authenticated SMTP health over HTTPS.
5. Keep the worker stopped while running preview/test-recipient checks.
6. Enable test mode with a non-empty approved allowlist and one event flag.
7. Start one worker, send one synthetic event, and verify outbox and inbox state.
8. Review SPF, DKIM, DMARC, bounce handling, rate limits, and consent records.
9. Disable test mode and enable a production event only after explicit approval.
10. Monitor `QUEUED`, `RETRY`, `PROCESSING`, and `FAILED` deliveries and retain a
    rollback plan that disables flags and stops the worker without deleting the
    audit/outbox records.
