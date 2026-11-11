"""Auth DOB-password regression tests (parents + teachers, synthetic data only)."""
from datetime import date

import tests._env  # noqa: F401  (isolates the test database - keep first)

from app.database import SessionLocal
from app.models.parent_profile import ParentProfile
from app.models.parent_student import ParentStudent
from app.models.student import Student
from app.models.user import User
from tests.api_base import ApiTestBase
from tests.fixtures import PARENT_PW, TEACHER_PW


class AuthDobPasswordTests(ApiTestBase):
    # -------------------------------------------------
    # TEACHER DOB LOGIN
    # -------------------------------------------------
    def test_teacher_login_accepts_date_of_birth(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "TEACH_TEST", "password": "15081990", "role": "TEACHER"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["user"]["username"], "TEACH_TEST")

    def test_teacher_login_accepts_dob_iso_format(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "TEACH_TEST", "password": "1990-08-15", "role": "TEACHER"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_teacher_login_accepts_employee_id_and_dob(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "testemp1",
                "password": "15081990",
                "role": "TEACHER",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["user"]["username"], "TEACH_TEST")

    def test_teacher_login_still_accepts_stored_password(self):
        # A changed / admin-set password keeps matching the stored hash.
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "TEACH_TEST", "password": TEACHER_PW, "role": "TEACHER"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_teacher_login_rejects_wrong_password(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "TEACH_TEST", "password": "wrong", "role": "TEACHER"},
        )
        self.assertEqual(resp.status_code, 401)

    # -------------------------------------------------
    # PARENT DOB + PASSWORD MATCH FALLBACK
    # -------------------------------------------------
    def test_parent_admission_login_accepts_student_date_of_birth(self):
        for password in ("09022014", "09-02-2014", "09/02/2014", "2014-02-09"):
            with self.subTest(password=password):
                resp = self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "testadm1",
                        "password": password,
                        "role": "PARENT",
                    },
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                self.assertEqual(resp.json()["user"]["username"], "PAR_TEST")

    def test_parent_admission_login_still_accepts_stored_password(self):
        # A changed / admin-set parent password keeps matching the stored hash.
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "TESTADM1", "password": PARENT_PW, "role": "PARENT"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["user"]["username"], "PAR_TEST")

    def test_parent_dob_login_repairs_missing_legacy_account_link(self):
        with SessionLocal() as db:
            student = Student(
                admission_no="LEGACYADM1",
                full_name="Legacy Student",
                date_of_birth=date(2013, 6, 7),
                is_active=True,
            )
            db.add(student)
            db.commit()
            student_id = student.id

        resp = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "LEGACYADM1",
                "password": "07062013",
                "role": "PARENT",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(
            resp.json()["user"]["username"],
            "PARENT_LEGACYADM1",
        )

        with SessionLocal() as db:
            link = (
                db.query(ParentStudent)
                .filter(ParentStudent.student_id == student_id)
                .one()
            )
            user = db.get(User, link.parent_user_id)
            profile = (
                db.query(ParentProfile)
                .filter(ParentProfile.user_id == user.id)
                .one()
            )
            self.assertEqual(user.role, "PARENT")
            self.assertIsNotNone(profile)

            db.delete(link)
            db.delete(profile)
            db.delete(user)
            db.delete(db.get(Student, student_id))
            db.commit()

    def test_wrong_dob_does_not_create_legacy_parent_account(self):
        with SessionLocal() as db:
            student = Student(
                admission_no="LEGACYADM2",
                full_name="Other Legacy Student",
                date_of_birth=date(2012, 1, 2),
                is_active=True,
            )
            db.add(student)
            db.commit()
            student_id = student.id

        resp = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "LEGACYADM2",
                "password": "wrong",
                "role": "PARENT",
            },
        )
        self.assertEqual(resp.status_code, 401)

        with SessionLocal() as db:
            link = (
                db.query(ParentStudent)
                .filter(ParentStudent.student_id == student_id)
                .first()
            )
            self.assertIsNone(link)
            db.delete(db.get(Student, student_id))
            db.commit()

    def test_parent_login_repairs_non_parent_legacy_link(self):
        with SessionLocal() as db:
            student = Student(
                admission_no="BADROLELINK1",
                full_name="Bad Role Link Student",
                date_of_birth=date(2011, 5, 4),
                is_active=True,
            )
            db.add(student)
            db.flush()
            db.add(
                ParentStudent(
                    parent_user_id=self.ids["teacher"],
                    student_id=student.id,
                    relationship="Legacy invalid link",
                )
            )
            db.commit()
            student_id = student.id

        resp = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "BADROLELINK1",
                "password": "04052011",
                "role": "PARENT",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["user"]["role"], "PARENT")

        with SessionLocal() as db:
            links = (
                db.query(ParentStudent)
                .filter(ParentStudent.student_id == student_id)
                .all()
            )
            parent_link = next(
                link
                for link in links
                if db.get(User, link.parent_user_id).role.upper()
                == "PARENT"
            )
            parent_user = db.get(User, parent_link.parent_user_id)
            parent_profile = (
                db.query(ParentProfile)
                .filter(ParentProfile.user_id == parent_user.id)
                .one()
            )
            for link in links:
                db.delete(link)
            db.delete(parent_profile)
            db.delete(parent_user)
            db.delete(db.get(Student, student_id))
            db.commit()
