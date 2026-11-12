"""Local E2E test server (NEVER production).

Boots the FastAPI app against a disposable file-based SQLite database
seeded with the synthetic TEST_* fixtures, and writes the synthetic
account credentials to a gitignored JSON file that the Playwright
suite reads.

Safety guarantees:
- Refuses to run with any MySQL DATABASE_URL.
- Binds only to 127.0.0.1 on port 8017 (production runs 8016 under PM2;
  this script is standalone and does not touch PM2 in any way).

Usage (from the backend repo root):
    venv\\Scripts\\python.exe scripts\\e2e_server.py

The Playwright webServer config starts and stops this process.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = BACKEND_ROOT.parent / "rosary-frontend"

# Optional, gitignored developer overrides such as E2E_PARENT_EMAIL. This is
# loaded only by the disposable local E2E server, never by production.
load_dotenv(BACKEND_ROOT / ".env.e2e.local", override=False)

DB_PATH = Path(os.environ.get(
    "E2E_DB_PATH",
    BACKEND_ROOT / "e2e_data" / "rosary_portal_test_e2e.db",
))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite+pysqlite:///{DB_PATH.as_posix()}"

if "mysql" in DATABASE_URL.lower():
    raise RuntimeError("E2E server must never run against MySQL")

os.environ["DATABASE_URL"] = DATABASE_URL
# tests._env intentionally refuses to inherit DATABASE_URL. This is the
# explicit, already-validated SQLite opt-in used by the fixture importer.
os.environ["ROSARY_TEST_DATABASE_URL"] = DATABASE_URL
os.environ.setdefault(
    "SECRET_KEY", "e2e-only-secret-key-that-is-at-least-32-bytes-long"
)
os.environ.setdefault("ALGORITHM", "HS256")
# Email tests must never contact a real provider. The feature is enabled so
# browser tests can exercise previews and queue creation; the worker is not
# started by this server and the only permitted transport is the in-memory
# mock.
os.environ["EMAIL_NOTIFICATIONS_ENABLED"] = "true"
os.environ["EMAIL_TRANSPORT"] = "mock"
os.environ["EMAIL_VERIFICATION_ENABLED"] = "true"
os.environ["EMAIL_VERIFICATION_COOLDOWN_SECONDS"] = "1"
os.environ["SMTP_FROM_EMAIL"] = "school@example.com"
os.environ["EMAIL_RATE_LIMIT_PER_SECOND"] = "0"

# Recreate a fresh database on every boot so tests always start
# from a known state.
if DB_PATH.exists():
    DB_PATH.unlink()

# Make sure the app resolves modules from the backend repo root.
sys.path.insert(0, str(BACKEND_ROOT))


def seed_and_write_accounts():
    """Seed the synthetic dataset and export account credentials."""
    from tests.fixtures import init_test_db

    ids = init_test_db()

    accounts = {
        "note": "SYNTHETIC E2E ONLY - these accounts exist solely in the "
                "disposable e2e_data sqlite database and can never touch "
                "production data.",
        "admin": {
            "username": "ADM_TEST",
            "password": os.environ.get("E2E_ADMIN_PW", "Admin@Test1!"),
            "role": "ADMIN",
        },
        "teacher": {
            "username": "TEACH_TEST",
            "password": os.environ.get("E2E_TEACHER_PW", "Teach@Test1!"),
            "role": "TEACHER",
        },
        "teacher_other": {
            "username": "TEACH_OTHER",
            "password": os.environ.get("E2E_TEACHER_OTHER_PW", "Other@Test1!"),
            "role": "TEACHER",
        },
        "parent": {
            "username": "PAR_TEST",
            "password": os.environ.get("E2E_PARENT_PW", "Par@Test1!"),
            "role": "PARENT",
            "admission_numbers": ["TESTADM1", "TESTADM2"],
        },
        "parent_other": {
            "username": "PAR_OTHER",
            "password": os.environ.get("E2E_PARENT_OTHER_PW", "Other@Test1!"),
            "role": "PARENT",
            "admission_numbers": ["TESTADM3"],
        },
        "class_a_id": ids["class_a"],
        "class_b_id": ids["class_b"],
        "student1_id": ids["s1"],
        "student2_id": ids["s2"],
        "student3_id": ids["s3"],
        "exam_id": ids["exam"],
        "exam2_id": ids["exam2"],
    }

    out_path = Path(
        os.environ.get(
            "E2E_ACCOUNTS_PATH",
            FRONTEND_ROOT / "e2e" / ".test-accounts.json",
        )
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(accounts, indent=2), encoding="utf-8")
    print(f"E2E accounts written to {out_path}")


def main():
    seed_and_write_accounts()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8017,
        workers=1,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
