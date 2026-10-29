"""Cross-cutting role-permission matrix and authentication regression tests.

These tests verify the strict three-role access model of the portal:
TEACHER, PARENT and ADMIN must each only reach their own endpoint
families, unauthenticated requests must get 401 everywhere, and login
semantics (role mismatch, admission-number resolution, inactive
accounts, malformed tokens) must behave as documented.
"""
import tests._env  # noqa: F401  (isolates the test database - keep first)

import unittest
from datetime import date, timedelta

from tests.api_base import ApiTestBase

ADMIN = [
    "/api/v1/admin/users",
    "/api/v1/admin/exams",
    "/api/v1/admin/results",
    "/api/v1/admin/exam-schedules",
    "/api/v1/admin/downloads",
    "/api/v1/admin/dashboard/stats",
]

TEACHER = [
    "/api/v1/teacher/classes",
    "/api/v1/teacher/exams",
    "/api/v1/teacher/exam-schedule",
    f"/api/v1/teacher/classes/CLASS_ID/students",
    f"/api/v1/teacher/classes/CLASS_ID/attendance?attendance_date={date.today().isoformat()}",
    f"/api/v1/teacher/classes/CLASS_ID/homework",
    f"/api/v1/teacher/classes/CLASS_ID/results?exam_id=EXAM_ID&subject=Mathematics",
]

PARENT = [
    "/api/v1/parent/children",
    "/api/v1/parent/children/CHILD_ID/attendance?year=2026&month=10",
    "/api/v1/parent/children/CHILD_ID/homework",
    "/api/v1/parent/children/CHILD_ID/fees",
    "/api/v1/parent/children/CHILD_ID/result-exams",
    "/api/v1/parent/circulars",
    "/api/v1/parent/calendar",
    "/api/v1/parent/download-forms",
    "/notifications",
    "/notifications/unread-count",
]


def substitute(path, ids):
    return (path
            .replace("CLASS_ID", str(ids["class_a"]))
            .replace("CHILD_ID", str(ids["s1"]))
            .replace("EXAM_ID", str(ids["exam"])))


class RolePermissionMatrixTests(ApiTestBase):
    # -------------------------------------------------
    # FULL MATRIX: GET requests, three roles + anonymous
    # -------------------------------------------------
    def test_admin_endpoints(self):
        for raw in ADMIN:
            path = substitute(raw, self.ids)
            self.assertEqual(
                self.get(path, self.tokens["admin"]).status_code, 200,
                f"ADMIN should access {path}")
            self.assertEqual(
                self.get(path, self.tokens["teacher"]).status_code, 403,
                f"TEACHER must not access {path}")
            self.assertEqual(
                self.get(path, self.tokens["parent"]).status_code, 403,
                f"PARENT must not access {path}")
            self.assertEqual(
                self.get(path).status_code, 401,
                f"anonymous must get 401 on {path}")

        # POST-only endpoint, guarded at router level
        preview = "/api/v1/admin/notifications/preview"
        self.assertEqual(
            self.post(preview, self.tokens["admin"],
                      json={"target_type": "ALL_PARENTS"}).status_code, 200)
        self.assertEqual(
            self.post(preview, self.tokens["teacher"],
                      json={"target_type": "ALL_PARENTS"}).status_code, 403)
        self.assertEqual(
            self.post(preview, self.tokens["parent"],
                      json={"target_type": "ALL_PARENTS"}).status_code, 403)
        self.assertEqual(
            self.post(preview, json={"target_type": "ALL_PARENTS"}).status_code, 401)

    def test_teacher_endpoints(self):
        # GET only; 200/404/422 acceptable for the owner, everything
        # else must be strictly 403 for wrong roles
        for raw in TEACHER:
            path = substitute(raw, self.ids)
            self.assertEqual(
                self.get(path, self.tokens["teacher"]).status_code, 200,
                f"TEACHER should access {path}")
            self.assertEqual(
                self.get(path, self.tokens["parent"]).status_code, 403,
                f"PARENT must not access {path}")
            self.assertEqual(
                self.get(path, self.tokens["admin"]).status_code, 403,
                f"ADMIN must not access {path}")
            self.assertEqual(
                self.get(path).status_code, 401,
                f"anonymous must get 401 on {path}")

    def test_parent_endpoints(self):
        for raw in PARENT:
            path = substitute(raw, self.ids)
            self.assertEqual(
                self.get(path, self.tokens["parent"]).status_code, 200,
                f"PARENT should access {path}")
            self.assertEqual(
                self.get(path, self.tokens["teacher"]).status_code, 403,
                f"TEACHER must not access {path}")
            self.assertEqual(
                self.get(path, self.tokens["admin"]).status_code, 403,
                f"ADMIN must not access {path}")
            self.assertEqual(
                self.get(path).status_code, 401,
                f"anonymous must get 401 on {path}")

    # -------------------------------------------------
    # AUTH REGRESSION
    # -------------------------------------------------
    def test_login_role_mismatch_rejected(self):
        # a teacher must not log in through the PARENT door
        resp = self.client.post("/api/v1/auth/login", json={
            "username": "TEACH_TEST", "password": "Teach@Test1!", "role": "PARENT"})
        self.assertEqual(resp.status_code, 403)

        # ... nor through the ADMIN door
        resp = self.client.post("/api/v1/auth/login", json={
            "username": "TEACH_TEST", "password": "Teach@Test1!", "role": "ADMIN"})
        self.assertEqual(resp.status_code, 403)

    def test_login_is_role_case_insensitive(self):
        resp = self.client.post("/api/v1/auth/login", json={
            "username": "TEACH_TEST", "password": "Teach@Test1!", "role": "teacher"})
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_login_unknown_user_and_bad_credentials(self):
        resp = self.client.post("/api/v1/auth/login", json={
            "username": "NO_SUCH_USER", "password": "x", "role": "PARENT"})
        self.assertEqual(resp.status_code, 401)

        resp = self.client.post("/api/v1/auth/login", json={
            "username": "PAR_TEST", "password": "definitely-wrong", "role": "PARENT"})
        self.assertEqual(resp.status_code, 401)

        resp = self.client.post("/api/v1/auth/login", json={
            "username": "   ", "password": "x", "role": "PARENT"})
        self.assertEqual(resp.status_code, 401)

        resp = self.client.post("/api/v1/auth/login", json={
            "username": "NOSUCHADM999", "password": "x", "role": "PARENT"})
        self.assertEqual(resp.status_code, 401)

    def test_malformed_tokens_rejected(self):
        for token in ("not-a-jwt", "a.b.c", ""):
            resp = self.get("/api/v1/parent/children", token or "x")
            self.assertEqual(resp.status_code, 401, f"token={token!r}")

    def test_inactive_user_token_rejected(self):
        from app.database import SessionLocal
        from app.models.user import User
        from app.core.security import hash_password

        # dedicated user so we never touch the shared fixtures' accounts
        db = SessionLocal()
        try:
            u = User(name="Inactive Test", username="USR_INACT",
                     email="usr_inact@test.local",
                     password_hash=hash_password("Inact@Test1!"),
                     role="PARENT", is_active=False)
            db.add(u)
            db.commit()
            uid = u.id
        finally:
            db.close()

        # login blocked for inactive account
        resp = self.client.post("/api/v1/auth/login", json={
            "username": "USR_INACT", "password": "Inact@Test1!", "role": "PARENT"})
        self.assertEqual(resp.status_code, 403)

        # re-activate, log in, deactivate again -> token must stop working
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.id == uid).first()
            u.is_active = True
            db.commit()
        finally:
            db.close()

        resp = self.client.post("/api/v1/auth/login", json={
            "username": "USR_INACT", "password": "Inact@Test1!", "role": "PARENT"})
        self.assertEqual(resp.status_code, 200)
        token = resp.json()["access_token"]

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.id == uid).first()
            u.is_active = False
            db.commit()
        finally:
            db.close()

        self.assertEqual(
            self.get("/api/v1/parent/children", token).status_code, 403)

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.id == uid).first()
            db.delete(u)
            db.commit()
        finally:
            db.close()


class FamilyScopingRegressionTests(ApiTestBase):
    """Privacy between families: one parent must never see another
    parent's child data, and one teacher must not manage another
    teacher's class."""

    def test_other_parent_cannot_reach_child(self):
        token = self.tokens["other_parent"]
        sid = self.ids["s1"]
        for path in [
            f"/api/v1/parent/children/{sid}",
            f"/api/v1/parent/children/{sid}/attendance?year={date.today().year}&month={date.today().month}",
            f"/api/v1/parent/children/{sid}/homework",
            f"/api/v1/parent/children/{sid}/fees",
            f"/api/v1/parent/children/{sid}/result-exams",
            f"/api/v1/parent/children/{sid}/results?exam_id={self.ids['exam']}",
            f"/api/v1/parent/dashboard?student_id={sid}",
        ]:
            resp = self.get(path, token)
            self.assertIn(resp.status_code, (403, 404), f"{path}: {resp.status_code}")

    def test_other_teacher_cannot_manage_class(self):
        token = self.tokens["other_teacher"]
        cid = self.ids["class_a"]
        today = date.today().isoformat()

        self.assertIn(
            self.get(f"/api/v1/teacher/classes/{cid}/students", token).status_code,
            (403, 404))

        self.assertIn(
            self.post(
                f"/api/v1/teacher/classes/{cid}/attendance", token,
                json={"attendance_date": today, "records": [
                    {"student_id": self.ids["s1"], "status": "PRESENT"}]},
            ).status_code,
            (400, 403, 404))

        self.assertIn(
            self.post(
                f"/api/v1/teacher/classes/{cid}/results", token,
                json={"exam_id": self.ids["exam"], "subject": "Mathematics",
                      "results": [{"student_id": self.ids["s1"],
                                   "max_marks": 100, "obtained_marks": 50}]},
            ).status_code,
            (400, 403, 404))

        # other teacher cannot edit/delete a schedule they did not create
        create = self.post("/api/v1/teacher/exam-schedule", self.tokens["teacher"], json={
            "class_id": self.ids["class_a"],
            "exam_id": self.ids["exam"],
            "subject": "Mathematics",
            "exam_date": (date.today() - timedelta(days=2)).isoformat(),
            "start_time": "10:00",
            "end_time": "11:00",
        })
        self.assertEqual(create.status_code, 201, create.text)
        sid = create.json()["id"]

        foreign_update = self.put(
            f"/api/v1/teacher/exam-schedule/{sid}", token, json={"room": "HACKED"})
        self.assertIn(foreign_update.status_code, (400, 403, 404))

        foreign_delete = self.delete(f"/api/v1/teacher/exam-schedule/{sid}", token)
        self.assertIn(foreign_delete.status_code, (400, 403, 404))

        cleanup = self.delete(f"/api/v1/teacher/exam-schedule/{sid}", self.tokens["teacher"])
        self.assertIn(cleanup.status_code, (200, 204))

    def test_homework_notification_scope(self):
        """Homework posted to class A must notify class-A parents only."""
        from app.database import SessionLocal
        from app.models.notification import Notification

        before_other = 0
        db = SessionLocal()
        try:
            before_other = (db.query(Notification)
                            .filter(Notification.user_id == self.ids["other_parent"],
                                    Notification.notification_type == "HOMEWORK")
                            .count())
        finally:
            db.close()

        create = self.post(
            f"/api/v1/teacher/classes/{self.ids['class_a']}/homework",
            self.tokens["teacher"],
            json={"subject": "Mathematics", "title": "Scope check homework",
                  "assigned_date": date.today().isoformat(),
                  "due_date": (date.today() + timedelta(days=1)).isoformat()},
        )
        self.assertIn(create.status_code, (200, 201), create.text)

        db = SessionLocal()
        try:
            after_other = (db.query(Notification)
                           .filter(Notification.user_id == self.ids["other_parent"],
                                   Notification.notification_type == "HOMEWORK")
                           .count())
            linked = (db.query(Notification)
                      .filter(Notification.user_id == self.ids["parent"],
                              Notification.notification_type == "HOMEWORK",
                              Notification.reference_id == create.json()["id"])
                      .count())
        finally:
            db.close()

        self.assertEqual(after_other, before_other,
                         "unlinked parent received a homework notification")
        self.assertGreaterEqual(linked, 1,
                                "linked parent did not receive the homework notification")


if __name__ == "__main__":
    unittest.main()
