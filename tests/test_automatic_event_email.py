"""Automatic supported-event integrations against synthetic SQLite only."""

import os
from datetime import date, time, timedelta
from unittest.mock import patch

import tests._env  # noqa: F401

from app.database import SessionLocal
from app.models.attendance import Attendance
from app.models.circular import Circular
from app.models.email_notification import EmailDelivery, EmailNotificationBatch
from app.models.exam import Exam
from app.models.exam_schedule import ExamSchedule
from app.models.notification import Notification
from app.models.school_event import SchoolEvent
from app.models.student_result import StudentResult
from tests.api_base import ApiTestBase


BASE_ENV = {
    "EMAIL_NOTIFICATIONS_ENABLED": "true",
    "EMAIL_AUTOMATION_TEST_MODE": "false",
    "EMAIL_TRANSPORT": "mock",
}


class AutomaticSupportedEventEmailTests(ApiTestBase):
    def _batch(self, category: str, title_prefix: str):
        db = SessionLocal()
        try:
            return (
                db.query(EmailNotificationBatch)
                .filter(
                    EmailNotificationBatch.category == category,
                    EmailNotificationBatch.title.like(f"{title_prefix}%"),
                )
                .order_by(EmailNotificationBatch.id.desc())
                .first()
            )
        finally:
            db.close()

    def test_absence_and_correction_queue_affected_parent(self):
        attendance_date = date.today() - timedelta(days=400)
        db = SessionLocal()
        try:
            db.query(Attendance).filter_by(
                student_id=self.ids["s1"], attendance_date=attendance_date
            ).delete()
            db.commit()
        finally:
            db.close()

        env = {**BASE_ENV, "EMAIL_ATTENDANCE_NOTIFICATIONS_ENABLED": "true"}
        endpoint = f"/api/v1/teacher/classes/{self.ids['class_a']}/attendance"
        with patch.dict(os.environ, env, clear=False):
            absent = self.post(
                endpoint,
                self.tokens["teacher"],
                json={
                    "attendance_date": attendance_date.isoformat(),
                    "records": [{"student_id": self.ids["s1"], "status": "ABSENT"}],
                },
            )
            self.assertEqual(absent.status_code, 200, absent.text)
            corrected = self.post(
                endpoint,
                self.tokens["teacher"],
                json={
                    "attendance_date": attendance_date.isoformat(),
                    "records": [{"student_id": self.ids["s1"], "status": "PRESENT"}],
                },
            )
            self.assertEqual(corrected.status_code, 200, corrected.text)

        db = SessionLocal()
        try:
            attendance = db.query(Attendance).filter_by(
                student_id=self.ids["s1"], attendance_date=attendance_date
            ).one()
            batches = db.query(EmailNotificationBatch).filter_by(
                category="ATTENDANCE"
            ).all()
            matching = [b for b in batches if b.created_by == self.ids["teacher"]]
            self.assertEqual(len(matching), 2)
            self.assertTrue(all(b.email_recipient_count == 1 for b in matching))
            self.assertEqual(
                db.query(Notification).filter_by(
                    reference_id=attendance.id, notification_type="ATTENDANCE"
                ).count(),
                2,
            )
            batch_ids = [b.id for b in matching]
            db.query(EmailDelivery).filter(EmailDelivery.batch_id.in_(batch_ids)).delete(
                synchronize_session=False
            )
            db.query(EmailNotificationBatch).filter(
                EmailNotificationBatch.id.in_(batch_ids)
            ).delete(synchronize_session=False)
            db.query(Notification).filter_by(
                reference_id=attendance.id, notification_type="ATTENDANCE"
            ).delete(synchronize_session=False)
            db.delete(attendance)
            db.commit()
        finally:
            db.close()

    def test_results_publication_queues_relevant_class_parents(self):
        db = SessionLocal()
        try:
            exam = db.get(Exam, self.ids["exam2"])
            exam.results_published = False
            schedule = ExamSchedule(
                exam_id=exam.id,
                class_id=self.ids["class_a"],
                subject="AUTO EMAIL RESULT",
                exam_date=date.today(),
                start_time=time(9, 0),
                end_time=time(10, 0),
            )
            result = StudentResult(
                student_id=self.ids["s1"],
                class_id=self.ids["class_a"],
                exam_id=exam.id,
                teacher_user_id=self.ids["teacher"],
                subject="AUTO EMAIL RESULT",
                max_marks=100,
                obtained_marks=80,
                result_status="PRESENT",
            )
            db.add_all([schedule, result])
            db.commit()
            schedule_id, result_id = schedule.id, result.id
        finally:
            db.close()

        env = {**BASE_ENV, "EMAIL_RESULTS_NOTIFICATIONS_ENABLED": "true"}
        with patch.dict(os.environ, env, clear=False):
            response = self.patch(
                f"/api/v1/admin/exams/{self.ids['exam2']}/publish-results",
                self.tokens["admin"],
                json={"results_published": True},
            )
        self.assertEqual(response.status_code, 200, response.text)

        db = SessionLocal()
        try:
            batch = (
                db.query(EmailNotificationBatch)
                .filter_by(category="RESULTS", target_type="AUTOMATIC_RESULTS")
                .order_by(EmailNotificationBatch.id.desc())
                .first()
            )
            self.assertIsNotNone(batch)
            self.assertEqual(batch.email_recipient_count, 1)
            self.assertEqual(
                db.query(Notification).filter_by(
                    user_id=self.ids["parent"],
                    notification_type="RESULTS_PUBLISHED",
                    reference_id=self.ids["exam2"],
                ).count(),
                1,
            )
            db.query(EmailDelivery).filter_by(batch_id=batch.id).delete()
            db.delete(batch)
            db.query(Notification).filter_by(
                notification_type="RESULTS_PUBLISHED",
                reference_id=self.ids["exam2"],
            ).delete(synchronize_session=False)
            db.get(Exam, self.ids["exam2"]).results_published = False
            db.query(StudentResult).filter_by(id=result_id).delete()
            db.query(ExamSchedule).filter_by(id=schedule_id).delete()
            db.commit()
        finally:
            db.close()

    def test_active_circular_and_event_queue_class_parent(self):
        suffix = date.today().isoformat()
        circular_title = f"AUTO EMAIL CIRCULAR {suffix}"
        event_title = f"AUTO EMAIL EVENT {suffix}"
        env = {
            **BASE_ENV,
            "EMAIL_CIRCULAR_NOTIFICATIONS_ENABLED": "true",
            "EMAIL_EVENT_NOTIFICATIONS_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            circular = self.post(
                "/api/v1/admin/circulars",
                self.tokens["admin"],
                json={
                    "title": circular_title,
                    "category": "General",
                    "description": "Synthetic circular",
                    "published_date": date.today().isoformat(),
                    "audience": "CLASS",
                    "class_id": self.ids["class_a"],
                    "created_by": self.ids["admin"],
                    "is_active": True,
                },
            )
            self.assertEqual(circular.status_code, 201, circular.text)
            event = self.post(
                "/api/v1/admin/calendar",
                self.tokens["admin"],
                json={
                    "title": event_title,
                    "event_type": "EVENT",
                    "description": "Synthetic event",
                    "start_date": date.today().isoformat(),
                    "audience": "CLASS",
                    "class_id": self.ids["class_a"],
                    "created_by": self.ids["admin"],
                    "is_active": True,
                },
            )
            self.assertEqual(event.status_code, 201, event.text)

        db = SessionLocal()
        try:
            batches = (
                db.query(EmailNotificationBatch)
                .filter(EmailNotificationBatch.category.in_(["CIRCULAR", "EVENT"]))
                .all()
            )
            selected = [
                batch
                for batch in batches
                if circular_title in batch.title or event_title in batch.title
            ]
            self.assertEqual(len(selected), 2)
            self.assertTrue(all(batch.email_recipient_count == 1 for batch in selected))
            batch_ids = [batch.id for batch in selected]
            db.query(EmailDelivery).filter(EmailDelivery.batch_id.in_(batch_ids)).delete(
                synchronize_session=False
            )
            db.query(EmailNotificationBatch).filter(
                EmailNotificationBatch.id.in_(batch_ids)
            ).delete(synchronize_session=False)
            circular_row = db.query(Circular).filter_by(title=circular_title).one()
            event_row = db.query(SchoolEvent).filter_by(title=event_title).one()
            db.query(Notification).filter(
                Notification.reference_id.in_([circular_row.id, event_row.id]),
                Notification.notification_type.in_(["CIRCULAR", "SCHOOL_EVENT"]),
            ).delete(synchronize_session=False)
            db.delete(circular_row)
            db.delete(event_row)
            db.commit()
        finally:
            db.close()

