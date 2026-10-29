"""Teacher Portal workflow tests (synthetic data only)."""
import tests._env  # noqa: F401  (isolates the test database - keep first)

from datetime import date, timedelta

from tests.api_base import ApiTestBase


class TeacherWorkflowTests(ApiTestBase):
    def test_login_and_me(self):
        me = self.get("/api/v1/auth/me", self.tokens["teacher"])
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "TEACH_TEST")

    def test_assigned_classes(self):
        resp = self.get("/api/v1/teacher/classes", self.tokens["teacher"])
        self.assertEqual(resp.status_code, 200)
        classes = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
        mine = [c for c in classes if c.get("id") == self.ids["class_a"]]
        self.assertTrue(mine, "assigned class TEST-A not visible to teacher")
        self.assertEqual(
            (mine[0].get("subject") or "").lower(), "mathematics"
        )

    def test_class_roster_and_search(self):
        cid = self.ids["class_a"]
        resp = self.get(f"/api/v1/teacher/classes/{cid}/students", self.tokens["teacher"])
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        students = data if isinstance(data, list) else data.get("data", data.get("students", []))
        ids = {s.get("student_id", s.get("id")) for s in students}
        self.assertIn(self.ids["s1"], ids)
        self.assertIn(self.ids["s2"], ids)
        self.assertNotIn(self.ids["s3"], ids)

        resp = self.get(
            f"/api/v1/teacher/classes/{cid}/students?search=Test Student Two",
            self.tokens["teacher"],
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        students = data if isinstance(data, list) else data.get("data", data.get("students", []))
        ids = {s.get("student_id", s.get("id")) for s in students}
        self.assertEqual(ids, {self.ids["s2"]})

    # -------------------------------------------------
    # ATTENDANCE
    # -------------------------------------------------
    def test_attendance_create_update_invalid(self):
        cid = self.ids["class_a"]
        tid = self.tokens["teacher"]
        today = date.today().isoformat()

        sheet = self.get(f"/api/v1/teacher/classes/{cid}/attendance?attendance_date={today}", tid)
        self.assertEqual(sheet.status_code, 200)

        save = self.post(
            f"/api/v1/teacher/classes/{cid}/attendance",
            tid,
            json={"attendance_date": today, "records": [
                {"student_id": self.ids["s1"], "status": "PRESENT"},
                {"student_id": self.ids["s2"], "status": "ABSENT"},
            ]},
        )
        self.assertEqual(save.status_code, 200, save.text)

        sheet = self.get(f"/api/v1/teacher/classes/{cid}/attendance?attendance_date={today}", tid)
        body = sheet.json()
        students = body.get("students", [])
        by_id = {s["student_id"]: s for s in students}
        self.assertEqual(by_id[self.ids["s1"]]["status"], "PRESENT")
        self.assertEqual(by_id[self.ids["s2"]]["status"], "ABSENT")
        self.assertEqual(body.get("absent_count"), 1)

        update = self.post(
            f"/api/v1/teacher/classes/{cid}/attendance",
            tid,
            json={"attendance_date": today, "records": [
                {"student_id": self.ids["s1"], "status": "ABSENT"},
            ]},
        )
        self.assertEqual(update.status_code, 200, update.text)
        sheet = self.get(f"/api/v1/teacher/classes/{cid}/attendance?attendance_date={today}", tid)
        by_id = {s["student_id"]: s for s in sheet.json().get("students", [])}
        self.assertEqual(by_id[self.ids["s1"]]["status"], "ABSENT")

        invalid = self.post(
            f"/api/v1/teacher/classes/{cid}/attendance",
            tid,
            json={"attendance_date": today, "records": [
                {"student_id": self.ids["s1"], "status": "LATE"},
            ]},
        )
        self.assertEqual(invalid.status_code, 422)

        future = self.post(
            f"/api/v1/teacher/classes/{cid}/attendance",
            tid,
            json={"attendance_date": (date.today() + timedelta(days=2)).isoformat(),
                  "records": [{"student_id": self.ids["s1"], "status": "PRESENT"}]},
        )
        self.assertEqual(future.status_code, 422)

        dup = self.post(
            f"/api/v1/teacher/classes/{cid}/attendance",
            tid,
            json={"attendance_date": today, "records": [
                {"student_id": self.ids["s1"], "status": "PRESENT"},
                {"student_id": self.ids["s1"], "status": "ABSENT"},
            ]},
        )
        self.assertEqual(dup.status_code, 422)

        # student of another class must be rejected
        cross = self.post(
            f"/api/v1/teacher/classes/{cid}/attendance",
            tid,
            json={"attendance_date": today, "records": [
                {"student_id": self.ids["s3"], "status": "PRESENT"},
            ]},
        )
        self.assertIn(cross.status_code, (400, 403, 404))

    # -------------------------------------------------
    # HOMEWORK (+ parent notification)
    # -------------------------------------------------
    def test_homework_create_validations_notification(self):
        cid = self.ids["class_a"]
        tid = self.tokens["teacher"]

        create = self.post(
            f"/api/v1/teacher/classes/{cid}/homework",
            tid,
            json={"subject": "WRONG-SUBJECT-TAMPER", "title": "Algebra worksheet",
                  "description": "Exercise 4.2", "assigned_date": date.today().isoformat(),
                  "due_date": (date.today() + timedelta(days=3)).isoformat()},
        )
        self.assertIn(create.status_code, (200, 201), create.text)
        hw = create.json()
        # subject must come from the DB assignment, never the client payload
        self.assertEqual((hw.get("subject") or "").lower(), "mathematics")

        overdue = self.post(
            f"/api/v1/teacher/classes/{cid}/homework",
            tid,
            json={"subject": "Mathematics", "title": "Bad dates",
                  "assigned_date": date.today().isoformat(),
                  "due_date": (date.today() - timedelta(days=1)).isoformat()},
        )
        self.assertIn(overdue.status_code, (400, 422))

        listing = self.get(f"/api/v1/teacher/classes/{cid}/homework", tid)
        self.assertEqual(listing.status_code, 200)
        items = listing.json().get("homework", [])
        self.assertTrue(any(h["title"] == "Algebra worksheet" for h in items))

        # parents of the class receive a HOMEWORK notification
        from app.database import SessionLocal
        from app.models.notification import Notification
        db = SessionLocal()
        try:
            n = (db.query(Notification)
                 .filter(Notification.user_id == self.ids["parent"],
                         Notification.notification_type == "HOMEWORK")
                 .count())
            self.assertGreaterEqual(n, 1, "parent did not receive homework notification")
        finally:
            db.close()

        # teacher cannot create homework for an unassigned class
        other = self.post(
            f"/api/v1/teacher/classes/{self.ids["class_b"]}/homework",
            tid,
            json={"subject": "Science", "title": "X", "assigned_date": date.today().isoformat(),
                  "due_date": (date.today() + timedelta(days=1)).isoformat()},
        )
        self.assertIn(other.status_code, (403, 404))

    # -------------------------------------------------
    # EXAMS + RESULTS
    # -------------------------------------------------
    def test_exams_and_result_entry(self):
        tid = self.tokens["teacher"]
        cid = self.ids["class_a"]
        eid = self.ids["exam"]

        exams = self.get("/api/v1/teacher/exams", tid)
        self.assertEqual(exams.status_code, 200)
        body = exams.json()
        exams_list = body if isinstance(body, list) else body.get("data", body.get("exams", []))
        self.assertTrue(any(e["id"] == eid for e in exams_list))

        # the publish guard: results of a published exam cannot be edited
        guarded = self.post(
            f"/api/v1/teacher/classes/{cid}/results",
            tid,
            json={"exam_id": eid, "subject": "Mathematics", "results": [
                {"student_id": self.ids["s1"], "max_marks": 100, "obtained_marks": 10},
            ]},
        )
        self.assertIn(guarded.status_code, (403, 409))

        # unpublish via the admin API, then save results
        unpublish = self.patch(
            f"/api/v1/admin/exams/{eid}/publish-results",
            self.tokens["admin"],
            json={"results_published": False},
        )
        self.assertEqual(unpublish.status_code, 200, unpublish.text)

        sheet = self.get(f"/api/v1/teacher/classes/{cid}/results?exam_id={eid}&subject=Mathematics", tid)
        self.assertEqual(sheet.status_code, 200)

        save = self.post(
            f"/api/v1/teacher/classes/{cid}/results",
            tid,
            json={"exam_id": eid, "subject": "Mathematics", "results": [
                {"student_id": self.ids["s1"], "max_marks": 100, "obtained_marks": 92},
                {"student_id": self.ids["s2"], "max_marks": 100, "obtained_marks": 45},
            ]},
        )
        self.assertEqual(save.status_code, 200, save.text)

        sheet = self.get(f"/api/v1/teacher/classes/{cid}/results?exam_id={eid}&subject=Mathematics", tid)
        by_id = {s["student_id"]: s for s in sheet.json().get("students", [])}
        self.assertEqual(by_id[self.ids["s1"]]["grade"], "A+")

        # duplicate student in one payload
        dup = self.post(
            f"/api/v1/teacher/classes/{cid}/results",
            tid,
            json={"exam_id": eid, "subject": "Mathematics", "results": [
                {"student_id": self.ids["s1"], "max_marks": 100, "obtained_marks": 50},
                {"student_id": self.ids["s1"], "max_marks": 100, "obtained_marks": 60},
            ]},
        )
        self.assertEqual(dup.status_code, 422)

        # obtained > max
        over = self.post(
            f"/api/v1/teacher/classes/{cid}/results",
            tid,
            json={"exam_id": eid, "subject": "Mathematics", "results": [
                {"student_id": self.ids["s1"], "max_marks": 100, "obtained_marks": 101},
            ]},
        )
        self.assertEqual(over.status_code, 422)

        # ABSENT result must not carry marks
        absent = self.post(
            f"/api/v1/teacher/classes/{cid}/results",
            tid,
            json={"exam_id": eid, "subject": "Mathematics", "results": [
                {"student_id": self.ids["s2"], "max_marks": 100,
                 "obtained_marks": 10, "result_status": "ABSENT"},
            ]},
        )
        self.assertEqual(absent.status_code, 422)

        # unassigned subject
        wrong_subject = self.post(
            f"/api/v1/teacher/classes/{cid}/results",
            tid,
            json={"exam_id": eid, "subject": "Science", "results": [
                {"student_id": self.ids["s1"], "max_marks": 100, "obtained_marks": 10},
            ]},
        )
        self.assertIn(wrong_subject.status_code, (400, 403, 404))

        # class of another teacher
        other_class = self.post(
            f"/api/v1/teacher/classes/{self.ids["class_b"]}/results",
            tid,
            json={"exam_id": eid, "subject": "Mathematics", "results": [
                {"student_id": self.ids["s3"], "max_marks": 100, "obtained_marks": 10},
            ]},
        )
        self.assertIn(other_class.status_code, (400, 403, 404))

    # -------------------------------------------------
    # EXAM SCHEDULE
    # -------------------------------------------------
    def test_exam_schedule_crud_and_authorization(self):
        tid = self.tokens["teacher"]
        payload = {
            "class_id": self.ids["class_a"],
            "exam_id": self.ids["exam"],
            "subject": "Mathematics",
            "exam_date": (date.today() - timedelta(days=4)).isoformat(),
            "start_time": "10:00",
            "end_time": "12:00",
            "room": "T-101",
        }
        create = self.post("/api/v1/teacher/exam-schedule", tid, json=payload)
        self.assertEqual(create.status_code, 201, create.text)
        sid = create.json()["id"]

        duplicate = self.post("/api/v1/teacher/exam-schedule", tid, json=payload)
        self.assertEqual(duplicate.status_code, 409)

        bad_times = dict(payload, start_time="13:00", end_time="11:00")
        bad = self.post("/api/v1/teacher/exam-schedule", tid, json=bad_times)
        self.assertEqual(bad.status_code, 422)

        update = self.put(
            f"/api/v1/teacher/exam-schedule/{sid}",
            tid,
            json={"room": "T-102"},
        )
        self.assertEqual(update.status_code, 200, update.text)

        # schedule for a class the teacher is not assigned to
        foreign = dict(payload, class_id=self.ids["class_b"], subject="Science",
                       start_time="14:00", end_time="15:00")
        foreign_resp = self.post("/api/v1/teacher/exam-schedule", tid, json=foreign)
        self.assertIn(foreign_resp.status_code, (400, 403, 404))

        delete = self.delete(f"/api/v1/teacher/exam-schedule/{sid}", tid)
        self.assertIn(delete.status_code, (200, 204))

        gone = self.get("/api/v1/teacher/exam-schedule?class_id="
                        f"{self.ids["class_a"]}", tid)
        self.assertEqual(gone.status_code, 200)

    # -------------------------------------------------
    # CROSS-ROLE AUTHORIZATION
    # -------------------------------------------------
    def test_teacher_cannot_access_parent_or_admin(self):
        self.assertEqual(
            self.get("/api/v1/parent/children", self.tokens["teacher"]).status_code, 403)
        self.assertEqual(
            self.get("/api/v1/admin/users", self.tokens["teacher"]).status_code, 403)

    def test_unauthenticated_access_rejected(self):
        self.assertEqual(self.get("/api/v1/teacher/classes").status_code, 401)
        self.assertEqual(self.get("/api/v1/parent/children").status_code, 401)
        self.assertEqual(self.get("/api/v1/admin/users").status_code, 401)


if __name__ == "__main__":
    unittest.main()


