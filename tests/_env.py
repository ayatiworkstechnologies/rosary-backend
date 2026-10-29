"""Environment guard for the test suite.

Every test module must import this module BEFORE any ``app`` import so the
app is always bound to an isolated SQLite test database, never to the
database configured in ``.env`` (which may be production MySQL).
"""
import os

# An explicitly provided DATABASE_URL pointing at the dedicated MySQL test
# database (set from the DBA-prepared env file) is honored. Anything else -
# including the production URL that load_dotenv() may pick up from .env -
# is replaced with the isolated in-memory SQLite database.
_EXISTING_URL = os.environ.get("DATABASE_URL", "")

if "rosary_portal_test" not in _EXISTING_URL:
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-bytes")
os.environ.setdefault("ALGORITHM", "HS256")


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
