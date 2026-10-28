import unittest
from datetime import date, timedelta

from pydantic import ValidationError

from app.schemas.attendance import (
    AttendanceRecordInput,
    AttendanceSaveRequest,
)
from app.schemas.result import ResultSaveRequest


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


if __name__ == "__main__":
    unittest.main()
