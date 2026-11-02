"""Staff notification inbox tests (synthetic data only).

Covers /api/v1/staff/notifications plus the notification event
triggers that fan out to staff (RESULT_SUBMISSION, RESULTS_PUBLISHED,
CIRCULAR, EXAM_SCHEDULE).

Every test captures its own "before" state and references seeded
records created inside the test with a unique STAFFTEST- marker, so
the suite passes in any module order and in any test order.
"""
import tests._env  # noqa: F401  (isolates the test database - keep first)

import unittest
import uuid
from datetime import date, timedelta

from tests.api_base import ApiTestBase


def _marker():
    return f"STAFFTEST-{uuid.uuid4().hex[:8]}"


class StaffNotificationsTests(ApiTestBase):

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    @classmethod
    def _seed_notification(cls, user_id, unread=True, ntype="GENERAL",
                           reference_id=None, title=None):
        """Insert one notification directly (deterministic setup)."""
        from app.database import SessionLocal
        from app.models.notification import Notification

        title = title or _marker()
        db = SessionLocal()
        try:
            n = Notification(user_id=user_id, title=title, message=title,
                             notification_type=ntype,
                             reference_id=reference_id, is_read=not unread)
            db.add(n)
            db.commit()
            return n.id
        finally:
            db.close()

    @classmethod
    def _count_notifications(cls, user_id, ntype=None, unread=None,
                            reference_id=None):
        from app.database import SessionLocal
        from app.models.notification import Notification

        db = SessionLocal()
        try:
            q = db.query(Notification).filter(
                Notification.user_id == user_id)
            if ntype is not None:
                q = q.filter(Notification.notification_type == ntype)
            if unread is not None:
                # unread=True filters rows NOT yet read.
                q = q.filter(Notification.is_read.is_(not unread))
            if reference_id is not None:
                q = q.filter(Notification.reference_id == reference_id)
            return q.count()
        finally:
            db.close()

    @classmethod
    def _create_exam(cls, suffix):
        """Create a dedicated exam via the admin API (total isolation)."""
        tag = uuid.uuid4().hex[:8]
        create = cls.post(
            "/api/v1/admin/exams",
            cls.tokens["admin"],
            json={"name": f"STAFFTESTEXAM{suffix}-{tag}",
                  "academic_year": "2026-2027",
                  "start_date": (date.today() - timedelta(days=2)).isoformat(),
                  "end_date": (date.today() + timedelta(days=30)).isoformat()},
        )
        assert create.status_code == 201, create.text
        return create.json()["id"]

    @classmethod
    def _list_titles(cls, token, query=""):
        resp = cls.get(f"/api/v1/staff/notifications"
                       f"?page_size=100{query}", token)
        assert resp.status_code == 200, resp.text
        return resp.json()

    # -------------------------------------------------
    # AUTHENTICATION / AUTHORIZATION
    # -------------------------------------------------
    def test_unauthenticated_access_rejected(self):
        self.assertEqual(
            self.get("/api/v1/staff/notifications").status_code, 401)
        self.assertEqual(
            self.get("/api/v1/staff/notifications/unread-count").status_code,
            401)
        self.assertEqual(
            self.patch("/api/v1/staff/notifications/1/read").status_code, 401)

    def test_parent_role_rejected(self):
        ptok = self.tokens["parent"]
        self.assertEqual(
            self.get("/api/v1/staff/notifications", ptok).status_code, 403)
        self.assertEqual(
            self.get("/api/v1/staff/notifications/unread-count",
                     ptok).status_code, 403)
        self.assertEqual(
            self.patch("/api/v1/staff/notifications/1/read",
                       ptok).status_code, 403)

    # -------------------------------------------------
    # SCOPING (each staff member sees only own inbox)
    # -------------------------------------------------
    def test_list_scoped_to_calling_user(self):
        my_title, admin_title = _marker(), _marker()
        self._seed_notification(self.ids["teacher"], title=my_title)
        self._seed_notification(self.ids["admin"], title=admin_title)

        teacher_body = self._list_titles(self.tokens["teacher"])
        teacher_titles = [n["title"] for n in teacher_body["data"]]
        self.assertIn(my_title, teacher_titles)
        self.assertNotIn(admin_title, teacher_titles)

        admin_body = self._list_titles(self.tokens["admin"])
        admin_titles = [n["title"] for n in admin_body["data"]]
        self.assertIn(admin_title, admin_titles)
        self.assertNotIn(my_title, admin_titles)

        # one teacher's inbox must never include another teacher's rows
        other_titles = [n["title"] for n in self._list_titles(
            self.tokens["other_teacher"])["data"]]
        self.assertNotIn(my_title, other_titles)
        self.assertNotIn(admin_title, other_titles)

    def test_list_total_scoped_to_calling_user(self):
        teacher_total_before = self._list_titles(
            self.tokens["teacher"])["total"]
        admin_total_before = self._list_titles(self.tokens["admin"])["total"]

        self._seed_notification(self.ids["teacher"])
        self._seed_notification(self.ids["admin"])

        self.assertEqual(
            self._list_titles(self.tokens["teacher"])["total"],
            teacher_total_before + 1,
            "teacher inbox total must include only the teacher's own row")
        self.assertEqual(
            self._list_titles(self.tokens["admin"])["total"],
            admin_total_before + 1,
            "admin inbox total must include only the admin's own row")

    def test_unread_count_scoped_to_calling_user(self):
        unread = self.get("/api/v1/staff/notifications/unread-count",
                          self.tokens["other_teacher"]).json()["unread_count"]
        uid_before_admin = self.get(
            "/api/v1/staff/notifications/unread-count",
            self.tokens["admin"]).json()["unread_count"]

        uid = self._seed_notification(self.ids["other_teacher"])
        self._seed_notification(self.ids["admin"])

        self.assertEqual(
            self.get("/api/v1/staff/notifications/unread-count",
                     self.tokens["other_teacher"]).json()["unread_count"],
            unread + 1)
        self.assertEqual(
            self.get("/api/v1/staff/notifications/unread-count",
                     self.tokens["admin"]).json()["unread_count"],
            uid_before_admin + 1)

        # the rows the caller can see must include the seeded one
        visible = {n["id"] for n in self._list_titles(
            self.tokens["other_teacher"])["data"]}
        self.assertIn(uid, visible)

    def test_unread_count_matches_database(self):
        self._seed_notification(self.ids["other_teacher"])
        self._seed_notification(self.ids["other_teacher"], unread=False)

        db_unread = self._count_notifications(
            self.ids["other_teacher"], unread=True)
        api_unread = self.get(
            "/api/v1/staff/notifications/unread-count",
            self.tokens["other_teacher"]).json()["unread_count"]
        self.assertEqual(api_unread, db_unread)

    # -------------------------------------------------
    # PAGINATION
    # -------------------------------------------------
    def test_pagination_metadata(self):
        for _ in range(3):
            self._seed_notification(self.ids["other_teacher"])

        resp = self.get(
            "/api/v1/staff/notifications?page=1&page_size=2",
            self.tokens["other_teacher"])
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 2)
        self.assertEqual(len(body["data"]), 2)
        self.assertGreaterEqual(body["total"], 1)
        expected_pages = (body["total"] + body["page_size"] - 1) \
            // body["page_size"]
        self.assertEqual(body["total_pages"], expected_pages)
        self.assertEqual(body["has_next"], 1 < body["total_pages"])
        self.assertEqual(body["has_previous"], False)

    # -------------------------------------------------
    # MARK AS READ
    # -------------------------------------------------
    def test_mark_read_success_decrements_unread(self):
        uid = self._seed_notification(self.ids["other_teacher"])
        before = self.get(
            "/api/v1/staff/notifications/unread-count",
            self.tokens["other_teacher"]).json()["unread_count"]

        marked = self.patch(
            f"/api/v1/staff/notifications/{uid}/read",
            self.tokens["other_teacher"])
        self.assertEqual(marked.status_code, 200, marked.text)
        self.assertTrue(marked.json()["is_read"])
        self.assertEqual(marked.json()["notification_id"], uid)

        after = self.get(
            "/api/v1/staff/notifications/unread-count",
            self.tokens["other_teacher"]).json()["unread_count"]
        self.assertEqual(after, before - 1,
                         "marking read must decrement the unread count")

    def test_mark_read_rejects_foreign_notification(self):
        admin_uid = self._seed_notification(self.ids["admin"])

        cross = self.patch(
            f"/api/v1/staff/notifications/{admin_uid}/read",
            self.tokens["teacher"])
        self.assertEqual(cross.status_code, 404)

        # the admin's row must remain untouched (still unread)
        self.assertTrue(self._count_notifications(
            self.ids["admin"], unread=True) >= 1)

    def test_mark_read_missing_notification_404(self):
        resp = self.patch(
            "/api/v1/staff/notifications/424242/read",
            self.tokens["teacher"])
        self.assertEqual(resp.status_code, 404)

    def test_mark_read_repeated_is_stable(self):
        uid = self._seed_notification(self.ids["other_teacher"])
        first = self.patch(
            f"/api/v1/staff/notifications/{uid}/read",
            self.tokens["other_teacher"])
        second = self.patch(
            f"/api/v1/staff/notifications/{uid}/read",
            self.tokens["other_teacher"])
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["is_read"])

    # -------------------------------------------------
    # EVENT TRIGGERS -> STAFF FAN-OUT
    # -------------------------------------------------
    def test_result_submission_notifies_admins(self):
        tid = self.tokens["teacher"]
        eid = self._create_exam("RS")

        admins_before = self._count_notifications(
            self.ids["admin"], ntype="RESULT_SUBMISSION")
        teacher_before = self._count_notifications(
            self.ids["teacher"], ntype="RESULT_SUBMISSION")

        save = self.post(
            f"/api/v1/teacher/classes/{self.ids['class_a']}/results",
            tid,
            json={"exam_id": eid, "subject": "Mathematics", "results": [
                {"student_id": self.ids["s1"], "max_marks": 100,
                 "obtained_marks": 91},
            ]},
        )
        self.assertEqual(save.status_code, 200, save.text)

        self.assertEqual(
            self._count_notifications(self.ids["admin"],
                                      ntype="RESULT_SUBMISSION"),
            admins_before + 1,
            "admins must receive a RESULT_SUBMISSION notification")
        self.assertEqual(
            self._count_notifications(self.ids["teacher"],
                                      ntype="RESULT_SUBMISSION"),
            teacher_before,
            "teachers must not receive their own submission notification")

    def test_publish_results_notifies_assigned_teachers(self):
        admin = self.tokens["admin"]
        eid = self._create_exam("PR")

        # the publish guard requires at least one result for the exam
        from app.database import SessionLocal
        from app.models.student_result import StudentResult
        db = SessionLocal()
        try:
            has_results = (db.query(StudentResult)
                           .filter(StudentResult.exam_id == eid).count())
            if not has_results:
                db.add(StudentResult(student_id=self.ids["s1"],
                                     class_id=self.ids["class_a"],
                                     exam_id=eid, subject="Mathematics",
                                     max_marks=100, obtained_marks=80,
                                     grade="A+", teacher_user_id=self.ids["teacher"]))
                db.commit()
        finally:
            db.close()

        # assigned teachers get notified only via scheduled classes;
        # ensure class TEST-A has a schedule entry for this exam.
        sched = self.post(
            "/api/v1/teacher/exam-schedule",
            self.tokens["teacher"],
            json={"class_id": self.ids["class_a"], "exam_id": eid,
                  "subject": "Mathematics",
                  "exam_date": (date.today() - timedelta(days=1)).isoformat(),
                  "start_time": "09:00", "end_time": "11:00",
                  "room": f"R-{uuid.uuid4().hex[:6]}"},
        )
        self.assertIn(sched.status_code, (201, 409), sched.text)

        # publishing must be a False -> True transition
        unpublish = self.patch(
            f"/api/v1/admin/exams/{eid}/publish-results", admin,
            json={"results_published": False})
        self.assertEqual(unpublish.status_code, 200, unpublish.text)

        before = self._count_notifications(
            self.ids["teacher"], ntype="RESULTS_PUBLISHED",
            reference_id=eid)
        other_before = self._count_notifications(
            self.ids["other_teacher"], ntype="RESULTS_PUBLISHED",
            reference_id=eid)

        publish = self.patch(
            f"/api/v1/admin/exams/{eid}/publish-results", admin,
            json={"results_published": True})
        self.assertEqual(publish.status_code, 200, publish.text)

        self.assertEqual(
            self._count_notifications(self.ids["teacher"],
                                      ntype="RESULTS_PUBLISHED",
                                      reference_id=eid),
            before + 1,
            "assigned teacher must receive a RESULTS_PUBLISHED notification")
        self.assertEqual(
            self._count_notifications(self.ids["other_teacher"],
                                      ntype="RESULTS_PUBLISHED",
                                      reference_id=eid),
            other_before,
            "teacher of an unscheduled class must not be notified")

    def test_new_circular_notifies_teachers(self):
        admin = self.tokens["admin"]
        title = _marker()

        teacher_before = self._count_notifications(
            self.ids["teacher"], ntype="CIRCULAR")
        other_before = self._count_notifications(
            self.ids["other_teacher"], ntype="CIRCULAR")
        admin_before = self._count_notifications(
            self.ids["admin"], ntype="CIRCULAR")

        create = self.post(
            "/api/v1/admin/circulars", admin,
            json={"title": title, "category": "General",
                  "description": "Synthetic circular for staff fan-out",
                  "published_date": date.today().isoformat(),
                  "audience": "ALL", "class_id": None,
                  "created_by": self.ids["admin"]},
        )
        self.assertEqual(create.status_code, 201, create.text)

        self.assertEqual(
            self._count_notifications(self.ids["teacher"],
                                      ntype="CIRCULAR"),
            teacher_before + 1,
            "active teachers must receive a CIRCULAR notification")
        self.assertEqual(
            self._count_notifications(self.ids["other_teacher"],
                                      ntype="CIRCULAR"),
            other_before + 1)
        self.assertEqual(
            self._count_notifications(self.ids["admin"],
                                      ntype="CIRCULAR"),
            admin_before,
            "admins must not fan out CIRCULAR notifications to themselves")

    def test_exam_schedule_creation_notifies_assigned_teacher(self):
        eid = self.ids["exam2"]

        before = self._count_notifications(
            self.ids["teacher"], ntype="EXAM_SCHEDULE")

        # admin path fans out to the teachers assigned to the class
        # (the teacher self-service path intentionally does not).
        create = self.post(
            "/api/v1/admin/exam-schedules", self.tokens["admin"],
            json={"class_id": self.ids["class_a"], "exam_id": eid,
                  "subject": "Mathematics",
                  "exam_date": date.today().isoformat(),
                  "start_time": "13:00", "end_time": "15:00",
                  "room": f"R-{uuid.uuid4().hex[:6]}"},
        )
        self.assertEqual(create.status_code, 201, create.text)

        self.assertEqual(
            self._count_notifications(self.ids["teacher"],
                                      ntype="EXAM_SCHEDULE"),
            before + 1,
            "assigned teachers of the scheduled class must be notified")


if __name__ == "__main__":
    unittest.main()  # noqa: F821
