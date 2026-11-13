# School operational parent email policy

## Two separate communication classes

`OPTIONAL` email preserves the existing parent choice. A recipient must have an
active parent account, a valid registered address, successful address
verification, explicit email opt-in, an active student relationship, and no
active suppression.

`OPERATIONAL` email is available only to an automatic business event that the
school has explicitly authorized through both the operational master flag and
that category's operational flag. It never changes `email_verified_at` or
`email_notifications_enabled`. Active account, valid address, intended student
relationship, test restriction, and suppression rules still apply.

An unverified operational recipient receives only this generic notice:

> New School Update — Rosary School
>
> A new school update is available in the Rosary School Parent Portal. Please
> sign in to view the details securely.

The email contains no student name, admission number, attendance state, marks,
grade, fee amount, or other private record. Details remain behind authenticated
parent login. Verified operational recipients may receive the existing
category content after that category is approved.

## Category approval register

| Category | Implemented event | Operational approval status |
| --- | --- | --- |
| `HOMEWORK` | Successful teacher homework creation | **Not approved; default optional** |
| `ATTENDANCE` | New absence or actual stored-status correction | **Not approved; default optional** |
| `RESULTS` | Unpublished-to-published exam result transition | **Not approved; default optional** |
| `CIRCULAR` | Active parent-capable circular creation | **Not approved; default optional** |
| `EVENT` | Active parent-capable school-event creation | **Not approved; default optional** |
| `FEE_PAYMENT` | Increase in cumulative paid amount | **Not approved; default optional** |

Code support is not approval. Before enabling any row, the school must record
the purpose, lawful/contractual basis, audience, content classification,
retention, support contact, owner, approval date, and rollback authority.
Attendance, results, and fee categories require particular review because their
source messages contain sensitive student or financial details for verified
recipients.

## Default-deny controls

Operational delivery for a category requires every applicable control:

```env
EMAIL_NOTIFICATIONS_ENABLED=true
EMAIL_<CATEGORY>_NOTIFICATIONS_ENABLED=true
EMAIL_OPERATIONAL_NOTIFICATIONS_ENABLED=true
EMAIL_<CATEGORY>_OPERATIONAL_ENABLED=true
```

Every value defaults to `false`. During restricted testing,
`EMAIL_AUTOMATION_TEST_MODE=true` also requires the category-specific recipient
allowlist. Missing and invalid allowlists queue zero delivery. Manual Admin
email is optional-only and additionally requires `EMAIL_ADMIN_TEST_RECIPIENTS`
in restricted test mode.

## Queue and worker enforcement

- Every automatic batch persists `recipient_policy` and `event_reference`.
- Queue resolution normalizes/deduplicates addresses and records verified,
  unverified, missing, invalid, opted-out, and suppressed counts.
- The worker rechecks global/category authorization, operational approval,
  test allowlist, active account, current address, optional consent, and active
  suppression immediately before every attempt.
- Unverified operational delivery replaces batch content with the generic
  notice at send time. Optional unsubscribe links are not attached to an
  operational message.
- SMTP permanent recipient rejection creates a durable suppression. Authorized
  Admin endpoints can add/remove a single suppression; responses mask the
  address and there is no unrestricted bulk operation.
- Stable category/reference idempotency keys and the batch/address unique
  constraint prevent duplicate queue records.

## Read-only readiness

`GET /api/v1/admin/notifications/recipient-readiness` returns aggregate counts
only. It reports linked/unlinked/inactive relationships, optional eligibility,
operational address readiness, unverified, missing, invalid, duplicate, and
suppressed counts. It never returns an address list and requires Admin auth.

Operational address readiness is data quality, not permission to send. The
category approval register and feature flags remain authoritative.

## Product decisions intentionally not invented

There is no new email for homework update/delete, attendance deletion, result
unpublish/delete, circular edit/status/delete, event edit/status/delete, exam
schedule edit/delete, or fee metadata/status changes. Any such notification
requires a separately approved publication/correction policy.
