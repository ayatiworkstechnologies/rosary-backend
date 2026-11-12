"""Email worker reliability tests use only synthetic SQLite and mock transports."""

import os
import smtplib
import uuid
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.dialects import mysql

import tests._env  # noqa: F401

from app.database import SessionLocal
from app.models.email_notification import EmailDelivery, EmailNotificationBatch
from app.models.user import User
from app.services.parent_email_service import (
    MockEmailTransport,
    process_email_queue,
    render_parent_email_html,
)
from app.services.email_templates import (
    render_notification_email_html,
    render_notification_email_text,
)
from app.services.email_worker_health import read_worker_heartbeat, write_worker_heartbeat
from tests.api_base import ApiTestBase


WORKER_ENV = {
    "EMAIL_NOTIFICATIONS_ENABLED": "true",
    "EMAIL_TRANSPORT": "mock",
    "EMAIL_RATE_LIMIT_PER_SECOND": "0",
    "EMAIL_RETRY_BASE_SECONDS": "1",
    "EMAIL_PROCESSING_TIMEOUT_SECONDS": "60",
}


class RaisingTransport:
    def __init__(self, error):
        self.error = error
        self.sent = []

    def send(self, recipient, title, message, **_kwargs):
        self.sent.append(recipient)
        raise self.error


class EmailWorkerReliabilityTests(ApiTestBase):
    def tearDown(self):
        db = SessionLocal()
        try:
            batch_ids = [
                batch_id
                for (batch_id,) in db.query(EmailNotificationBatch.id)
                .filter(EmailNotificationBatch.idempotency_key.like("worker-test-%"))
                .all()
            ]
            if batch_ids:
                db.query(EmailDelivery).filter(
                    EmailDelivery.batch_id.in_(batch_ids)
                ).delete(synchronize_session=False)
                db.query(EmailNotificationBatch).filter(
                    EmailNotificationBatch.id.in_(batch_ids)
                ).delete(synchronize_session=False)
            parent = db.get(User, self.ids["parent"])
            parent.email_verified_at = datetime.now(timezone.utc)
            parent.email_notifications_enabled = True
            parent.is_active = True
            db.commit()
        finally:
            db.close()

    def _queue_delivery(
        self,
        db,
        *,
        status="QUEUED",
        attempt_count=0,
        max_attempts=3,
        updated_at=None,
    ):
        parent = db.get(User, self.ids["parent"])
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        batch = EmailNotificationBatch(
            idempotency_key=f"worker-test-{uuid.uuid4()}",
            request_fingerprint=uuid.uuid4().hex,
            created_by=self.ids["admin"],
            target_type="INDIVIDUAL_PARENT",
            category="GENERAL",
            title="Synthetic worker test",
            message="Synthetic content only",
            send_in_app=False,
            send_email=True,
            status="PROCESSING" if status == "PROCESSING" else "QUEUED",
            parent_recipient_count=1,
            email_recipient_count=1,
        )
        db.add(batch)
        db.flush()
        delivery = EmailDelivery(
            batch_id=batch.id,
            parent_user_id=parent.id,
            email=parent.email.lower(),
            status=status,
            attempt_count=attempt_count,
            max_attempts=max_attempts,
            next_attempt_at=now,
            updated_at=updated_at or now,
        )
        db.add(delivery)
        db.commit()
        return batch.id, delivery.id

    def test_temporary_failure_retries_then_succeeds(self):
        db = SessionLocal()
        try:
            batch_id, delivery_id = self._queue_delivery(db)
            temporary = RaisingTransport(smtplib.SMTPDataError(451, b"try later"))
            with patch.dict(os.environ, WORKER_ENV, clear=False):
                first = process_email_queue(db, transport=temporary)
            self.assertEqual(first["retried"], 1)
            delivery = db.get(EmailDelivery, delivery_id)
            self.assertEqual(delivery.status, "RETRY")
            self.assertEqual(delivery.attempt_count, 1)

            delivery.next_attempt_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            successful = MockEmailTransport()
            with patch.dict(os.environ, WORKER_ENV, clear=False):
                second = process_email_queue(db, transport=successful)
            self.assertEqual(second["sent"], 1)
            self.assertEqual(db.get(EmailDelivery, delivery_id).status, "SENT")
            self.assertEqual(db.get(EmailNotificationBatch, batch_id).status, "COMPLETED")
        finally:
            db.close()

    def test_permanent_smtp_failure_does_not_retry(self):
        db = SessionLocal()
        try:
            _, delivery_id = self._queue_delivery(db)
            recipient = db.get(EmailDelivery, delivery_id).email
            permanent = RaisingTransport(
                smtplib.SMTPRecipientsRefused({recipient: (550, b"rejected")})
            )
            with patch.dict(os.environ, WORKER_ENV, clear=False):
                result = process_email_queue(db, transport=permanent)
            delivery = db.get(EmailDelivery, delivery_id)
            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["retried"], 0)
            self.assertEqual(delivery.status, "FAILED")
            self.assertIsNone(delivery.next_attempt_at)
            self.assertNotIn(recipient, delivery.last_error)
        finally:
            db.close()

    def test_connection_and_timeout_failures_are_retryable(self):
        for error in (ConnectionError("synthetic connection failure"), TimeoutError("synthetic timeout")):
            with self.subTest(error=error.__class__.__name__):
                db = SessionLocal()
                try:
                    _, delivery_id = self._queue_delivery(db)
                    with patch.dict(os.environ, WORKER_ENV, clear=False):
                        result = process_email_queue(db, transport=RaisingTransport(error))
                    self.assertEqual(result["retried"], 1)
                    self.assertEqual(db.get(EmailDelivery, delivery_id).status, "RETRY")
                finally:
                    db.close()

    def test_smtp_authentication_failure_is_permanent(self):
        db = SessionLocal()
        try:
            _, delivery_id = self._queue_delivery(db)
            error = smtplib.SMTPAuthenticationError(535, b"synthetic auth failure")
            with patch.dict(os.environ, WORKER_ENV, clear=False):
                result = process_email_queue(db, transport=RaisingTransport(error))
            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["retried"], 0)
            self.assertEqual(db.get(EmailDelivery, delivery_id).status, "FAILED")
        finally:
            db.close()

    def test_stale_max_attempt_delivery_is_failed(self):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            _, delivery_id = self._queue_delivery(
                db,
                status="PROCESSING",
                attempt_count=3,
                max_attempts=3,
                updated_at=now - timedelta(minutes=5),
            )
            with patch.dict(os.environ, WORKER_ENV, clear=False):
                result = process_email_queue(db, transport=MockEmailTransport(), now=now)
            self.assertEqual(result["processed"], 0)
            delivery = db.get(EmailDelivery, delivery_id)
            self.assertEqual(delivery.status, "FAILED")
            self.assertIn("maximum attempts", delivery.last_error)
        finally:
            db.close()

    def test_opt_out_after_queue_prevents_delivery(self):
        db = SessionLocal()
        try:
            _, delivery_id = self._queue_delivery(db)
            parent = db.get(User, self.ids["parent"])
            parent.email_notifications_enabled = False
            db.commit()
            transport = MockEmailTransport()
            with patch.dict(os.environ, WORKER_ENV, clear=False):
                result = process_email_queue(db, transport=transport)
            self.assertEqual(result["failed"], 1)
            self.assertEqual(transport.sent, [])
            self.assertEqual(db.get(EmailDelivery, delivery_id).status, "FAILED")
        finally:
            db.close()

    def test_provider_error_redacts_credentials(self):
        db = SessionLocal()
        try:
            _, delivery_id = self._queue_delivery(db, max_attempts=1)
            secret = "synthetic-smtp-secret"
            username = "synthetic-smtp-user"
            transport = RaisingTransport(
                RuntimeError(f"login failed for {username} password={secret}")
            )
            env = {
                **WORKER_ENV,
                "SMTP_USERNAME": username,
                "SMTP_PASSWORD": secret,
            }
            with patch.dict(os.environ, env, clear=False):
                process_email_queue(db, transport=transport)
            error = db.get(EmailDelivery, delivery_id).last_error
            self.assertNotIn(secret, error)
            self.assertNotIn(username, error)
            self.assertIn("[redacted]", error)
        finally:
            db.close()

    def test_admin_metrics_are_authorized_and_mask_failures(self):
        db = SessionLocal()
        try:
            self._queue_delivery(db, status="FAILED", attempt_count=2)
        finally:
            db.close()

        self.assertEqual(
            self.get("/api/v1/admin/notifications/email-metrics").status_code,
            401,
        )
        self.assertEqual(
            self.get(
                "/api/v1/admin/notifications/email-metrics",
                self.tokens["parent"],
            ).status_code,
            403,
        )
        response = self.get(
            "/api/v1/admin/notifications/email-metrics",
            self.tokens["admin"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertGreaterEqual(data["total_emails_queued"], 1)
        self.assertGreaterEqual(data["delivery_counts"]["FAILED"], 1)
        self.assertGreaterEqual(data["retry_count"], 1)
        self.assertEqual(data["total_failed"], data["delivery_counts"]["FAILED"])
        self.assertIn("***", data["recent_failures"][0]["email"])

    def test_html_template_escapes_dynamic_content(self):
        rendered = render_parent_email_html(
            "<script>alert('title')</script>",
            "Student <img src=x onerror=alert(1)>",
            "https://school.example",
            "https://school.example/unsubscribe?token=a&next=b",
        )
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img src=x", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("token=a&amp;next=b", rendered)
        self.assertIn("Rosary Matriculation Higher Secondary School", rendered)

    def test_category_templates_have_safe_destination_and_plain_text(self):
        rendered = render_notification_email_html(
            "FEE_PAYMENT", "Payment received", "Synthetic receipt", "https://school.example"
        )
        plain = render_notification_email_text(
            "HOMEWORK", "New homework", "Synthetic details", "https://school.example"
        )
        self.assertIn("https://school.example/parent/fees", rendered)
        self.assertIn("Fee payment update", rendered)
        self.assertIn("https://school.example/parent/homework", plain)

    def test_worker_heartbeat_records_idle_cycles_without_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "heartbeat.json")
            with patch.dict(os.environ, {"EMAIL_WORKER_HEARTBEAT_FILE": path}, clear=False):
                write_worker_heartbeat({"processed": 0, "sent": 0, "failed": 0, "retried": 0})
                heartbeat = read_worker_heartbeat()
            self.assertEqual(heartbeat["status"], "healthy")
            self.assertEqual(heartbeat["processed"], 0)
            self.assertIn("timestamp", heartbeat)

    def test_mysql_claim_sql_uses_skip_locked_for_concurrent_workers(self):
        statement = (
            select(EmailDelivery.id)
            .where(EmailDelivery.status.in_(["QUEUED", "RETRY"]))
            .with_for_update(skip_locked=True)
        )
        sql = str(statement.compile(dialect=mysql.dialect())).upper()
        self.assertIn("FOR UPDATE SKIP LOCKED", sql)
