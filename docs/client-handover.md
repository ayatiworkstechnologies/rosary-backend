# Rosary School Portal client handover

Last verified: 5 November 2026

This document describes the implemented portal and its operating procedures. It intentionally contains no passwords, private keys, environment values, or student personal data.

## 1. Project overview

The portal has three role-specific applications backed by one FastAPI service and MySQL database:

- Admin: school setup and operational records.
- Teacher: assigned students, attendance, homework, exams, results, circulars, calendar, and profile.
- Parent: linked children, attendance, homework, exams, results, fees, circulars, downloads, calendar, and profile.

The frontend is a Next.js application deployed by Vercel. The backend is an immutable FastAPI release managed on the application server. Alembic owns database schema changes.

## 2. Production URLs

- Portal: <https://rosary-frontend.vercel.app/>
- API: <https://www.api.rosarychennai.com>
- API health: <https://www.api.rosarychennai.com/health>

The API process listens on server loopback only. Do not expose its application port directly; public API access must continue through HTTPS and the reverse proxy.

## 3. Admin user manual

1. Select **Admin** on the login page and sign in with an active admin account.
2. Use the dashboard for the operational overview.
3. Use **Classes**, **Students**, and **Teachers** to maintain academic records and teacher assignments.
4. Use **Parent Linking** to connect an existing parent account to the correct student.
5. Use **Fees** to create fee records and record payment status, payment mode, and receipt number.
6. Use **Circulars**, **Calendar**, and **Notifications** for school communication.

Confirm identifiers and the intended student before editing or deleting records. Bulk imports and speculative parent links are not routine UI operations.

## 4. Teacher user manual

1. Select **Teacher** at login and sign in with an active teacher account.
2. Review assigned classes and students on the dashboard and student pages.
3. Record attendance for the correct class and date.
4. Create or update homework for the intended class.
5. Maintain exam schedules and results only for the teacher's permitted classes.
6. Review circulars and calendar items and maintain the teacher profile where permitted.

If an expected class or student is missing, request an admin to verify the assignment instead of creating duplicate records.

## 5. Parent user manual

1. Select **Parent** at login and sign in with the registered parent account.
2. Open **My Child** to see children linked to that account.
3. Select the intended child before reviewing attendance, homework, exam schedules, results, or fees.
4. Use **Circulars**, **Downloads**, and **Calendar** for published school information.
5. Review the profile and contact the school office if a child is missing or incorrectly linked.

The fees page displays recorded fee and receipt information. It is not a payment gateway.

## 6. Authentication flow

The user selects a role and submits credentials. The backend validates the active account and selected role, then returns a bearer access token. The frontend stores the token in session storage unless the user chooses the persistent-login option, in which case local storage is used. Protected pages validate the token with the backend and enforce the returned role. Logout clears stored authentication state.

Never share accounts across roles. Disable departed staff accounts promptly and rotate secrets through the approved environment-management process.

## 7. Student and parent linking

Links are stored between existing parent and student records. Parent APIs restrict child data to these links. One parent may legitimately be linked to multiple siblings.

Production audit on 5 November 2026 found 2,292 active students, 1,877 linked students, 1,718 linked active parents, 155 parents with multiple children, no duplicate link groups, and no orphan link references. The remaining 415 active students have no relationship row; that is a reconciliation queue, not permission to guess links.

Safe correction procedure:

1. Obtain an authoritative, school-approved mapping using stable identifiers.
2. Validate that each student and parent exists, roles and active states are correct, and intended sibling groupings are explicit.
3. Produce a dry-run summary of creates, skips, conflicts, and duplicates without personal data in logs.
4. Obtain approval for the exact production write, create and verify a pre-change backup, and apply all changes in one auditable transaction.
5. Re-run orphan, duplicate, unlinked, and sibling-count checks; then test one school-designated account.

Do not infer a relationship from names, phone numbers, row order, or an inactive account alone.

## 8. Attendance and homework

Teachers maintain attendance and homework for permitted classes. Parents can read these records only for linked children. Always confirm class, student, and date before saving attendance. Correct mistakes through the owning teacher/admin workflow and retain the original business context in operational notes.

## 9. Exams and results

Teachers maintain exam schedules and results within assigned permissions. Parents can review schedules and results for linked children. Verify class, subject, exam, and student before publishing results; use the existing edit flow for corrections rather than creating a second result for the same assessment.

## 10. Fees and receipts

Admins maintain student fee records and payment details. Parents have read-only access to the linked child's recorded fees, payment status, payment mode, and receipt number. Reconcile any payment change with the school's financial source before editing. Never use demo data as a financial record.

The production audit recorded 632 fee rows with a total amount of INR 30,588,800 on 5 November 2026.

## 11. Circulars and notifications

Admins publish circulars and notifications for their intended audiences. Teachers and parents receive only permitted content through their portals. Check audience, class scope, dates, and attachments before publishing. Demo-preview routes are disabled in production and must remain excluded from official communications.

## 12. Deployment and rollback

Follow [deployment.md](deployment.md) and the private operations runbook. The safe order is backend before frontend when the API contract changes.

Before deployment, record the approved commit SHAs, verify CI and tests, verify an immediately restorable backup, and inspect the Alembic current/head state. Deploy immutable backend releases; do not edit a live release directory. Run the service on loopback and use the existing process manager. Deploy the frontend from the approved commit through Vercel.

Merges, production migrations, deployments, service restarts, and network changes require explicit authorization. Roll back to the recorded previous builds. Restore a database backup instead of forcing an unsafe migration downgrade.

Verified release state on 5 November 2026:

- Backend main/deployed merge: `fb8b5cbabfe3de2f52b692e4ace418938bb49df4`.
- Frontend main/Vercel deployment: `c2ee616d72634e4f375f23d63f4b3cf5da2ca937`.
- Alembic current and head: `c37b0e63a001`.

## 13. Backup and recovery

Keep database backups outside public web roots and repositories. After creation, store and verify a SHA-256 checksum. Periodically restore a selected backup into an isolated MySQL instance and validate schema and aggregate row counts without connecting it to production traffic.

On 5 November 2026, the pre-swap backup checksum passed and the dump restored into a disposable MySQL 8 container with 18 tables and the expected core aggregate counts. The container was removed after validation.

Production restoration requires explicit approval, a named backup, an outage/traffic plan, and post-restore health and portal smoke tests.

## 14. Security and permissions

- Keep both source repositories private and restrict access to named maintainers.
- Never commit `.env` files, credentials, database dumps, student exports, or private keys.
- Use HTTPS for public traffic and keep the backend and database bound to loopback/private interfaces.
- Enforce role authorization in the backend; frontend guards are an additional user-experience control, not the security boundary.
- Review active staff/admin accounts and repository/server access regularly.
- Treat logs, backups, exports, and screenshots containing personal data as confidential school records.
- Rotate secrets after personnel or vendor access changes and after any suspected exposure.

## 15. Known limitations

- 415 active students were unlinked in the 5 November aggregate audit and require authoritative school reconciliation.
- Authenticated production workflows and the live sibling-switch experience still require a school-designated test account; no real family account should be borrowed for QA.
- PM2 status and log review require authorized privileged server access.
- The fees module records school-entered fee and receipt information; it does not process online payments.
- Password recovery depends on the configured recovery process; school administrators must maintain valid account/contact data.

## 16. Maintenance checklist

Daily/operational:

- Confirm the public health endpoint is HTTP 200 and reports database connected.
- Review application errors without copying secrets or personal data into tickets.
- Verify important fee, attendance, and result corrections with the owning school team.

Before every release:

- Confirm repository privacy and least-privilege access.
- Require reviewed pull requests and passing backend/frontend CI.
- Run backend tests, frontend lint/build, and Playwright tests.
- Record release and rollback SHAs.
- Create, checksum, and restore-test a pre-release backup.
- Confirm Alembic current equals the intended head.
- Obtain approvals for merge, migration, deployment, restart, or network work.
- Smoke-test authentication, role isolation, core modules, sibling selection, and mobile/tablet navigation with designated test accounts.

Monthly/quarterly:

- Audit inactive and privileged accounts.
- Reconcile unlinked students and parent relationships.
- Review backup retention and perform an isolated recovery drill.
- Review TLS expiry, dependency/security updates, server storage, and process-manager logs.
- Confirm the direct application and database ports are not publicly reachable.
