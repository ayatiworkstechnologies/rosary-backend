"""Login throttling tests use only the isolated synthetic application."""

import os
from unittest.mock import patch

import tests._env  # noqa: F401

from app.routes.auth import _reset_login_limiter_for_tests
from tests.api_base import ApiTestBase


class LoginRateLimitTests(ApiTestBase):
    def setUp(self):
        _reset_login_limiter_for_tests()

    def tearDown(self):
        _reset_login_limiter_for_tests()

    def test_repeated_failures_are_temporarily_blocked(self):
        env = {
            "LOGIN_MAX_FAILED_ATTEMPTS": "2",
            "LOGIN_MAX_FAILED_ATTEMPTS_PER_IP": "50",
            "LOGIN_ATTEMPT_WINDOW_SECONDS": "60",
            "LOGIN_LOCKOUT_SECONDS": "60",
        }
        payload = {
            "username": "RATE_LIMIT_TEST_UNKNOWN",
            "password": "wrong",
            "role": "ADMIN",
        }
        with patch.dict(os.environ, env, clear=False):
            first = self.client.post("/api/v1/auth/login", json=payload)
            second = self.client.post("/api/v1/auth/login", json=payload)
            blocked = self.client.post("/api/v1/auth/login", json=payload)

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 401)
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Retry-After", blocked.headers)

    def test_successful_login_clears_account_failures(self):
        env = {
            "LOGIN_MAX_FAILED_ATTEMPTS": "3",
            "LOGIN_MAX_FAILED_ATTEMPTS_PER_IP": "50",
            "LOGIN_ATTEMPT_WINDOW_SECONDS": "60",
            "LOGIN_LOCKOUT_SECONDS": "60",
        }
        wrong = {
            "username": "ADM_TEST",
            "password": "wrong",
            "role": "ADMIN",
        }
        correct = {
            "username": "ADM_TEST",
            "password": "Admin@Test1!",
            "role": "ADMIN",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(
                self.client.post("/api/v1/auth/login", json=wrong).status_code,
                401,
            )
            self.assertEqual(
                self.client.post("/api/v1/auth/login", json=correct).status_code,
                200,
            )
            self.assertEqual(
                self.client.post("/api/v1/auth/login", json=wrong).status_code,
                401,
            )

