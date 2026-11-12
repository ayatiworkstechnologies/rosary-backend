"""Automatic homework email tests use only synthetic SQLite fixtures."""

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import tests._env  # noqa: F401 - isolate DB before importing app modules

from app.database import SessionLocal
from app.models.email_notification import EmailDelivery, EmailNotificationBatch
from app.models.homework import Homework
from app.models.notification import Notification
from app.models.user import User
from app.services.automatic_email_service import queue_parent_event_email
from app.services.parent_email_service import MockEmailTransport, process_email_queue
from tests.api_base import ApiTestBase


HOMEWORK_ENV = {
    "EMAIL_NOTIFICATIONS_ENABLED": "true",
    "EMAIL_HOMEWORK_NOTIFICATIONS_ENABLED": "true",
    "EMAIL_AUTOMATION_TEST_MODE": "false",
    "EMAIL_TRANSPORT": "mock",
}


class AutomaticHomeworkEmailTests(ApiTestBase):
    def tearDown(self):
        db = SessionLocal()
        try:
            batch_ids = [
                row[0]
                for row in db.query(EmailNotificationBatch.id)
                .filter(EmailNotificationBatch.target_type == "AUTOMATIC_HOMEWORK")
                .all()
            ]
            if batch_ids:
                db.query(EmailDelivery).filter(
                    EmailDelivery.batch_id.in_(batch_ids)
                ).delete(synchronize_session=False)
                db.query(EmailNotificationBatch).filter(
                    EmailNotificationBatch.id.in_(batch_ids)
                ).delete(synchronize_session=False)

            homework_ids = [
                row[0]
                for row in db.query(Homework.id)
                .filter(Homework.title.like("AUTO EMAIL TEST%"))
                .all()
            ]
            if homework_ids:
                db.query(Notification).filter(
                    Notification.notification_type == "HOMEWORK",
                    Notification.reference_id.in_(homework_ids),
                ).delete(synchronize_session=False)
                db.query(Homework).filter(Homework.id.in_(homework_ids)).delete(
                    synchronize_session=False
                )
            db.commit()
        finally:
            db.close()

    def _create_homework(self, title: str):
        return self.post(
            f"/api/v1/teacher/classes/{self.ids['class_a']}/homework",
            self.tokens["teacher"],
            json={
                "subject": "ignored-client-value",
                "title": title,
                "assigned_date": date.today().isoformat(),
                "due_date": (date.today() + timedelta(days=2)).isoformat(),
            },
        )

    def test_homework_queues_one_unique_parent_and_worker_sends(self):
        with patch.dict(os.environ, HOMEWORK_ENV, clear=False):
            response = self._create_homework("AUTO EMAIL TEST queue")
            self.assertEqual(response.status_code, 201, response.text)
            homework_id = response.json()["id"]

            db = SessionLocal()
            try:
                notifications = (
                    db.query(Notification)
                    .filter(
                        Notification.reference_id == homework_id,
                        Notification.notification_type == "HOMEWORK",
                    )
                    .all()
                )
                self.assertEqual(len(notifications), 1)

                batch = (
                    db.query(EmailNotificationBatch)
                    .filter_by(
                        target_type="AUTOMATIC_HOMEWORK",
                        category="HOMEWORK",
                    )
                    .order_by(EmailNotificationBatch.id.desc())
                    .first()
                )
                self.assertIsNotNone(batch)
                self.assertEqual(batch.parent_recipient_count, 1)
                self.assertEqual(batch.email_recipient_count, 1)
                self.assertIn("Mathematics", batch.message)
                self.assertIn(response.json()["title"], batch.message)
                self.assertIn(date.today().isoformat(), batch.message)
                self.assertEqual(
                    db.query(EmailDelivery).filter_by(batch_id=batch.id).count(),
                    1,
                )

                transport = MockEmailTransport()
                result = process_email_queue(db, transport=transport)
                self.assertEqual(result["sent"], 1)
                self.assertEqual(len(transport.sent), 1)
            finally:
                db.close()

            homework_view = self.get(
                f"/api/v1/parent/children/{self.ids['s1']}/homework",
                self.tokens["parent"],
            )
            self.assertEqual(homework_view.status_code, 200, homework_view.text)
            self.assertTrue(
                any(item["id"] == homework_id for item in homework_view.json()["homework"])
            )
            notification_view = self.get("/notifications", self.tokens["parent"])
            self.assertEqual(notification_view.status_code, 200, notification_view.text)
            self.assertTrue(
                any(
                    item["reference_id"] == homework_id
                    and item["notification_type"] == "HOMEWORK"
                    for item in notification_view.json()["data"]
                )
            )

    def test_disabled_homework_flag_preserves_in_app_only_behavior(self):
        env = {**HOMEWORK_ENV, "EMAIL_HOMEWORK_NOTIFICATIONS_ENABLED": "false"}
        with patch.dict(os.environ, env, clear=False):
            response = self._create_homework("AUTO EMAIL TEST disabled")
        self.assertEqual(response.status_code, 201, response.text)

        db = SessionLocal()
        try:
            homework_id = response.json()["id"]
            self.assertEqual(
                db.query(Notification)
                .filter_by(reference_id=homework_id, notification_type="HOMEWORK")
                .count(),
                1,
            )
            self.assertEqual(
                db.query(EmailNotificationBatch)
                .filter_by(target_type="AUTOMATIC_HOMEWORK")
                .count(),
                0,
            )
        finally:
            db.close()

    def test_test_mode_allowlist_filters_and_blank_list_fails_closed(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            allowed_env = {
                **HOMEWORK_ENV,
                "EMAIL_AUTOMATION_TEST_MODE": "true",
                "EMAIL_HOMEWORK_TEST_RECIPIENTS": parent.email,
            }
            with patch.dict(os.environ, allowed_env, clear=False):
                allowed = queue_parent_event_email(
                    db,
                    event_type="HOMEWORK",
                    reference_key=f"allow-{uuid.uuid4()}",
                    parent_ids=[parent.id],
                    created_by=self.ids["teacher"],
                    title="Allowed synthetic message",
                    message="Synthetic content",
                )
                self.assertEqual(allowed.queued_count, 1)

            blank_env = {
                **HOMEWORK_ENV,
                "EMAIL_AUTOMATION_TEST_MODE": "true",
                "EMAIL_HOMEWORK_TEST_RECIPIENTS": "",
            }
            with patch.dict(os.environ, blank_env, clear=False):
                blocked = queue_parent_event_email(
                    db,
                    event_type="HOMEWORK",
                    reference_key=f"blank-{uuid.uuid4()}",
                    parent_ids=[parent.id],
                    created_by=self.ids["teacher"],
                    title="Blocked synthetic message",
                    message="Synthetic content",
                )
                self.assertEqual(blocked.queued_count, 0)
            db.rollback()
        finally:
            db.close()

    def test_ineligible_and_inactive_parents_are_not_queued(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            original = (
                parent.email,
                parent.email_verified_at,
                parent.email_notifications_enabled,
                parent.is_active,
            )
            scenarios = [
                {"email": None},
                {"email": "not-an-email"},
                {"email_verified_at": None},
                {"email_notifications_enabled": False},
                {"is_active": False},
            ]
            with patch.dict(os.environ, HOMEWORK_ENV, clear=False):
                for index, changes in enumerate(scenarios):
                    (
                        parent.email,
                        parent.email_verified_at,
                        parent.email_notifications_enabled,
                        parent.is_active,
                    ) = original
                    for name, value in changes.items():
                        setattr(parent, name, value)
                    db.flush()
                    result = queue_parent_event_email(
                        db,
                        event_type="HOMEWORK",
                        reference_key=f"ineligible-{index}-{uuid.uuid4()}",
                        parent_ids=[parent.id],
                        created_by=self.ids["teacher"],
                        title="Ineligible synthetic message",
                        message="Synthetic content",
                    )
                    self.assertEqual(result.queued_count, 0)
                    db.rollback()
                    parent = db.get(User, self.ids["parent"])
            (
                parent.email,
                parent.email_verified_at,
                parent.email_notifications_enabled,
                parent.is_active,
            ) = original
            db.commit()
        finally:
            db.close()

    def test_queue_is_idempotent_and_never_contacts_smtp_in_request(self):
        env = {**HOMEWORK_ENV, "EMAIL_TRANSPORT": "smtp", "SMTP_HOST": ""}
        db = SessionLocal()
        try:
            reference = f"idempotent-{uuid.uuid4()}"
            kwargs = {
                "event_type": "HOMEWORK",
                "reference_key": reference,
                "parent_ids": [self.ids["parent"], self.ids["parent"]],
                "created_by": self.ids["teacher"],
                "title": "Idempotent synthetic message",
                "message": "Synthetic content",
            }
            with patch.dict(os.environ, env, clear=False):
                first = queue_parent_event_email(db, **kwargs)
                second = queue_parent_event_email(db, **kwargs)
            self.assertEqual(first.queued_count, 1)
            self.assertTrue(second.idempotent_replay)
            self.assertEqual(first.batch_id, second.batch_id)
            self.assertEqual(
                db.query(EmailDelivery).filter_by(batch_id=first.batch_id).count(),
                1,
            )
            db.rollback()
        finally:
            db.close()
