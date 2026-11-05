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
