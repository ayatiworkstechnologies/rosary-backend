# Deployment and rollback

## Release order

Deploy the backend before the frontend when a release changes the API contract.

## Pre-deployment

1. Confirm the backend and frontend pull requests are approved.
2. Confirm backend CI, frontend lint, frontend build, and Playwright tests pass.
3. Record the backend and frontend commit SHAs being released.
4. Back up the production database and verify that the backup can be restored.
5. Confirm production environment variables without printing their values:
   - Backend: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `CORS_ORIGINS`
   - Frontend: `NEXT_PUBLIC_API_URL`

## Database and backend

```powershell
alembic current
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8016
```

Use the production process manager instead of starting a second Uvicorn process when the service is already managed.

The production API must listen only on loopback. Never expose Uvicorn port
`8016` directly to the internet or use its plain-HTTP Swagger page with a JWT.
The live FastAPI process is root-managed as `rosary-backend`; it is not managed
by the devteam worker ecosystem file. From the approved versioned release,
the authorized root release operator reloads the existing process and exposes
the API only through the nginx HTTPS virtual host:

```bash
pm2 restart rosary-backend --update-env
pm2 logs rosary-backend --lines 100 --nostream
pm2 save
```

The devteam account manages only `rosary-email-worker`. Set
`ROSARY_BACKEND_RELEASE_DIR` to the same approved versioned release before
loading `ecosystem.config.cjs`; this must never create or replace FastAPI.

The operational-policy release adds Alembic revision `a7b8c9d0e1f2`. Back up
MySQL, confirm the current revision is `f5b2c3d4e5f6`, review the generated SQL,
then run `alembic upgrade head` from the approved versioned release. The API and
worker must use the same release because the worker reads the persisted
recipient policy, event reference, and suppression table. Keep the worker
stopped during migration/cutover; start it only after the API health and schema
revision checks pass.

All operational flags must remain false until the category approval register in
`OPERATIONAL_EMAIL_POLICY.md` is signed off. Verification-only operation is
independent and does not authorize optional or operational broadcast delivery.

The host firewall must deny public inbound traffic to `8016`. Confirm from an
external machine that `http://SERVER_IP:8016/health` is unreachable while the
HTTPS domain health endpoint remains available.

Verify `/health` returns HTTP 200 with:

```json
{"status":"healthy","database":"connected"}
```

Database failures return HTTP 503 and do not disclose connection details.

## Frontend

Build with the production `NEXT_PUBLIC_API_URL`, then deploy the immutable build produced from the recorded frontend commit.

```powershell
npm ci
npm run lint
npm run build
```

## Smoke test

- Admin, teacher, and parent authentication
- Role isolation between portals
- Classes, students, teachers, and parent linking
- Attendance, homework, exams, results, and fees
- Circulars, downloads, calendars, and notifications
- Tablet and mobile navigation

## Rollback

1. Stop rollout traffic or enable the platform's maintenance mode.
2. Restore the previous frontend and backend commit builds.
3. If a migration is explicitly reversible, inspect the target first and run `alembic downgrade <previous_revision>`.
4. If a migration is destructive or not safely reversible, restore the verified pre-deployment database backup instead of forcing a downgrade.
5. Re-run the health check and smoke test before reopening traffic.

Never run a downgrade or restore against production without confirming the exact revision and backup target.
