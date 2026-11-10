"""Parent email verification, opt-in, and unsubscribe tests."""

import tests._env  # noqa: F401 - isolate DB before importing app modules

from datetime import datetime, timezone
from unittest.mock import patch

from app.database import SessionLocal
from app.models.email_verification import EmailVerificationToken
from app.models.user import User
from app.services.parent_email_preferences_service import create_unsubscribe_token
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
