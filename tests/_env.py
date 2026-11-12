"""Environment guard for the test suite.

Every test module must import this module BEFORE any ``app`` import so the
app is always bound to an isolated SQLite test database, never to the
database configured in ``.env`` (which may be production MySQL).
"""
import os

# Never inherit DATABASE_URL: developer shells and .env files may point at
# shared or production data. A non-SQLite integration database requires the
# separately named, deliberate ROSARY_TEST_DATABASE_URL opt-in.
_TEST_URL = os.environ.get(
    "ROSARY_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:"
).strip()
if not (_TEST_URL.startswith("sqlite") or "rosary_portal_test" in _TEST_URL):
    raise RuntimeError(
        "ROSARY_TEST_DATABASE_URL must use SQLite or the dedicated "
        "rosary_portal_test database"
    )
os.environ["DATABASE_URL"] = _TEST_URL

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-bytes")
os.environ.setdefault("ALGORITHM", "HS256")
# Tests must never inherit real SMTP or automatic-broadcast settings from the
# developer shell or local .env. Individual tests may temporarily patch these
# values, but the suite-wide baseline is always mock and fail closed.
os.environ["EMAIL_NOTIFICATIONS_ENABLED"] = "true"
os.environ["EMAIL_TRANSPORT"] = "mock"
os.environ["EMAIL_AUTOMATION_TEST_MODE"] = "true"
os.environ["EMAIL_HOMEWORK_NOTIFICATIONS_ENABLED"] = "false"
os.environ["EMAIL_ATTENDANCE_NOTIFICATIONS_ENABLED"] = "false"
os.environ["EMAIL_RESULTS_NOTIFICATIONS_ENABLED"] = "false"
os.environ["EMAIL_CIRCULAR_NOTIFICATIONS_ENABLED"] = "false"
os.environ["EMAIL_EVENT_NOTIFICATIONS_ENABLED"] = "false"
os.environ["EMAIL_FEE_PAYMENT_NOTIFICATIONS_ENABLED"] = "false"
os.environ["EMAIL_HOMEWORK_TEST_RECIPIENTS"] = ""
os.environ["EMAIL_ATTENDANCE_TEST_RECIPIENTS"] = ""
os.environ["EMAIL_RESULTS_TEST_RECIPIENTS"] = ""
os.environ["EMAIL_CIRCULAR_TEST_RECIPIENTS"] = ""
os.environ["EMAIL_EVENT_TEST_RECIPIENTS"] = ""
os.environ["EMAIL_FEE_PAYMENT_TEST_RECIPIENTS"] = ""
os.environ.setdefault("SMTP_FROM_EMAIL", "no-reply@example.com")
os.environ.setdefault("EMAIL_RATE_LIMIT_PER_SECOND", "0")
os.environ.setdefault("EMAIL_RETRY_BASE_SECONDS", "1")


def _assert_isolated():
    url = os.environ.get("DATABASE_URL", "")
    allowed = (
        url.startswith("sqlite")
        or "rosary_portal_test" in url
    )
    if not allowed:
        raise RuntimeError(
            "Test suite must run against sqlite:// or rosary_portal_test; "
            f"refusing DATABASE_URL: {url}"
        )


_assert_isolated()
