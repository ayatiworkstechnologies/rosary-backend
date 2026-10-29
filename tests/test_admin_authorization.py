import tests._env  # noqa: F401  (isolates the test database - keep first)
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies import get_current_admin, get_current_user


class _FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.user


class _FakeSession:
    def __init__(self, user):
        self.user = user

    def query(self, _model):
        return _FakeQuery(self.user)


class AdminAuthorizationTests(unittest.TestCase):
    secret = "test-secret-key-that-is-at-least-32-bytes-long"

    def test_admin_role_is_accepted_case_insensitively(self):
        user = SimpleNamespace(role="admin")

        self.assertIs(get_current_admin(user), user)

    def test_non_admin_role_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            get_current_admin(SimpleNamespace(role="TEACHER"))

        self.assertEqual(raised.exception.status_code, 403)

    def test_valid_token_returns_active_user(self):
        secret = self.secret
        token = jwt.encode({"sub": "42"}, secret, algorithm="HS256")
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token,
        )
        user = SimpleNamespace(id=42, role="ADMIN", is_active=True)

        with patch("app.dependencies.SECRET_KEY", secret):
            result = get_current_user(credentials, _FakeSession(user))

        self.assertIs(result, user)

    def test_invalid_token_is_rejected(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="not-a-jwt",
        )

        with patch("app.dependencies.SECRET_KEY", self.secret):
            with self.assertRaises(HTTPException) as raised:
                get_current_user(credentials, _FakeSession(None))

        self.assertEqual(raised.exception.status_code, 401)

    def test_inactive_user_is_rejected(self):
        secret = self.secret
        token = jwt.encode({"sub": "42"}, secret, algorithm="HS256")
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token,
        )
        user = SimpleNamespace(id=42, role="ADMIN", is_active=False)

        with patch("app.dependencies.SECRET_KEY", secret):
            with self.assertRaises(HTTPException) as raised:
                get_current_user(credentials, _FakeSession(user))

        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
