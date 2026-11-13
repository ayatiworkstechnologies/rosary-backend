"""Operational parent-email policy tests using synthetic SQLite and mock SMTP."""

import os
import smtplib
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import tests._env  # noqa: F401 - isolate DB before application imports

from app.database import SessionLocal
from app.models.email_notification import (
    EmailDelivery,
    EmailNotificationBatch,
    EmailSuppression,
)
from app.models.homework import Homework
from app.models.notification import Notification
from app.models.user import User
from app.services.automatic_email_service import (
    EVENT_FLAGS,
    OPERATIONAL_EVENT_FLAGS,
    operational_event_enabled,
    queue_parent_event_email,
)
from app.services.parent_email_service import (
    GENERIC_OPERATIONAL_MESSAGE,
    GENERIC_OPERATIONAL_SUBJECT,
    MockEmailTransport,
    process_email_queue,
    resolve_parent_email_recipients,
)
from tests.api_base import ApiTestBase


BASE_OPERATIONAL_ENV = {
    "EMAIL_NOTIFICATIONS_ENABLED": "true",
    "EMAIL_HOMEWORK_NOTIFICATIONS_ENABLED": "true",
    "EMAIL_OPERATIONAL_NOTIFICATIONS_ENABLED": "true",
    "EMAIL_HOMEWORK_OPERATIONAL_ENABLED": "true",
    "EMAIL_AUTOMATION_TEST_MODE": "false",
    "EMAIL_TRANSPORT": "mock",
    "EMAIL_RATE_LIMIT_PER_SECOND": "0",
}


class OperationalEmailPolicyTests(ApiTestBase):
    prefix = "OPERATIONAL POLICY TEST"

    def setUp(self):
        db = SessionLocal()
        try:
            for user_id in (self.ids["parent"], self.ids["other_parent"]):
                parent = db.get(User, user_id)
                parent.email_verified_at = datetime.now(timezone.utc)
                parent.email_notifications_enabled = True
                parent.is_active = True
            db.query(EmailSuppression).filter(
                EmailSuppression.email.like("%@example.com")
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        db = SessionLocal()
        try:
            homework_ids = [
                row[0]
                for row in db.query(Homework.id)
                .filter(Homework.title.like(f"{self.prefix}%"))
                .all()
            ]
            batch_ids = [
                row[0]
                for row in db.query(EmailNotificationBatch.id)
                .filter(EmailNotificationBatch.message.like(f"%{self.prefix}%"))
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
            db.query(EmailSuppression).filter(
                EmailSuppression.email.like("%@example.com")
            ).delete(synchronize_session=False)
            for user_id in (self.ids["parent"], self.ids["other_parent"]):
                parent = db.get(User, user_id)
                parent.email_verified_at = datetime.now(timezone.utc)
                parent.email_notifications_enabled = True
                parent.is_active = True
            db.commit()
        finally:
            db.close()

    def _create_homework(self, suffix: str):
        return self.post(
            f"/api/v1/teacher/classes/{self.ids['class_a']}/homework",
            self.tokens["teacher"],
            json={
                "subject": "ignored-client-value",
                "title": f"{self.prefix} {suffix}",
                "description": "Private student detail must not leave the portal",
                "assigned_date": date.today().isoformat(),
                "due_date": (date.today() + timedelta(days=2)).isoformat(),
            },
        )

    def test_unverified_parent_gets_only_generic_operational_homework_email(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent.email_verified_at = None
            parent.email_notifications_enabled = False
            db.commit()
        finally:
            db.close()

        with patch.dict(os.environ, BASE_OPERATIONAL_ENV, clear=False):
            response = self._create_homework("GENERIC")
            self.assertEqual(response.status_code, 201, response.text)
            homework_id = response.json()["id"]

            db = SessionLocal()
            try:
                batch = (
                    db.query(EmailNotificationBatch)
                    .filter(EmailNotificationBatch.message.like(f"%{self.prefix}%"))
                    .one()
                )
                self.assertEqual(batch.recipient_policy, "OPERATIONAL")
                self.assertEqual(batch.event_reference, str(homework_id))
                self.assertEqual(batch.email_recipient_count, 1)
                self.assertEqual(batch.verified_email_recipient_count, 0)
                self.assertEqual(batch.unverified_email_recipient_count, 1)

                transport = MockEmailTransport()
                result = process_email_queue(db, transport=transport)
                self.assertEqual(result["sent"], 1)
                self.assertEqual(len(transport.messages), 1)
                sent = transport.messages[0]
                self.assertEqual(sent["title"], GENERIC_OPERATIONAL_SUBJECT)
                self.assertEqual(sent["message"], GENERIC_OPERATIONAL_MESSAGE)
                self.assertNotIn(self.prefix, sent["message"])
                self.assertNotIn("student", sent["message"].lower())
                self.assertIsNone(sent["unsubscribe_url"])
            finally:
                db.close()

    def test_operational_policy_is_default_deny_and_optional_rules_remain(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent.email_verified_at = None
            parent.email_notifications_enabled = False
            db.commit()

            env = {
                "EMAIL_NOTIFICATIONS_ENABLED": "true",
                "EMAIL_HOMEWORK_NOTIFICATIONS_ENABLED": "true",
                "EMAIL_OPERATIONAL_NOTIFICATIONS_ENABLED": "false",
                "EMAIL_HOMEWORK_OPERATIONAL_ENABLED": "false",
                "EMAIL_AUTOMATION_TEST_MODE": "false",
            }
            with patch.dict(os.environ, env, clear=False):
                result = queue_parent_event_email(
                    db,
                    event_type="HOMEWORK",
                    reference_key=f"optional-{uuid.uuid4()}",
                    parent_ids=[parent.id],
                    created_by=self.ids["teacher"],
                    title="Optional only",
                    message=f"{self.prefix} optional rules",
                )
            batch = db.get(EmailNotificationBatch, result.batch_id)
            self.assertEqual(batch.recipient_policy, "OPTIONAL")
            self.assertEqual(batch.status, "NO_RECIPIENTS")
            self.assertEqual(batch.unverified_email_count, 1)
            self.assertEqual(batch.email_recipient_count, 0)
            self.assertFalse(parent.email_notifications_enabled)
            self.assertIsNone(parent.email_verified_at)
            db.commit()
        finally:
            db.close()

    def test_worker_honors_allowlist_or_policy_revocation_after_queueing(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent.email_verified_at = None
            parent.email_notifications_enabled = False
            queue_env = {
                **BASE_OPERATIONAL_ENV,
                "EMAIL_AUTOMATION_TEST_MODE": "true",
                "EMAIL_HOMEWORK_TEST_RECIPIENTS": parent.email,
            }
            with patch.dict(os.environ, queue_env, clear=False):
                queued = queue_parent_event_email(
                    db,
                    event_type="HOMEWORK",
                    reference_key=f"recheck-{uuid.uuid4()}",
                    parent_ids=[parent.id],
                    created_by=self.ids["teacher"],
                    title="Recheck",
                    message=f"{self.prefix} recheck",
                )
                db.commit()
            self.assertEqual(queued.queued_count, 1)

            blocked_env = {
                **queue_env,
                "EMAIL_HOMEWORK_TEST_RECIPIENTS": "",
            }
            transport = MockEmailTransport()
            with patch.dict(os.environ, blocked_env, clear=False):
                result = process_email_queue(db, transport=transport)
            self.assertEqual(result["failed"], 1)
            self.assertEqual(transport.sent, [])
            delivery = db.query(EmailDelivery).filter_by(
                batch_id=queued.batch_id
            ).one()
            self.assertEqual(delivery.status, "FAILED")
            self.assertNotIn(parent.email, delivery.last_error or "")
        finally:
            db.close()

    def test_suppression_blocks_both_policies_and_readiness_is_aggregate(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            parent_email = parent.email
        finally:
            db.close()

        created = self.post(
            "/api/v1/admin/notifications/email-suppressions",
            self.tokens["admin"],
            json={
                "email": parent_email,
                "reason": "Synthetic communication prohibition",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertNotIn(parent_email, created.text)

        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            suppression = db.query(EmailSuppression).filter_by(
                email=parent.email.lower()
            ).one()
            self.assertEqual(suppression.source, "ADMIN")
            self.assertEqual(suppression.created_by, self.ids["admin"])
            self.assertTrue(suppression.is_active)

            optional = resolve_parent_email_recipients(
                db, [parent.id], policy="OPTIONAL"
            )
            operational = resolve_parent_email_recipients(
                db, [parent.id], policy="OPERATIONAL"
            )
            self.assertEqual(optional.email_recipient_count, 0)
            self.assertEqual(operational.email_recipient_count, 0)
            self.assertEqual(optional.suppressed_email_count, 1)
            self.assertEqual(operational.suppressed_email_count, 1)
        finally:
            db.close()

        readiness = self.get(
            "/api/v1/admin/notifications/recipient-readiness",
            self.tokens["admin"],
        )
        self.assertEqual(readiness.status_code, 200, readiness.text)
        self.assertGreaterEqual(readiness.json()["suppressed_addresses"], 1)
        self.assertGreaterEqual(
            readiness.json()["parents_with_multiple_active_students"], 1
        )
        self.assertNotIn("@", readiness.text)
        forbidden = self.get(
            "/api/v1/admin/notifications/recipient-readiness",
            self.tokens["parent"],
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        removed = self.post(
            "/api/v1/admin/notifications/email-suppressions/remove",
            self.tokens["admin"],
            json={"email": parent_email},
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertNotIn(parent_email, removed.text)

    def test_admin_preview_is_optional_only_and_test_mode_fails_closed(self):
        env = {
            "EMAIL_AUTOMATION_TEST_MODE": "true",
            "EMAIL_ADMIN_TEST_RECIPIENTS": "",
        }
        with patch.dict(os.environ, env, clear=False):
            response = self.post(
                "/api/v1/admin/notifications/preview",
                self.tokens["admin"],
                json={
                    "target_type": "INDIVIDUAL_PARENT",
                    "parent_user_id": self.ids["parent"],
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["email_recipient_count"], 0)
        self.assertEqual(data["test_filtered_count"], 1)
        self.assertEqual(data["verified_email_recipient_count"], 0)
        self.assertEqual(data["operational_email_recipient_count"], 0)

    def test_permanent_recipient_rejection_creates_suppression(self):
        class RecipientRefusedTransport:
            def send(self, recipient, *_args, **_kwargs):
                raise smtplib.SMTPRecipientsRefused(
                    {recipient: (550, b"synthetic mailbox unavailable")}
                )

        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            env = {
                "EMAIL_NOTIFICATIONS_ENABLED": "true",
                "EMAIL_HOMEWORK_NOTIFICATIONS_ENABLED": "true",
                "EMAIL_OPERATIONAL_NOTIFICATIONS_ENABLED": "false",
                "EMAIL_AUTOMATION_TEST_MODE": "false",
                "EMAIL_TRANSPORT": "mock",
            }
            with patch.dict(os.environ, env, clear=False):
                queued = queue_parent_event_email(
                    db,
                    event_type="HOMEWORK",
                    reference_key=f"bounce-{uuid.uuid4()}",
                    parent_ids=[parent.id],
                    created_by=self.ids["teacher"],
                    title="Bounce",
                    message=f"{self.prefix} bounce",
                )
                db.commit()
                result = process_email_queue(
                    db, transport=RecipientRefusedTransport()
                )
            self.assertEqual(result["failed"], 1)
            suppression = db.query(EmailSuppression).filter_by(
                email=parent.email.lower()
            ).one()
            self.assertTrue(suppression.is_active)
            self.assertEqual(suppression.source, "SMTP_RECIPIENT_REFUSED")
            self.assertEqual(
                db.query(EmailDelivery).filter_by(batch_id=queued.batch_id).one().status,
                "FAILED",
            )
        finally:
            db.close()

    def test_every_operational_category_requires_master_and_category_approval(self):
        disabled = {flag: "false" for flag in OPERATIONAL_EVENT_FLAGS.values()}
        disabled["EMAIL_OPERATIONAL_NOTIFICATIONS_ENABLED"] = "false"
        with patch.dict(os.environ, disabled, clear=False):
            self.assertTrue(
                all(not operational_event_enabled(category) for category in EVENT_FLAGS)
            )

        for category, flag in OPERATIONAL_EVENT_FLAGS.items():
            env = {
                "EMAIL_OPERATIONAL_NOTIFICATIONS_ENABLED": "true",
                **{value: "false" for value in OPERATIONAL_EVENT_FLAGS.values()},
                flag: "true",
            }
            with patch.dict(os.environ, env, clear=False):
                self.assertTrue(operational_event_enabled(category))
                self.assertTrue(
                    all(
                        not operational_event_enabled(other)
                        for other in EVENT_FLAGS
                        if other != category
                    )
                )
