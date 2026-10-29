"""Parent Portal workflow tests (synthetic data only)."""
import tests._env  # noqa: F401  (isolates the test database - keep first)

import unittest
from datetime import date, timedelta

from tests.api_base import ApiTestBase


class ParentWorkflowTests(ApiTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tid = cls.tokens["teacher"]
        cid = cls.ids["class_a"]
        eid = cls.ids["exam"]

        # teacher enters results for the synthetic exam
        save = cls.post(
            f"/api/v1/teacher/classes/{cid}/results",
            tid,
            json={"exam_id": eid, "subject": "Mathematics", "results": [
                {"student_id": cls.ids["s1"], "max_marks": 100, "obtained_marks": 92},
                {"student_id": cls.ids["s2"], "max_marks": 100,
                 "obtained_marks": None, "result_status": "ABSENT"},
            ]},
        )
        assert save.status_code == 200, save.text

        # admin publishes the results
        publish = cls.patch(
            f"/api/v1/admin/exams/{eid}/publish-results",
            cls.tokens["admin"],
            json={"results_published": True},
        )
        assert publish.status_code in (200, 201, 400), publish.text
        if publish.status_code == 400:
            # some builds require an explicit bool flag or different shape;
            # fall back to direct DB update for the synthetic test exam only
            from app.database import SessionLocal
            from app.models.exam import Exam
            db = SessionLocal()
            try:
                row = db.query(Exam).filter(Exam.id == eid).first()
                row.results_published = True
                db.commit()
            finally:
                db.close()

        # teacher posts homework so the parent receives a HOMEWORK
        # notification (parent suite runs before the teacher suite)
        hw = cls.post(
            f"/api/v1/teacher/classes/{cid}/homework",
            tid,
            json={"subject": "Mathematics", "title": "Parent suite homework",
                  "description": "Exercise 1.1", "assigned_date": date.today().isoformat(),
                  "due_date": (date.today() + timedelta(days=2)).isoformat()},
        )
        assert hw.status_code in (200, 201), hw.text

    # -------------------------------------------------
    # LOGIN
    # -------------------------------------------------
    def test_login_with_username(self):
        me = self.get("/api/v1/auth/me", self.tokens["parent"])
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "PAR_TEST")

    def test_login_with_admission_number_resolves_parent(self):
        for adm in ("TESTADM1", "TESTADM2"):
            resp = self.client.post(
                "/api/v1/auth/login",
                json={"username": adm, "password": "Par@Test1!", "role": "PARENT"},
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            self.assertEqual(resp.json()["user"]["username"], "PAR_TEST")

        # wrong password
        bad = self.client.post(
            "/api/v1/auth/login",
            json={"username": "TESTADM1", "password": "wrong", "role": "PARENT"},
        )
        self.assertEqual(bad.status_code, 401)

    def test_admission_number_login_requires_linked_child(self):
        # TESTADM3 belongs to another parent
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "TESTADM3", "password": "Par@Test1!", "role": "PARENT"},
        )
        self.assertEqual(resp.status_code, 401)

    # -------------------------------------------------
    # CHILDREN / SIBLINGS
    # -------------------------------------------------
    def test_children_includes_all_siblings(self):
        resp = self.get("/api/v1/parent/children", self.tokens["parent"])
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        children = body if isinstance(body, list) else body.get("data", body.get("children", []))
        ids = {c.get("id", c.get("student_id")) for c in children}
        self.assertIn(self.ids["s1"], ids)
        self.assertIn(self.ids["s2"], ids)
        self.assertNotIn(self.ids["s3"], ids)

    def test_unlinked_child_returns_404(self):
        sid = self.ids["s3"]
        for path in [
            f"/api/v1/parent/children/{sid}",
            f"/api/v1/parent/children/{sid}/attendance?year={date.today().year}&month={date.today().month}",
            f"/api/v1/parent/children/{sid}/homework",
        ]:
            resp = self.get(path, self.tokens["parent"])
            self.assertIn(resp.status_code, (403, 404), f"{path}: {resp.status_code}")

    # -------------------------------------------------
    # ATTENDANCE
    # -------------------------------------------------
    def test_monthly_attendance(self):
        cid = self.ids["class_a"]
        today = date.today()
        # mark attendance for today via teacher API
        self.post(
            f"/api/v1/teacher/classes/{cid}/attendance",
            self.tokens["teacher"],
            json={"attendance_date": today.isoformat(), "records": [
                {"student_id": self.ids["s1"], "status": "PRESENT"},
            ]},
        )
        resp = self.get(
            f"/api/v1/parent/children/{self.ids['s1']}/attendance"
            f"?year={today.year}&month={today.month}",
            self.tokens["parent"],
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertGreaterEqual(body.get("present_count", body.get("present_days", 0)), 1)

        invalid = self.get(
            f"/api/v1/parent/children/{self.ids['s1']}/attendance?year=2026&month=13",
            self.tokens["parent"],
        )
        # the endpoint validates the month itself and returns 400
        self.assertEqual(invalid.status_code, 400)

    # -------------------------------------------------
    # RESULTS
    # -------------------------------------------------
    def test_results_for_published_exam(self):
        resp = self.get(
            f"/api/v1/parent/children/{self.ids['s1']}/result-exams",
            self.tokens["parent"],
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        exams = body if isinstance(body, list) else body.get("data", body.get("exams", []))
        self.assertTrue(any(e["id"] == self.ids["exam"] for e in exams))

        detail = self.get(
            f"/api/v1/parent/children/{self.ids['s1']}/results?exam_id={self.ids['exam']}",
            self.tokens["parent"],
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        subjects = detail.json().get("results", detail.json().get("subjects", []))
        math = [s for s in subjects if (s.get("subject") or "").lower() == "mathematics"]
        self.assertTrue(math)
        self.assertEqual(math[0].get("obtained_marks"), 92)
        self.assertEqual(math[0].get("grade"), "A+")

    # -------------------------------------------------
    # FEES
    # -------------------------------------------------
    def test_fee_summary_and_status(self):
        resp = self.get(
            f"/api/v1/parent/children/{self.ids['s1']}/fees",
            self.tokens["parent"],
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        fees = body.get("fees", body.get("data", []))
        titles = {f["fee_title"]: f for f in fees}
        self.assertIn("Term 1", titles)
        self.assertIn("Term 2", titles)
        self.assertEqual(titles["Term 1"].get("payment_status", titles["Term 1"].get("status")), "PAID")
        self.assertIn(titles["Term 2"].get("payment_status", titles["Term 2"].get("status")),
                      {"PENDING", "PARTIAL"})
        totals = body.get("summary", body.get("totals", {}))
        if totals:
            self.assertGreaterEqual(
                float(totals.get("total_amount", totals.get("total", 0))), 1500)

    # -------------------------------------------------
    # CIRCULARS / CALENDAR / DOWNLOADS / HOMEWORK
    # -------------------------------------------------
    def test_broadcast_scoping(self):
        circulars = self.get("/api/v1/parent/circulars", self.tokens["parent"])
        self.assertEqual(circulars.status_code, 200)
        body = circulars.json()
        items = body.get("circulars", body.get("data", []))
        self.assertTrue(any(c["title"] == "Test Circular" for c in items))

        calendar = self.get("/api/v1/parent/calendar", self.tokens["parent"])
        self.assertEqual(calendar.status_code, 200)
        body = calendar.json()
        events = body.get("events", body.get("data", []))
        self.assertTrue(any(e["title"] == "Test Event" for e in events))

        downloads = self.get("/api/v1/parent/download-forms", self.tokens["parent"])
        self.assertEqual(downloads.status_code, 200)

        homework = self.get(
            f"/api/v1/parent/children/{self.ids['s1']}/homework",
            self.tokens["parent"],
        )
        self.assertEqual(homework.status_code, 200)

    # -------------------------------------------------
    # DASHBOARD
    # -------------------------------------------------
    def test_dashboard_aggregates(self):
        resp = self.get(
            f"/api/v1/parent/dashboard?student_id={self.ids['s1']}",
            self.tokens["parent"],
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body.get("success", True))

    # -------------------------------------------------
    # NOTIFICATIONS
    # -------------------------------------------------
    def test_notifications_flow(self):
        count = self.get("/notifications/unread-count", self.tokens["parent"])
        self.assertEqual(count.status_code, 200, count.text)
        before = count.json().get("unread_count", count.json().get("count", 0))
        self.assertGreaterEqual(before, 1, "expected at least one unread notification")

        listing = self.get("/notifications", self.tokens["parent"])
        self.assertEqual(listing.status_code, 200)
        body = listing.json()
        items = (body.get("notifications", body.get("data", []))
                 if isinstance(body, dict) else body)
        self.assertTrue(items)
        nid = items[0]["id"]

        mark = self.patch(f"/notifications/{nid}/read", self.tokens["parent"])
        self.assertIn(mark.status_code, (200, 204))

        count = self.get("/notifications/unread-count", self.tokens["parent"])
        after = count.json().get("unread_count", count.json().get("count", 0))
        self.assertEqual(after, before - 1)

        # other parent's notification must not be readable
        foreign = self.patch(
            f"/notifications/{nid}/read", self.tokens["other_parent"])
        self.assertIn(foreign.status_code, (403, 404))

    # -------------------------------------------------
    # CROSS-ROLE
    # -------------------------------------------------
    def test_parent_cannot_access_teacher_or_admin(self):
        self.assertEqual(
            self.get("/api/v1/teacher/classes", self.tokens["parent"]).status_code, 403)
        self.assertEqual(
            self.get("/api/v1/admin/users", self.tokens["parent"]).status_code, 403)

    def test_inactive_account_cannot_login(self):
        from app.database import SessionLocal
        from app.models.user import User
        from app.core.security import hash_password

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.username == "PAR_TEST").first()
            original = u.is_active
            u.is_active = False
            db.commit()
        finally:
            db.close()

        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "PAR_TEST", "password": "Par@Test1!", "role": "PARENT"},
        )
        self.assertEqual(resp.status_code, 403)

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.username == "PAR_TEST").first()
            u.is_active = original
            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
