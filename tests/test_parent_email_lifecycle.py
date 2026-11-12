"""One isolated parent-email lifecycle using synthetic data and mock delivery."""

import os
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import tests._env  # noqa: F401 - configure disposable SQLite before app imports

from app.database import SessionLocal
from app.models.email_notification import EmailDelivery, EmailNotificationBatch
from app.models.email_verification import EmailVerificationToken
from app.models.homework import Homework
from app.models.notification import Notification
from app.models.user import User
from app.services.parent_email_preferences_service import create_unsubscribe_token
from app.services.parent_email_service import MockEmailTransport, process_email_queue
from tests.api_base import ApiTestBase


class ParentEmailLifecycleTests(ApiTestBase):
    title_prefix = "PARENT EMAIL LIFECYCLE"

    def setUp(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent.email_verified_at = None
            parent.email_notifications_enabled = False
            db.query(EmailVerificationToken).filter_by(user_id=parent.id).delete()
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        db = SessionLocal()
        try:
            homework_ids = [
                row[0]
                for row in db.query(Homework.id)
                .filter(Homework.title.like(f"{self.title_prefix}%"))
                .all()
            ]
            batch_ids = [
                row[0]
                for row in db.query(EmailNotificationBatch.id)
                .filter(EmailNotificationBatch.message.like(f"%{self.title_prefix}%"))
                .all()
            ]
            if batch_ids:
                db.query(EmailDelivery).filter(
                    EmailDelivery.batch_id.in_(batch_ids)
                ).delete(synchronize_session=False)
                db.query(EmailNotificationBatch).filter(
                    EmailNotificationBatch.id.in_(batch_ids)
                ).delete(synchronize_session=False)
            if homework_ids:
                db.query(Notification).filter(
                    Notification.notification_type == "HOMEWORK",
                    Notification.reference_id.in_(homework_ids),
                ).delete(synchronize_session=False)
                db.query(Homework).filter(Homework.id.in_(homework_ids)).delete(
                    synchronize_session=False
                )
            db.query(EmailVerificationToken).filter_by(
                user_id=self.ids["parent"]
            ).delete()
            parent = db.get(User, self.ids["parent"])
            parent.email_verified_at = datetime.now(timezone.utc)
            parent.email_notifications_enabled = True
            db.commit()
        finally:
            db.close()

    def _create_homework(self, suffix: str):
        return self.post(
            f"/api/v1/teacher/classes/{self.ids['class_a']}/homework",
            self.tokens["teacher"],
            json={
                "subject": "ignored-client-value",
                "title": f"{self.title_prefix} {suffix}",
                "assigned_date": date.today().isoformat(),
                "due_date": (date.today() + timedelta(days=2)).isoformat(),
            },
        )

    def test_verification_opt_in_delivery_unsubscribe_and_later_block(self):
        verification_token = "synthetic-full-lifecycle-verification-token"
        verification_env = {
            "EMAIL_NOTIFICATIONS_ENABLED": "false",
            "EMAIL_VERIFICATION_ENABLED": "true",
            "EMAIL_TRANSPORT": "mock",
            "EMAIL_VERIFICATION_MAX_REQUESTS": "3",
            "EMAIL_VERIFICATION_WINDOW_SECONDS": "3600",
            "EMAIL_VERIFICATION_COOLDOWN_SECONDS": "0",
        }
        with (
            patch.dict(os.environ, verification_env, clear=False),
            patch(
                "app.services.parent_email_preferences_service.secrets.token_urlsafe",
                return_value=verification_token,
            ),
            patch(
                "app.routes.parent_email_preferences.send_verification_email"
            ) as send_verification,
        ):
            requested = self.post(
                "/api/v1/parent/email-preferences/verification/request",
                self.tokens["parent"],
            )
        self.assertEqual(requested.status_code, 200, requested.text)
        send_verification.assert_called_once()

        confirmed = self.post(
            "/api/v1/parent/email-preferences/verification/confirm",
            json={"token": verification_token},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertIsNotNone(confirmed.json()["email_verified_at"])
        self.assertFalse(confirmed.json()["email_notifications_enabled"])

        opted_in = self.patch(
            "/api/v1/parent/email-preferences",
            self.tokens["parent"],
            json={"email_notifications_enabled": True},
        )
        self.assertEqual(opted_in.status_code, 200, opted_in.text)
        self.assertTrue(opted_in.json()["email_notifications_enabled"])

        delivery_env = {
            "EMAIL_NOTIFICATIONS_ENABLED": "true",
            "EMAIL_HOMEWORK_NOTIFICATIONS_ENABLED": "true",
            "EMAIL_AUTOMATION_TEST_MODE": "false",
            "EMAIL_TRANSPORT": "mock",
            "EMAIL_RATE_LIMIT_PER_SECOND": "0",
        }
        with patch.dict(os.environ, delivery_env, clear=False):
            first = self._create_homework("FIRST")
            self.assertEqual(first.status_code, 201, first.text)
            first_id = first.json()["id"]

            db = SessionLocal()
            try:
                first_batch = (
                    db.query(EmailNotificationBatch)
                    .filter_by(category="HOMEWORK", target_type="AUTOMATIC_HOMEWORK")
                    .filter(EmailNotificationBatch.message.like(f"%{self.title_prefix}%"))
                    .order_by(EmailNotificationBatch.id.desc())
                    .first()
                )
                self.assertIsNotNone(first_batch)
                self.assertEqual(first_batch.email_recipient_count, 1)
                self.assertIn(self.title_prefix, first_batch.message)
                delivery = db.query(EmailDelivery).filter_by(
                    batch_id=first_batch.id
                ).one()
                self.assertEqual(delivery.status, "QUEUED")

                transport = MockEmailTransport()
                processed = process_email_queue(db, transport=transport)
                self.assertEqual(processed["sent"], 1)
                self.assertEqual(len(transport.sent), 1)
                db.refresh(delivery)
                db.refresh(first_batch)
                self.assertEqual(delivery.status, "SENT")
                self.assertEqual(first_batch.status, "COMPLETED")
            finally:
                db.close()

        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            unsubscribe_token = create_unsubscribe_token(parent)
        finally:
            db.close()

        unsubscribed = self.post(
            "/api/v1/parent/email-preferences/unsubscribe",
            params={"token": unsubscribe_token},
        )
        self.assertEqual(unsubscribed.status_code, 200, unsubscribed.text)
        db = SessionLocal()
        try:
            self.assertFalse(
                db.get(User, self.ids["parent"]).email_notifications_enabled
            )
        finally:
            db.close()

        with patch.dict(os.environ, delivery_env, clear=False):
            second = self._create_homework("AFTER UNSUBSCRIBE")
        self.assertEqual(second.status_code, 201, second.text)
        second_id = second.json()["id"]

        db = SessionLocal()
        try:
            second_batch = (
                db.query(EmailNotificationBatch)
                .filter_by(category="HOMEWORK", target_type="AUTOMATIC_HOMEWORK")
                .filter(EmailNotificationBatch.message.like(f"%AFTER UNSUBSCRIBE%"))
                .one()
            )
            self.assertEqual(second_batch.status, "NO_RECIPIENTS")
            self.assertEqual(second_batch.email_recipient_count, 0)
            self.assertEqual(second_batch.opted_out_count, 1)
            self.assertEqual(
                db.query(EmailDelivery).filter_by(batch_id=second_batch.id).count(), 0
            )
            self.assertEqual(
                db.query(Notification).filter_by(
                    user_id=self.ids["parent"],
                    notification_type="HOMEWORK",
                    reference_id=second_id,
                ).count(),
                1,
            )
            self.assertNotEqual(first_id, second_id)
        finally:
            db.close()
