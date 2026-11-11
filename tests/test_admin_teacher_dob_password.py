"""Teacher create/update DOB-password regression tests."""

import tests._env  # noqa: F401  (isolates the test database - keep first)

from app.core.security import verify_password
from app.database import SessionLocal
from app.models.teacher_profile import TeacherProfile
from app.models.user import User
from tests.api_base import ApiTestBase


class AdminTeacherDobPasswordTests(ApiTestBase):
    def test_create_and_dob_update_generate_password_hash(self):
        create = self.post(
            "/api/v1/admin/teachers",
            self.tokens["admin"],
            json={
                "name": "DOB Password Teacher",
                "username": "DOBTEACH1",
                "employee_id": "DOBEMP1",
                "date_of_birth": "1988-12-03",
            },
        )
        self.assertEqual(create.status_code, 201, create.text)
        teacher_id = create.json()["data"]["id"]
        user_id = create.json()["data"]["user_id"]

        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                self.assertTrue(
                    verify_password("03121988", user.password_hash)
                )

            login = self.client.post(
                "/api/v1/auth/login",
                json={
                    "username": "dobemp1",
                    "password": "03121988",
                    "role": "TEACHER",
                },
            )
            self.assertEqual(login.status_code, 200, login.text)

            update = self.put(
                f"/api/v1/admin/teachers/{teacher_id}",
                self.tokens["admin"],
                json={
                    "name": "DOB Password Teacher",
                    "username": "DOBTEACH1",
                    "employee_id": "DOBEMP1",
                    "date_of_birth": "1989-01-04",
                },
            )
            self.assertEqual(update.status_code, 200, update.text)

            with SessionLocal() as db:
                user = db.get(User, user_id)
                self.assertTrue(
                    verify_password("04011989", user.password_hash)
                )
                self.assertFalse(
                    verify_password("03121988", user.password_hash)
                )
        finally:
            with SessionLocal() as db:
                profile = db.get(TeacherProfile, teacher_id)
                user = db.get(User, user_id)
                if profile:
                    db.delete(profile)
                if user:
                    db.delete(user)
                db.commit()
