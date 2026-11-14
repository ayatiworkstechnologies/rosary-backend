"""Parent email verification, opt-in, and unsubscribe tests."""

import tests._env  # noqa: F401 - isolate DB before importing app modules

from datetime import datetime, timezone
from unittest.mock import patch

from app.database import SessionLocal
from app.models.email_verification import EmailVerificationToken
from app.models.user import User
from app.services.parent_email_preferences_service import create_unsubscribe_token
from app.services.parent_email_preferences_service import send_verification_email
from app.services.parent_email_service import MockEmailTransport
from tests.api_base import ApiTestBase


class ParentEmailPreferenceTests(ApiTestBase):
    def tearDown(self):
        db = SessionLocal()
        try:
            db.query(EmailVerificationToken).filter(
                EmailVerificationToken.user_id.in_(
                    [self.ids["parent"], self.ids["other_parent"]]
                )
            ).delete(synchronize_session=False)
            for user_id in (self.ids["parent"], self.ids["other_parent"]):
                user = db.get(User, user_id)
                user.email_verified_at = datetime.now(timezone.utc)
                user.email_notifications_enabled = True
            db.commit()
        finally:
            db.close()

    def test_verification_is_one_time_then_parent_explicitly_opts_in(self):
        raw_token = "synthetic-verification-token"
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent.email_verified_at = None
            parent.email_notifications_enabled = False
            db.commit()
        finally:
            db.close()

        with (
            patch(
                "app.services.parent_email_preferences_service.secrets.token_urlsafe",
                return_value=raw_token,
            ),
            patch(
                "app.routes.parent_email_preferences.send_verification_email"
            ) as send_email,
        ):
            requested = self.post(
                "/api/v1/parent/email-preferences/verification/request",
                self.tokens["parent"],
            )
        self.assertEqual(requested.status_code, 200, requested.text)
        send_email.assert_called_once()

        confirmed = self.post(
            "/api/v1/parent/email-preferences/verification/confirm",
            json={"token": raw_token},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertIsNotNone(confirmed.json()["email_verified_at"])
        self.assertFalse(confirmed.json()["email_notifications_enabled"])

        enabled = self.patch(
            "/api/v1/parent/email-preferences",
            self.tokens["parent"],
            json={"email_notifications_enabled": True},
        )
        self.assertEqual(enabled.status_code, 200, enabled.text)
        self.assertTrue(enabled.json()["email_notifications_enabled"])

        replay = self.post(
            "/api/v1/parent/email-preferences/verification/confirm",
            json={"token": raw_token},
        )
        self.assertEqual(replay.status_code, 400, replay.text)

    def test_unverified_parent_cannot_opt_in_but_can_opt_out(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent.email_verified_at = None
            parent.email_notifications_enabled = False
            db.commit()
        finally:
            db.close()

        enable = self.patch(
            "/api/v1/parent/email-preferences",
            self.tokens["parent"],
            json={"email_notifications_enabled": True},
        )
        self.assertEqual(enable.status_code, 409, enable.text)

        disable = self.patch(
            "/api/v1/parent/email-preferences",
            self.tokens["parent"],
            json={"email_notifications_enabled": False},
        )
        self.assertEqual(disable.status_code, 200, disable.text)
        self.assertFalse(disable.json()["email_notifications_enabled"])

    def test_signed_unsubscribe_is_public_idempotent_and_address_bound(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            token = create_unsubscribe_token(parent)
        finally:
            db.close()

        first = self.post(
            "/api/v1/parent/email-preferences/unsubscribe",
            params={"token": token},
        )
        self.assertEqual(first.status_code, 200, first.text)
        second = self.post(
            "/api/v1/parent/email-preferences/unsubscribe",
            params={"token": token},
        )
        self.assertEqual(second.status_code, 200, second.text)

        preferences = self.get(
            "/api/v1/parent/email-preferences",
            self.tokens["parent"],
        )
        self.assertFalse(preferences.json()["email_notifications_enabled"])

        invalid = self.post(
            "/api/v1/parent/email-preferences/unsubscribe",
            params={"token": token + "tampered"},
        )
        self.assertEqual(invalid.status_code, 400, invalid.text)

    def test_only_parents_can_access_authenticated_preferences(self):
        forbidden = self.get(
            "/api/v1/parent/email-preferences",
            self.tokens["teacher"],
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

    def test_verification_email_has_independent_gate_from_bulk_email(self):
        transport = MockEmailTransport()
        with patch.dict(
            "os.environ",
            {
                "EMAIL_NOTIFICATIONS_ENABLED": "false",
                "EMAIL_VERIFICATION_ENABLED": "true",
                "EMAIL_TRANSPORT": "mock",
            },
            clear=False,
        ):
            message_id = send_verification_email(
                "parent@example.com", "synthetic-token", transport=transport
            )
        self.assertTrue(message_id.startswith("mock-"))
        self.assertEqual(transport.sent, ["parent@example.com"])

    def test_verification_requests_are_disabled_and_rate_limited_safely(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent.email_verified_at = None
            parent.email_notifications_enabled = False
            db.commit()
        finally:
            db.close()

        with patch.dict(
            "os.environ", {"EMAIL_VERIFICATION_ENABLED": "false"}, clear=False
        ):
            disabled = self.post(
                "/api/v1/parent/email-preferences/verification/request",
                self.tokens["parent"],
            )
        self.assertEqual(disabled.status_code, 503, disabled.text)

        env = {
            "EMAIL_VERIFICATION_ENABLED": "true",
            "EMAIL_VERIFICATION_MAX_REQUESTS": "1",
            "EMAIL_VERIFICATION_WINDOW_SECONDS": "3600",
            "EMAIL_VERIFICATION_COOLDOWN_SECONDS": "60",
        }
        with (
            patch.dict("os.environ", env, clear=False),
            patch("app.routes.parent_email_preferences.send_verification_email"),
        ):
            first = self.post(
                "/api/v1/parent/email-preferences/verification/request",
                self.tokens["parent"],
            )
            second = self.post(
                "/api/v1/parent/email-preferences/verification/request",
                self.tokens["parent"],
            )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 429, second.text)
        self.assertIn("Retry-After", second.headers)

    def test_admin_health_supports_verification_only_mode(self):
        env = {
            "EMAIL_NOTIFICATIONS_ENABLED": "false",
            "EMAIL_VERIFICATION_ENABLED": "true",
            "EMAIL_TRANSPORT": "mock",
        }
        with patch.dict("os.environ", env, clear=False):
            status_response = self.get(
                "/api/v1/admin/notifications/email-status", self.tokens["admin"]
            )
            health_response = self.get(
                "/api/v1/admin/notifications/email-health", self.tokens["admin"]
            )
        self.assertEqual(status_response.status_code, 200, status_response.text)
        self.assertFalse(status_response.json()["enabled"])
        self.assertTrue(status_response.json()["verification_enabled"])
        self.assertEqual(status_response.json()["delivery_mode"], "disabled")
        self.assertIn("In-app notifications remain available", status_response.json()["delivery_status_message"])
        self.assertEqual(health_response.json()["status"], "ok")

    def test_admin_email_status_reports_test_and_available_modes(self):
        modes = [
            ({"EMAIL_NOTIFICATIONS_ENABLED": "true", "EMAIL_TRANSPORT": "mock", "EMAIL_AUTOMATION_TEST_MODE": "true"}, "test"),
            ({"EMAIL_NOTIFICATIONS_ENABLED": "true", "EMAIL_TRANSPORT": "mock", "EMAIL_AUTOMATION_TEST_MODE": "false"}, "available"),
            ({"EMAIL_NOTIFICATIONS_ENABLED": "true", "EMAIL_TRANSPORT": "smtp", "SMTP_HOST": "", "EMAIL_AUTOMATION_TEST_MODE": "false"}, "misconfigured"),
        ]
        for env, expected_mode in modes:
            with self.subTest(expected_mode=expected_mode), patch.dict(
                "os.environ", env, clear=False
            ):
                response = self.get(
                    "/api/v1/admin/notifications/email-status",
                    self.tokens["admin"],
                )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["delivery_mode"], expected_mode)
            self.assertTrue(response.json()["delivery_status_message"])

    def test_missing_or_changed_email_cannot_be_verified(self):
        raw_token = "email-change-bound-token"
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            original_email = parent.email
            parent.email_verified_at = None
            db.commit()
        finally:
            db.close()

        with (
            patch(
                "app.services.parent_email_preferences_service.secrets.token_urlsafe",
                return_value=raw_token,
            ),
            patch("app.routes.parent_email_preferences.send_verification_email"),
        ):
            requested = self.post(
                "/api/v1/parent/email-preferences/verification/request",
                self.tokens["parent"],
            )
        self.assertEqual(requested.status_code, 200, requested.text)

        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent.email = "changed.parent@example.com"
            parent.email_verified_at = None
            parent.email_notifications_enabled = False
            db.commit()
        finally:
            db.close()

        changed = self.post(
            "/api/v1/parent/email-preferences/verification/confirm",
            json={"token": raw_token},
        )
        self.assertEqual(changed.status_code, 400, changed.text)

        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent.email = original_email
            parent.email_verified_at = None
            db.commit()
        finally:
            db.close()
