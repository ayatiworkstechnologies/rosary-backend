"""Authorization regression tests for Teacher Exam Schedule updates."""

import tests._env  # noqa: F401 - isolate DB before importing app modules

import uuid
from datetime import date, time, timedelta

from app.database import SessionLocal
from app.models.exam import Exam
from app.models.exam_schedule import ExamSchedule
from app.models.school_class import SchoolClass
from app.models.teacher_class import TeacherClass
from tests.api_base import ApiTestBase


class TeacherExamScheduleUpdateTests(ApiTestBase):
    def setUp(self):
        self.foreign_schedule_id = None
        suffix = uuid.uuid4().hex[:8]
        today = date.today()
        db = SessionLocal()
        try:
            proposed_exam = Exam(
                name=f"UPDATE-EXAM-{suffix}",
                academic_year="2026-2027",
                start_date=today + timedelta(days=5),
                end_date=today + timedelta(days=10),
                is_active=True,
            )
            inactive_exam = Exam(
                name=f"INACTIVE-EXAM-{suffix}",
                academic_year="2026-2027",
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=1),
                is_active=False,
            )
            inactive_class = SchoolClass(
                name="UPDATE-TEST",
                section=suffix,
                academic_year="2026-2027",
                is_active=False,
            )
            db.add_all([proposed_exam, inactive_exam, inactive_class])
            db.flush()
            db.add(
                TeacherClass(
                    teacher_user_id=self.ids["teacher"],
                    class_id=inactive_class.id,
                    subject="Mathematics",
                    is_class_teacher=False,
                )
            )
            schedule = ExamSchedule(
                class_id=self.ids["class_a"],
                exam_id=self.ids["exam"],
                subject="Mathematics",
                exam_date=today,
                start_time=time(9, 0),
                end_time=time(10, 0),
                room="ORIGINAL",
                instructions="Original instructions",
            )
            db.add(schedule)
            db.commit()
            self.schedule_id = schedule.id
            self.proposed_exam_id = proposed_exam.id
            self.inactive_exam_id = inactive_exam.id
            self.inactive_class_id = inactive_class.id
        finally:
            db.close()

    def tearDown(self):
        db = SessionLocal()
        try:
            schedule_ids = [self.schedule_id]
            if self.foreign_schedule_id is not None:
                schedule_ids.append(self.foreign_schedule_id)
            db.query(ExamSchedule).filter(
                ExamSchedule.id.in_(schedule_ids)
            ).delete(synchronize_session=False)
            db.query(TeacherClass).filter(
                TeacherClass.class_id == self.inactive_class_id
            ).delete(synchronize_session=False)
            db.query(SchoolClass).filter(
                SchoolClass.id == self.inactive_class_id
            ).delete(synchronize_session=False)
            db.query(Exam).filter(
                Exam.id.in_([self.proposed_exam_id, self.inactive_exam_id])
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def _snapshot(self, schedule_id=None):
        db = SessionLocal()
        try:
            schedule = db.get(ExamSchedule, schedule_id or self.schedule_id)
            return (
                schedule.class_id,
                schedule.exam_id,
                schedule.subject,
                schedule.exam_date,
                schedule.start_time,
                schedule.end_time,
                schedule.room,
                schedule.instructions,
            )
        finally:
            db.close()

    def _put(self, payload, schedule_id=None, token=None):
        return self.put(
            f"/api/v1/teacher/exam-schedule/{schedule_id or self.schedule_id}",
            token or self.tokens["teacher"],
            json=payload,
        )

    def _assert_failed_unchanged(self, payload, expected_status):
        before = self._snapshot()
        response = self._put(payload)
        self.assertEqual(response.status_code, expected_status, response.text)
        self.assertEqual(self._snapshot(), before)
        return response

    def test_authorized_schedule_update_succeeds_with_normalized_subject(self):
        response = self._put(
            {
                "subject": "  mAtHeMaTiCs  ",
                "start_time": "10:00",
                "end_time": "11:30",
                "room": "UPDATED",
            }
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["subject"], "mAtHeMaTiCs")
        self.assertEqual(response.json()["room"], "UPDATED")
        self.assertEqual(response.json()["message"], "Exam schedule updated successfully")

    def test_update_to_unauthorized_class_returns_403_without_changes(self):
        self._assert_failed_unchanged(
            {"class_id": self.ids["class_b"]},
            403,
        )

    def test_update_to_unauthorized_subject_returns_403_without_changes(self):
        self._assert_failed_unchanged({"subject": "Science"}, 403)

    def test_changing_exam_id_uses_new_examination_date_range(self):
        self._assert_failed_unchanged({"exam_id": self.proposed_exam_id}, 400)

        valid_date = date.today() + timedelta(days=6)
        response = self._put(
            {
                "exam_id": self.proposed_exam_id,
                "exam_date": valid_date.isoformat(),
            }
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["exam_id"], self.proposed_exam_id)
        self.assertEqual(response.json()["exam_date"], valid_date.isoformat())

    def test_invalid_exam_date_returns_400_without_changes(self):
        db = SessionLocal()
        try:
            exam = db.get(Exam, self.ids["exam"])
            invalid_date = exam.end_date + timedelta(days=1)
        finally:
            db.close()
        self._assert_failed_unchanged(
            {"exam_date": invalid_date.isoformat()},
            400,
        )

    def test_invalid_effective_time_range_returns_400_without_changes(self):
        self._assert_failed_unchanged({"start_time": "10:30"}, 400)

    def test_explicit_null_required_fields_are_rejected_without_changes(self):
        for field in (
            "class_id",
            "exam_id",
            "subject",
            "exam_date",
            "start_time",
            "end_time",
        ):
            with self.subTest(field=field):
                self._assert_failed_unchanged({field: None}, 422)

    def test_inactive_proposed_class_and_exam_are_rejected(self):
        self._assert_failed_unchanged(
            {"class_id": self.inactive_class_id},
            404,
        )
        self._assert_failed_unchanged(
            {"exam_id": self.inactive_exam_id},
            404,
        )

    def test_teacher_cannot_update_another_teachers_subject_schedule(self):
        db = SessionLocal()
        try:
            foreign_schedule = ExamSchedule(
                class_id=self.ids["class_b"],
                exam_id=self.ids["exam"],
                subject="Science",
                exam_date=date.today(),
                start_time=time(12, 0),
                end_time=time(13, 0),
                room="FOREIGN",
            )
            db.add(foreign_schedule)
            db.commit()
            self.foreign_schedule_id = foreign_schedule.id
        finally:
            db.close()

        before = self._snapshot(self.foreign_schedule_id)
        response = self._put(
            {"room": "HACKED"},
            schedule_id=self.foreign_schedule_id,
        )
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self._snapshot(self.foreign_schedule_id), before)

