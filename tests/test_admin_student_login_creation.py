"""Admin student creation and generated parent-login regression tests."""

from datetime import datetime, timezone

import tests._env  # noqa: F401 - isolate DB before importing app modules

from app.database import SessionLocal
from app.models.parent_profile import ParentProfile
from app.models.parent_student import ParentStudent
from app.models.student import Student
from app.models.user import User
from tests.api_base import ApiTestBase


class TestAdminStudentLoginCreation(ApiTestBase):
    def tearDown(self):
        db = SessionLocal()
        try:
            student_ids = [
                row[0]
                for row in db.query(Student.id)
                .filter(Student.admission_no.like("TESTNEWADM%"))
                .all()
            ]
            parent_ids = [
                row[0]
                for row in db.query(User.id)
                .filter(User.username.like("PARENT_TESTNEWADM%"))
                .all()
            ]

            if student_ids:
                db.query(ParentStudent).filter(
                    ParentStudent.student_id.in_(student_ids)
                ).delete(synchronize_session=False)
                db.query(Student).filter(
                    Student.id.in_(student_ids)
                ).delete(synchronize_session=False)

            if parent_ids:
                db.query(ParentProfile).filter(
                    ParentProfile.user_id.in_(parent_ids)
                ).delete(synchronize_session=False)
                db.query(User).filter(
                    User.id.in_(parent_ids)
                ).delete(synchronize_session=False)

            db.commit()
        finally:
            db.close()

    def test_create_student_generates_working_parent_login(self):
        response = self.post(
            "/api/v1/admin/students",
            self.tokens["admin"],
            json={
                "admission_no": "TESTNEWADM1",
                "roll_no": "99",
                "full_name": "Generated Login Student",
                "date_of_birth": "2014-02-09",
                "parent_email": "generated.parent@example.com",
                "gender": "Female",
                "class_id": self.ids["class_a"],
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 201, response.text)

        data = response.json()["data"]
        self.assertEqual(data["login_username"], "TESTNEWADM1")
        self.assertEqual(data["initial_password"], "09022014")
        self.assertEqual(
            data["parent_email"],
            "generated.parent@example.com",
        )
        self.assertFalse(data["parent_account_reused"])

        detail = self.get(
            f"/api/v1/admin/students/{data['id']}",
            self.tokens["admin"],
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(
            detail.json()["data"]["parent_email"],
            "generated.parent@example.com",
        )

        db = SessionLocal()
        try:
            parent = (
                db.query(User)
                .filter(User.username == "PARENT_TESTNEWADM1")
                .one()
            )
            parent.email_verified_at = datetime.now(timezone.utc)
            parent.email_notifications_enabled = True
            db.commit()
        finally:
            db.close()

        update = self.put(
            f"/api/v1/admin/students/{data['id']}",
            self.tokens["admin"],
            json={
                "admission_no": "TESTNEWADM1",
                "roll_no": "99",
                "full_name": "Generated Login Student",
                "date_of_birth": "2014-02-09",
                "parent_email": "updated.parent@example.com",
                "gender": "Female",
                "class_id": self.ids["class_a"],
                "is_active": True,
            },
        )

        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(
            update.json()["data"]["parent_email"],
            "updated.parent@example.com",
        )

        db = SessionLocal()
        try:
            parent = (
                db.query(User)
                .filter(User.username == "PARENT_TESTNEWADM1")
                .one()
            )
            self.assertIsNone(parent.email_verified_at)
            self.assertFalse(parent.email_notifications_enabled)
        finally:
            db.close()

        login = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "TESTNEWADM1",
                "password": "09022014",
                "role": "PARENT",
            },
        )

        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["user"]["role"], "PARENT")

        sibling = self.post(
            "/api/v1/admin/students",
            self.tokens["admin"],
            json={
                "admission_no": "TESTNEWADM3",
                "full_name": "Generated Login Sibling",
                "date_of_birth": "2012-07-15",
                "parent_email": "updated.parent@example.com",
                "class_id": self.ids["class_a"],
                "is_active": True,
            },
        )

        self.assertEqual(sibling.status_code, 201, sibling.text)
        self.assertTrue(sibling.json()["data"]["parent_account_reused"])

        sibling_login = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "TESTNEWADM3",
                "password": "15072012",
                "role": "PARENT",
            },
        )

        self.assertEqual(sibling_login.status_code, 200, sibling_login.text)

    def test_create_student_requires_date_of_birth(self):
        response = self.post(
            "/api/v1/admin/students",
            self.tokens["admin"],
            json={
                "admission_no": "TESTNEWADM2",
                "full_name": "Missing DOB Student",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 422, response.text)
