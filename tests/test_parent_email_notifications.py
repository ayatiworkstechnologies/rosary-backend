"""Parent email notification tests use only the synthetic SQLite database."""

import tests._env  # noqa: F401 - isolate DB before importing app modules

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.database import SessionLocal
from app.models.email_notification import EmailDelivery, EmailNotificationBatch
from app.models.notification import Notification
from app.models.user import User
from app.services.parent_email_service import MockEmailTransport, process_email_queue
from tests.api_base import ApiTestBase


class ParentEmailNotificationTests(ApiTestBase):
    def tearDown(self):
        db = SessionLocal()
        try:
            batch_ids = [
                row[0]
                for row in db.query(EmailNotificationBatch.id)
                .filter(EmailNotificationBatch.idempotency_key.like("email-test-%"))
                .all()
            ]
            if batch_ids:
                db.query(EmailDelivery).filter(
                    EmailDelivery.batch_id.in_(batch_ids)
                ).delete(synchronize_session=False)
                db.query(EmailNotificationBatch).filter(
                    EmailNotificationBatch.id.in_(batch_ids)
                ).delete(synchronize_session=False)
            db.query(Notification).filter(
                Notification.title.like("EMAIL TEST%")
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def _set_parent(self, user_id, **values):
        db = SessionLocal()
        try:
            db.query(User).filter(User.id == user_id).update(values)
            db.commit()
        finally:
            db.close()

    def test_preview_students_siblings_and_email_deduplication(self):
        admin = self.tokens["admin"]
        students = self.post(
            "/api/v1/admin/notifications/preview",
            admin,
            json={
                "target_type": "STUDENTS",
                "student_ids": [self.ids["s1"], self.ids["s2"]],
            },
        )
        self.assertEqual(students.status_code, 200, students.text)
        self.assertEqual(students.json()["recipient_count"], 1)
        self.assertEqual(students.json()["email_recipient_count"], 1)

        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            other = db.get(User, self.ids["other_parent"])
            original = other.email
            other.email = parent.email.upper()
            db.commit()
        finally:
            db.close()

        try:
            all_parents = self.post(
                "/api/v1/admin/notifications/preview",
                admin,
                json={"target_type": "ALL_PARENTS"},
            )
            self.assertEqual(all_parents.status_code, 200)
            self.assertEqual(all_parents.json()["recipient_count"], 2)
            self.assertEqual(all_parents.json()["email_recipient_count"], 1)
            self.assertEqual(all_parents.json()["deduplicated_email_count"], 1)
        finally:
            self._set_parent(self.ids["other_parent"], email=original)

    def test_preview_reports_missing_invalid_unverified_and_opted_out(self):
        db = SessionLocal()
        try:
            parent = db.get(User, self.ids["parent"])
            other = db.get(User, self.ids["other_parent"])
            original_parent = (
                parent.email,
                parent.email_verified_at,
                parent.email_notifications_enabled,
            )
            original_other = (
                other.email,
                other.email_verified_at,
                other.email_notifications_enabled,
            )
            parent.email = "invalid-address"
            other.email = None
            db.commit()
        finally:
            db.close()

        try:
            response = self.post(
                "/api/v1/admin/notifications/preview",
                self.tokens["admin"],
                json={"target_type": "ALL_PARENTS"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["missing_email_count"], 1)
            self.assertEqual(response.json()["invalid_email_count"], 1)
            self.assertEqual(response.json()["email_recipient_count"], 0)
        finally:
            self._set_parent(
                self.ids["parent"],
                email=original_parent[0],
                email_verified_at=original_parent[1],
                email_notifications_enabled=original_parent[2],
            )
            self._set_parent(
                self.ids["other_parent"],
                email=original_other[0],
                email_verified_at=original_other[1],
                email_notifications_enabled=original_other[2],
            )

        self._set_parent(self.ids["parent"], email_verified_at=None)
        self._set_parent(
            self.ids["other_parent"], email_notifications_enabled=False
        )
        try:
            response = self.post(
                "/api/v1/admin/notifications/preview",
                self.tokens["admin"],
                json={"target_type": "ALL_PARENTS"},
            )
            self.assertEqual(response.json()["unverified_email_count"], 1)
            self.assertEqual(response.json()["opted_out_count"], 1)
        finally:
            self._set_parent(
                self.ids["parent"], email_verified_at=datetime.now(timezone.utc)
            )
            self._set_parent(
                self.ids["other_parent"], email_notifications_enabled=True
            )

    def test_send_is_idempotent_and_mock_worker_tracks_success(self):
        payload = {
            "target_type": "STUDENTS",
            "student_ids": [self.ids["s1"], self.ids["s2"]],
            "title": "EMAIL TEST success",
            "message": "Synthetic parent email notification",
            "category": "IMPORTANT",
            "send_in_app": True,
            "send_email": True,
            "idempotency_key": "email-test-success",
            "confirmed_email_recipient_count": 1,
        }
        first = self.post(
            "/api/v1/admin/notifications/send",
            self.tokens["admin"],
            json=payload,
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["email_queued"], 1)

        replay = self.post(
            "/api/v1/admin/notifications/send",
            self.tokens["admin"],
            json=payload,
        )
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["idempotent_replay"])
        self.assertEqual(replay.json()["batch_id"], first.json()["batch_id"])

        conflicting_payload = {**payload, "message": "A different request"}
        conflict = self.post(
            "/api/v1/admin/notifications/send",
            self.tokens["admin"],
            json=conflicting_payload,
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)

        db = SessionLocal()
        try:
            notifications = (
                db.query(Notification)
                .filter(Notification.title == payload["title"])
                .all()
            )
            self.assertEqual(len(notifications), 1)
            transport = MockEmailTransport()
            result = process_email_queue(db, transport=transport)
            self.assertEqual(result["sent"], 1)
            batch = db.get(EmailNotificationBatch, first.json()["batch_id"])
            self.assertEqual(batch.status, "COMPLETED")
            self.assertEqual(len(transport.sent), 1)
        finally:
            db.close()

        history = self.get(
            "/api/v1/admin/notifications/email-batches",
            self.tokens["admin"],
        )
        self.assertEqual(history.status_code, 200, history.text)
        history_ids = [item["id"] for item in history.json()["data"]]
        self.assertIn(first.json()["batch_id"], history_ids)

        detail = self.get(
            f"/api/v1/admin/notifications/email-batches/{first.json()['batch_id']}",
            self.tokens["admin"],
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        masked_email = detail.json()["deliveries"][0]["email"]
        self.assertIn("***", masked_email)
        self.assertNotEqual(masked_email, transport.sent[0])

    def test_provider_failure_retries_then_marks_failed(self):
        db = SessionLocal()
        try:
            recipient = db.get(User, self.ids["other_parent"]).email.lower()
        finally:
            db.close()

        payload = {
            "target_type": "INDIVIDUAL_PARENT",
            "parent_user_id": self.ids["other_parent"],
            "title": "EMAIL TEST failure",
            "message": "Synthetic provider failure",
            "send_in_app": False,
            "send_email": True,
            "idempotency_key": "email-test-failure",
            "confirmed_email_recipient_count": 1,
        }
        response = self.post(
            "/api/v1/admin/notifications/send",
            self.tokens["admin"],
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.text)

        db = SessionLocal()
        try:
            transport = MockEmailTransport(fail_recipients={recipient})
            current = datetime.now(timezone.utc).replace(tzinfo=None)
            for attempt in range(3):
                delivery = db.query(EmailDelivery).filter_by(
                    batch_id=response.json()["batch_id"]
                ).one()
                delivery.next_attempt_at = current
                db.commit()
                process_email_queue(
                    db,
                    transport=transport,
                    now=current + timedelta(seconds=attempt),
                )
            delivery = db.query(EmailDelivery).filter_by(
                batch_id=response.json()["batch_id"]
            ).one()
            self.assertEqual(delivery.status, "FAILED")
            self.assertEqual(delivery.attempt_count, 3)
            self.assertNotIn("password", delivery.last_error.lower())
            batch = db.get(EmailNotificationBatch, response.json()["batch_id"])
            self.assertEqual(batch.status, "COMPLETED_WITH_FAILURES")
        finally:
            db.close()

    def test_email_send_requires_enabled_provider_and_admin_role(self):
        payload = {
            "target_type": "INDIVIDUAL_PARENT",
            "parent_user_id": self.ids["parent"],
            "title": "EMAIL TEST disabled",
            "message": "Synthetic disabled provider",
            "send_in_app": False,
            "send_email": True,
            "idempotency_key": "email-test-disabled",
            "confirmed_email_recipient_count": 1,
        }
        with patch.dict(os.environ, {"EMAIL_NOTIFICATIONS_ENABLED": "false"}):
            response = self.post(
                "/api/v1/admin/notifications/send",
                self.tokens["admin"],
                json=payload,
            )
            self.assertEqual(response.status_code, 503)

        forbidden = self.post(
            "/api/v1/admin/notifications/send",
            self.tokens["parent"],
            json=payload,
        )
        self.assertEqual(forbidden.status_code, 403)

        forbidden_history = self.get(
            "/api/v1/admin/notifications/email-batches",
            self.tokens["parent"],
        )
        self.assertEqual(forbidden_history.status_code, 403)

    def test_fee_reminder_requires_separate_feature_permission(self):
        payload = {
            "target_type": "INDIVIDUAL_PARENT",
            "parent_user_id": self.ids["parent"],
            "category": "FEE_REMINDER",
            "title": "EMAIL TEST fee reminder",
            "message": "Synthetic fee reminder",
            "send_in_app": True,
            "send_email": False,
            "idempotency_key": "email-test-fee-reminder",
        }
        with patch.dict(
            os.environ,
            {"EMAIL_FEE_REMINDERS_ENABLED": "false"},
            clear=False,
        ):
            denied = self.post(
                "/api/v1/admin/notifications/send",
                self.tokens["admin"],
                json=payload,
            )
        self.assertEqual(denied.status_code, 403, denied.text)

        with patch.dict(
            os.environ,
            {"EMAIL_FEE_REMINDERS_ENABLED": "true"},
            clear=False,
        ):
            accepted = self.post(
                "/api/v1/admin/notifications/send",
                self.tokens["admin"],
                json=payload,
            )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["email_queued"], 0)
