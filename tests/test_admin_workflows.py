"""Admin Portal workflow tests (synthetic data only).

NOTE: this module runs FIRST in alphabetical discovery order
(test_admin_workflows < test_parent_workflows < test_teacher_workflows),
so it must never leave global state behind: exams/results/schedules it
touches on the shared fixture exam are cleaned up, and the fixture exam
is left unpublished for the later suites.
"""
import tests._env  # noqa: F401  (isolates the test database - keep first)

import unittest
from datetime import date, timedelta
from pathlib import Path

from tests.api_base import ApiTestBase

UPLOAD_DIR = Path("uploads/download_forms")


def _upload_path(file_url: str) -> Path:
    return UPLOAD_DIR / Path(file_url).name


class AdminWorkflowTests(ApiTestBase):
    # -------------------------------------------------
    # USERS
    # -------------------------------------------------
    def test_user_list_and_filters(self):
        resp = self.get("/api/v1/admin/users", self.tokens["admin"])
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("data", body)
        self.assertGreaterEqual(body["total"], 5)

        filtered = self.get("/api/v1/admin/users?role=TEACHER", self.tokens["admin"])
        self.assertEqual(filtered.status_code, 200)
        usernames = {u["username"] for u in filtered.json()["data"]}
        self.assertIn("TEACH_TEST", usernames)
        self.assertNotIn("PAR_TEST", usernames)

        search = self.get("/api/v1/admin/users?search=ADM_TEST", self.tokens["admin"])
        self.assertEqual(search.status_code, 200)
        usernames = {u["username"] for u in search.json()["data"]}
        self.assertEqual(usernames, {"ADM_TEST"})

    def test_user_create_and_duplicates(self):
        payload = {
            "name": "Test Admin User",
            "username": "ADMTESTUSR",
            "email": "admtestusr@rosarytest.dev",
            "password": "AdmTest#2233",
            "role": "PARENT",
        }
        create = self.post("/api/v1/admin/users", self.tokens["admin"], json=payload)
        self.assertEqual(create.status_code, 201, create.text)
        uid = create.json()["id"]
        self.addCleanup(self._delete_user_silent, uid)

        dup_username = dict(payload, email="other-admin@rosarytest.dev")
        self.assertEqual(
            self.post("/api/v1/admin/users", self.tokens["admin"], json=dup_username).status_code,
            409)

        dup_email = dict(payload, username="ADMTESTUSR2")
        self.assertEqual(
            self.post("/api/v1/admin/users", self.tokens["admin"], json=dup_email).status_code,
            409)

        bad_role = dict(payload, username="ADMTESTUSR3", email="admtestusr3@test.local",
                        role="STUDENT")
        self.assertEqual(
            self.post("/api/v1/admin/users", self.tokens["admin"], json=bad_role).status_code,
            422)

        short_pw = dict(payload, username="ADMTESTUSR4", email="admtestusr4@test.local",
                        password="short")
        self.assertEqual(
            self.post("/api/v1/admin/users", self.tokens["admin"], json=short_pw).status_code,
            422)

    def test_user_update_and_role_change_block(self):
        # linked users must never change role
        teacher_re_role = self.put(
            f"/api/v1/admin/users/{self.ids['teacher']}",
            self.tokens["admin"],
            json={"role": "PARENT"},
        )
        self.assertEqual(teacher_re_role.status_code, 409, teacher_re_role.text)

        parent_re_role = self.put(
            f"/api/v1/admin/users/{self.ids['parent']}",
            self.tokens["admin"],
            json={"role": "TEACHER"},
        )
        self.assertEqual(parent_re_role.status_code, 409, parent_re_role.text)

        # deleting linked users is blocked too
        self.assertEqual(
            self.delete(f"/api/v1/admin/users/{self.ids['parent']}", self.tokens["admin"]).status_code,
            409)

        # a plain (unlinked) user can be renamed and deleted
        payload = {
            "name": "Test Admin User",
            "username": "ADMTESTUSR",
            "email": "admtestusr@rosarytest.dev",
            "password": "AdmTest#2233",
            "role": "PARENT",
        }
        create = self.post("/api/v1/admin/users", self.tokens["admin"], json=payload)
        self.assertEqual(create.status_code, 201, create.text)
        uid = create.json()["id"]
        self.addCleanup(self._delete_user_silent, uid)

        rename = self.put(f"/api/v1/admin/users/{uid}", self.tokens["admin"],
                          json={"name": "Renamed Test User"})
        self.assertEqual(rename.status_code, 200, rename.text)
        self.assertEqual(rename.json()["name"], "Renamed Test User")

    def test_user_password_reset_and_status(self):
        payload = {
            "name": "Test Admin User",
            "username": "ADMTESTUSR",
            "email": "admtestusr@rosarytest.dev",
            "password": "AdmTest#2233",
            "role": "PARENT",
        }
        create = self.post("/api/v1/admin/users", self.tokens["admin"], json=payload)
        self.assertEqual(create.status_code, 201, create.text)
        uid = create.json()["id"]
        self.addCleanup(self._delete_user_silent, uid)

        reset = self.patch(f"/api/v1/admin/users/{uid}/password", self.tokens["admin"],
                           json={"new_password": "NewPass#2233"})
        self.assertEqual(reset.status_code, 200, reset.text)

        old_login = self.client.post("/api/v1/auth/login", json={
            "username": "ADMTESTUSR", "password": "AdmTest#2233", "role": "PARENT"})
        self.assertEqual(old_login.status_code, 401)

        new_login = self.client.post("/api/v1/auth/login", json={
            "username": "ADMTESTUSR", "password": "NewPass#2233", "role": "PARENT"})
        self.assertEqual(new_login.status_code, 200, new_login.text)

        # deactivate -> login forbidden
        status_off = self.patch(f"/api/v1/admin/users/{uid}/status", self.tokens["admin"],
                                json={"is_active": False})
        self.assertEqual(status_off.status_code, 200)
        self.assertFalse(status_off.json()["is_active"])

        blocked = self.client.post("/api/v1/auth/login", json={
            "username": "ADMTESTUSR", "password": "NewPass#2233", "role": "PARENT"})
        self.assertEqual(blocked.status_code, 403)

        # short password rejected
        bad_reset = self.patch(f"/api/v1/admin/users/{uid}/password", self.tokens["admin"],
                               json={"new_password": "short"})
        self.assertEqual(bad_reset.status_code, 422)

    def _delete_user_silent(self, user_id):
        self.delete(f"/api/v1/admin/users/{user_id}", self.tokens["admin"])

    # -------------------------------------------------
    # EXAMS
    # -------------------------------------------------
    def test_exam_crud(self):
        admin = self.tokens["admin"]
        payload = {
            "name": "ADMTESTEXAM",
            "academic_year": "2026-2027",
            "start_date": (date.today() - timedelta(days=2)).isoformat(),
            "end_date": date.today().isoformat(),
        }
        create = self.post("/api/v1/admin/exams", admin, json=payload)
        self.assertEqual(create.status_code, 201, create.text)
        eid = create.json()["id"]
        self.assertFalse(create.json()["results_published"])

        invalid = dict(payload, name="ADMTESTEXAM-BAD",
                       start_date=date.today().isoformat(),
                       end_date=(date.today() - timedelta(days=5)).isoformat())
        self.assertEqual(
            self.post("/api/v1/admin/exams", admin, json=invalid).status_code, 422)

        rename = self.put(f"/api/v1/admin/exams/{eid}", admin,
                          json={"name": "ADMTESTEXAM-RENAMED"})
        self.assertEqual(rename.status_code, 200, rename.text)
        self.assertEqual(rename.json()["name"], "ADMTESTEXAM-RENAMED")

        detail = self.get(f"/api/v1/admin/exams/{eid}", admin)
        self.assertEqual(detail.status_code, 200)

        delete = self.delete(f"/api/v1/admin/exams/{eid}", admin)
        self.assertIn(delete.status_code, (200, 204))

        gone = self.get(f"/api/v1/admin/exams/{eid}", admin)
        self.assertEqual(gone.status_code, 404)

    def test_exam_publish_guard_delete_guard_and_admin_results(self):
        admin = self.tokens["admin"]
        create = self.post("/api/v1/admin/exams", admin, json={
            "name": "ADMTESTEXAM2",
            "academic_year": "2026-2027",
            "start_date": (date.today() - timedelta(days=2)).isoformat(),
            "end_date": date.today().isoformat(),
        })
        self.assertEqual(create.status_code, 201, create.text)
        eid = create.json()["id"]

        # publish with zero results must be refused
        publish_empty = self.patch(f"/api/v1/admin/exams/{eid}/publish-results", admin,
                                   json={"results_published": True})
        self.assertEqual(publish_empty.status_code, 400, publish_empty.text)

        # a schedule link blocks deletion
        schedule = self.post("/api/v1/admin/exam-schedules", admin, json={
            "exam_id": eid,
            "class_id": self.ids["class_b"],
            "subject": "Science",
            "exam_date": date.today().isoformat(),
            "start_time": "10:00",
            "end_time": "11:00",
        })
        self.assertEqual(schedule.status_code, 201, schedule.text)
        sid = schedule.json()["id"]

        delete_with_schedule = self.delete(f"/api/v1/admin/exams/{eid}", admin)
        self.assertEqual(delete_with_schedule.status_code, 409)

        # admin creates a result
        result = self.post("/api/v1/admin/results", admin, json={
            "student_id": self.ids["s2"],
            "exam_id": eid,
            "subject": "Science",
            "max_marks": 100,
            "obtained_marks": 77,
        })
        self.assertEqual(result.status_code, 201, result.text)
        rid = result.json()["id"]

        # duplicate (student, exam, subject)
        dup = self.post("/api/v1/admin/results", admin, json={
            "student_id": self.ids["s2"], "exam_id": eid, "subject": "Science",
            "max_marks": 100, "obtained_marks": 80})
        self.assertEqual(dup.status_code, 409)

        # obtained > max
        over = self.post("/api/v1/admin/results", admin, json={
            "student_id": self.ids["s3"], "exam_id": eid, "subject": "Science",
            "max_marks": 100, "obtained_marks": 101})
        self.assertIn(over.status_code, (400, 422))

        # ABSENT with marks
        absent = self.post("/api/v1/admin/results", admin, json={
            "student_id": self.ids["s3"], "exam_id": eid, "subject": "Science",
            "max_marks": 100, "obtained_marks": 5, "result_status": "ABSENT"})
        self.assertIn(absent.status_code, (400, 422))

        # now publish succeeds because a result exists
        publish = self.patch(f"/api/v1/admin/exams/{eid}/publish-results", admin,
                             json={"results_published": True})
        self.assertEqual(publish.status_code, 200, publish.text)
        self.assertTrue(publish.json()["results_published"])

        unpublish = self.patch(f"/api/v1/admin/exams/{eid}/publish-results", admin,
                               json={"results_published": False})
        self.assertEqual(unpublish.status_code, 200, unpublish.text)
        self.assertFalse(unpublish.json()["results_published"])

        # update the admin result then delete it
        update = self.put(f"/api/v1/admin/results/{rid}", admin,
                          json={"obtained_marks": 85})
        self.assertEqual(update.status_code, 200, update.text)

        delete_result = self.delete(f"/api/v1/admin/results/{rid}", admin)
        self.assertIn(delete_result.status_code, (200, 204))

        # cleanup schedule, then the exam deletes cleanly
        self.assertIn(self.delete(f"/api/v1/admin/exam-schedules/{sid}", admin).status_code,
                      (200, 204))
        self.assertIn(self.delete(f"/api/v1/admin/exams/{eid}", admin).status_code,
                      (200, 204))

    # -------------------------------------------------
    # EXAM SCHEDULES (admin)
    # -------------------------------------------------
    def test_exam_schedules_admin_crud(self):
        admin = self.tokens["admin"]
        base = {
            "exam_id": self.ids["exam"],
            "class_id": self.ids["class_b"],
            "subject": "Science",
            "exam_date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "S-201",
        }
        create = self.post("/api/v1/admin/exam-schedules", admin, json=base)
        self.assertEqual(create.status_code, 201, create.text)
        sid = create.json()["id"]
        self.assertEqual(create.json()["class_name"], "TEST - B")

        # same exam/class/subject/date -> conflict
        self.assertEqual(
            self.post("/api/v1/admin/exam-schedules", admin, json=base).status_code, 409)

        # same exam/class/subject but a DIFFERENT date is allowed by admin rules
        other_day = dict(base, exam_date=(date.today() + timedelta(days=2)).isoformat())
        second = self.post("/api/v1/admin/exam-schedules", admin, json=other_day)
        self.assertEqual(second.status_code, 201, second.text)
        sid2 = second.json()["id"]

        # bad time range
        bad = dict(base, exam_date=(date.today() + timedelta(days=3)).isoformat(),
                   start_time="14:00", end_time="13:00")
        self.assertIn(
            self.post("/api/v1/admin/exam-schedules", admin, json=bad).status_code,
            (400, 422))

        # foreign class/exam
        self.assertEqual(
            self.post("/api/v1/admin/exam-schedules", admin,
                      json=dict(base, class_id=99999)).status_code, 404)
        self.assertEqual(
            self.post("/api/v1/admin/exam-schedules", admin,
                      json=dict(base, exam_id=99999)).status_code, 404)

        listing = self.get(
            f"/api/v1/admin/exam-schedules?exam_id={self.ids['exam']}", admin)
        self.assertEqual(listing.status_code, 200)
        self.assertGreaterEqual(listing.json()["total"], 2)

        update = self.put(f"/api/v1/admin/exam-schedules/{sid}", admin,
                          json={"room": "S-202"})
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()["room"], "S-202")

        for schedule_id in (sid, sid2):
            self.assertIn(
                self.delete(f"/api/v1/admin/exam-schedules/{schedule_id}", admin).status_code,
                (200, 204))

    # -------------------------------------------------
    # DOWNLOADS
    # -------------------------------------------------
    def test_download_upload_replace_delete(self):
        admin = self.tokens["admin"]

        create = self.post(
            "/api/v1/admin/downloads",
            admin,
            data={
                "title": "TEST ADMIN FORM",
                "category": "Forms",
                "description": "Synthetic download",
                "audience": "ALL",
                "published_date": date.today().isoformat(),
            },
            files={"file": ("TEST_ADMIN_FORM.pdf", b"%PDF-1.4 synthetic admin form content")},
        )
        self.assertEqual(create.status_code, 201, create.text)
        download = create.json()
        did = download["id"]
        first_url = download["file_url"]
        self.assertTrue(_upload_path(first_url).exists(),
                        "uploaded file missing on disk")

        # replace the file -> old file must be removed
        replace = self.put(
            f"/api/v1/admin/downloads/{did}",
            admin,
            data={"title": "TEST ADMIN FORM v2"},
            files={"file": ("TEST_ADMIN_FORM2.pdf", b"%PDF-1.4 replaced content")},
        )
        self.assertEqual(replace.status_code, 200, replace.text)
        second_url = replace.json()["file_url"]
        self.assertNotEqual(second_url, first_url)
        self.assertTrue(_upload_path(second_url).exists())
        self.assertFalse(_upload_path(first_url).exists(),
                         "old file was not cleaned up on replace")

        status = self.patch(f"/api/v1/admin/downloads/{did}/status", admin,
                            params={"is_active": False})
        self.assertEqual(status.status_code, 200, status.text)
        self.assertFalse(status.json()["is_active"])

        delete = self.delete(f"/api/v1/admin/downloads/{did}", admin)
        self.assertIn(delete.status_code, (200, 204))
        self.assertFalse(_upload_path(second_url).exists(),
                         "file was not cleaned up on delete")

        # missing file -> validation error
        no_file = self.post(
            "/api/v1/admin/downloads",
            admin,
            data={"title": "TEST NO FILE", "category": "Forms",
                  "audience": "ALL", "published_date": date.today().isoformat()},
        )
        self.assertEqual(no_file.status_code, 422)

    # -------------------------------------------------
    # ADMIN NOTIFICATIONS
    # -------------------------------------------------
    def test_admin_notification_preview_send(self):
        admin = self.tokens["admin"]

        preview_all = self.post("/api/v1/admin/notifications/preview", admin,
                                json={"target_type": "ALL_PARENTS"})
        self.assertEqual(preview_all.status_code, 200, preview_all.text)
        self.assertEqual(preview_all.json()["recipient_count"], 2)

        preview_class = self.post("/api/v1/admin/notifications/preview", admin,
                                  json={"target_type": "CLASSES",
                                        "class_ids": [self.ids["class_a"]]})
        self.assertEqual(preview_class.status_code, 200)
        self.assertEqual(preview_class.json()["recipient_count"], 1)

        invalid_class = self.post("/api/v1/admin/notifications/preview", admin,
                                  json={"target_type": "CLASSES", "class_ids": [99999]})
        self.assertEqual(invalid_class.status_code, 400)

        preview_individual = self.post("/api/v1/admin/notifications/preview", admin,
                                       json={"target_type": "INDIVIDUAL_PARENT",
                                             "parent_user_id": self.ids["other_parent"]})
        self.assertEqual(preview_individual.status_code, 200)
        self.assertEqual(preview_individual.json()["recipient_count"], 1)

        # send to class_b -> other_parent receives the announcement
        send = self.post("/api/v1/admin/notifications/send", admin,
                         json={"target_type": "CLASSES",
                               "class_ids": [self.ids["class_b"]],
                               "title": "Test announcement",
                               "message": "Synthetic admin announcement for class TEST-B"})
        self.assertEqual(send.status_code, 200, send.text)
        self.assertEqual(send.json()["recipient_count"], 1)

        unread = self.get("/notifications/unread-count", self.tokens["other_parent"])
        self.assertEqual(unread.status_code, 200)
        self.assertGreaterEqual(unread.json()["unread_count"], 1)

        # no eligible parents (target user is not a PARENT)
        empty = self.post("/api/v1/admin/notifications/send", admin,
                          json={"target_type": "INDIVIDUAL_PARENT",
                                "parent_user_id": self.ids["admin"],
                                "title": "Test announcement",
                                "message": "Synthetic message"})
        self.assertIn(empty.status_code, (400, 404))

        # invalid target shapes
        self.assertEqual(
            self.post("/api/v1/admin/notifications/preview", admin,
                      json={"target_type": "ALL_PARENTS",
                            "class_ids": [self.ids["class_a"]]}).status_code, 422)
        self.assertEqual(
            self.post("/api/v1/admin/notifications/preview", admin,
                      json={"target_type": "CLASSES"}).status_code, 422)

        # cross-role + unauthenticated
        self.assertEqual(
            self.get("/api/v1/admin/users", self.tokens["teacher"]).status_code, 403)
        self.assertEqual(
            self.post("/api/v1/admin/notifications/preview", self.tokens["parent"],
                      json={"target_type": "ALL_PARENTS"}).status_code, 403)
        self.assertEqual(self.get("/api/v1/admin/users").status_code, 401)
        self.assertEqual(
            self.post("/api/v1/admin/notifications/preview",
                      json={"target_type": "ALL_PARENTS"}).status_code, 401)

    # -------------------------------------------------
    # DASHBOARD
    # -------------------------------------------------
    def test_dashboard_stats(self):
        resp = self.get("/api/v1/admin/dashboard/stats", self.tokens["admin"])
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        stats = body.get("data", body)
        self.assertGreaterEqual(stats.get("total_students", 0), 3)
        self.assertGreaterEqual(stats.get("total_classes", 0), 2)


if __name__ == "__main__":
    unittest.main()

