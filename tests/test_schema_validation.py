import unittest
from datetime import date, timedelta

from pydantic import ValidationError

from app.schemas.attendance import (
    AttendanceRecordInput,
    AttendanceSaveRequest,
)
from app.schemas.result import ResultSaveRequest
from app.schemas.teacher_exam_schedule import (
    TeacherExamScheduleCreate,
    TeacherExamScheduleUpdate,
)


class AttendanceValidationTests(unittest.TestCase):
    def test_status_is_normalized(self):
        record = AttendanceRecordInput(
            student_id=1,
            status=" present ",
        )

        self.assertEqual(record.status, "PRESENT")

    def test_rejects_invalid_status(self):
        with self.assertRaises(ValidationError):
            AttendanceRecordInput(student_id=1, status="LATE")

    def test_rejects_duplicate_students(self):
        with self.assertRaises(ValidationError):
            AttendanceSaveRequest(
                attendance_date=date.today(),
                records=[
                    {"student_id": 1, "status": "PRESENT"},
                    {"student_id": 1, "status": "ABSENT"},
                ],
            )

    def test_rejects_future_attendance(self):
        with self.assertRaises(ValidationError):
            AttendanceSaveRequest(
                attendance_date=date.today() + timedelta(days=1),
                records=[{"student_id": 1, "status": "PRESENT"}],
            )


class ResultValidationTests(unittest.TestCase):
    def test_rejects_duplicate_students(self):
        with self.assertRaises(ValidationError):
            ResultSaveRequest(
                exam_id=1,
                subject="Mathematics",
                results=[
                    {
                        "student_id": 1,
                        "max_marks": 100,
                        "obtained_marks": 80,
                    },
                    {
                        "student_id": 1,
                        "max_marks": 100,
                        "obtained_marks": 75,
                    },
                ],
            )

    def test_rejects_empty_results(self):
        with self.assertRaises(ValidationError):
            ResultSaveRequest(
                exam_id=1,
                subject="Mathematics",
                results=[],
            )


class TeacherExamScheduleValidationTests(unittest.TestCase):
    def test_create_rejects_end_time_before_start_time(self):
        with self.assertRaises(ValidationError):
            TeacherExamScheduleCreate(
                class_id=1,
                exam_id=1,
                subject="Mathematics",
                exam_date=date.today(),
                start_time="10:00",
                end_time="09:00",
            )

    def test_create_strips_subject_and_optional_text(self):
        payload = TeacherExamScheduleCreate(
            class_id=1,
            exam_id=1,
            subject="  Mathematics  ",
            exam_date=date.today(),
            start_time="09:00",
            end_time="10:00",
            room="  101  ",
        )

        self.assertEqual(payload.subject, "Mathematics")
        self.assertEqual(payload.room, "101")

    def test_update_rejects_invalid_complete_time_range(self):
        with self.assertRaises(ValidationError):
            TeacherExamScheduleUpdate(
                start_time="10:00",
                end_time="10:00",
            )


if __name__ == "__main__":
    unittest.main()
