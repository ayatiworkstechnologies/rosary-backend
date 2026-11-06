# Rosary School Portal API

FastAPI backend for the Rosary School admin, teacher, and parent portals.

## Main capabilities

- JWT authentication with admin, teacher, and parent authorization
- Class, student, teacher, parent, fee, exam, result, circular, download, and calendar administration
- Teacher attendance, homework, result, roster, and exam-schedule workflows
- Parent dashboard, linked-child, attendance, homework, result, fee, download, and calendar workflows
- Role-scoped notifications

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Create `.env` with `DATABASE_URL`, `SECRET_KEY`, and optional `CORS_ORIGINS`.
4. Apply migrations:

   ```powershell
   alembic upgrade head
   ```

5. Start the API:

   ```powershell
   uvicorn app.main:app --reload
   ```

The API is available at `http://127.0.0.1:8000`; health is reported by `/health`.

## Verification

```powershell
python -m pytest -q
```

The test suite replaces ordinary database configuration with isolated SQLite. A dedicated database is used only when its URL contains `rosary_portal_test`.

## Database lifecycle

Application startup does not create or modify database tables. Schema changes must be represented by Alembic migrations and applied explicitly.

See [docs/deployment.md](docs/deployment.md) for release and rollback steps and
[docs/client-handover.md](docs/client-handover.md) for the operations and user
handover guide.
