"""Read-only audit of issued Rosary Parent credentials against the current DB.

Run from the rosary-backend project root:
    python audit_parent_logins.py
or:
    python audit_parent_logins.py path/to/parent_login_credentials.csv

Does not create users, reset passwords, generate tokens, or log plaintext credentials.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

from app.core.security import verify_password
from app.database import SessionLocal
from app.models.parent_student import ParentStudent
from app.models.student import Student
from app.models.user import User


def locate_credentials() -> Path:
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser().resolve()
        if not p.is_file():
            raise SystemExit(f"Credentials CSV not found: {p}")
        return p
    files = list(Path.cwd().rglob("parent_login_credentials.csv"))
    if len(files) != 1:
        raise SystemExit(
            "Expected one parent_login_credentials.csv inside this backend. "
            "Pass the exact CSV path as the first argument."
        )
    return files[0]


def main():
    csv_path = locate_credentials()
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        credentials = list(csv.DictReader(handle))
    required = {"parent_user_id", "login_admission_numbers", "initial_password"}
    if not credentials or not required.issubset(credentials[0]):
        raise SystemExit("Credential CSV is empty or has unexpected headers")

    db = SessionLocal()
    try:
        users = {u.id: u for u in db.query(User).filter(User.role == "PARENT").all()}
        students = {s.admission_no.strip(): s for s in db.query(Student).all()}
        links_by_student = {}
        for link in db.query(ParentStudent).order_by(ParentStudent.id.asc()).all():
            links_by_student.setdefault(link.student_id, []).append(link)

        counts = Counter()
        issues = []
        password_checks = {}  # parent ID -> password match result, no plaintext stored
        for row in credentials:
            parent_id = int(row["parent_user_id"])
            password = row["initial_password"]
            parent = users.get(parent_id)
            if parent_id not in password_checks:
                if parent is None:
                    password_checks[parent_id] = "PARENT_NOT_FOUND"
                elif not parent.is_active:
                    password_checks[parent_id] = "PARENT_INACTIVE"
                else:
                    try:
                        password_checks[parent_id] = (
                            "PASS" if verify_password(password, parent.password_hash)
                            else "PASSWORD_MISMATCH"
                        )
                    except Exception:
                        password_checks[parent_id] = "PASSWORD_HASH_ERROR"

            for admission in row["login_admission_numbers"].split(","):
                admission = admission.strip()
                if not admission:
                    continue
                counts["admissions_checked"] += 1
                reason = password_checks[parent_id]
                student = students.get(admission)
                if student is None:
                    reason = "STUDENT_NOT_FOUND"
                else:
                    links = links_by_student.get(student.id, [])
                    if not links:
                        reason = "NO_PARENT_LINK"
                    elif links[0].parent_user_id != parent_id:
                        reason = "LOGIN_SELECTS_DIFFERENT_PARENT"
                if reason == "PASS":
                    counts["ready"] += 1
                else:
                    counts[reason] += 1
                    issues.append([admission, parent_id, reason])

        out = Path("parent_login_issues.csv")
        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["admission_no", "parent_user_id", "issue"])
            writer.writerows(issues)

        print("Credential records:", len(credentials))
        print("Admission logins checked:", counts["admissions_checked"])
        print("Parent password hashes checked:", len(password_checks))
        print("READY (correct parent mapping and matching password):", counts["ready"])
        print("NOT READY:", len(issues))
        for issue in sorted(set(counts) - {"admissions_checked", "ready"}):
            print(f"  {issue}: {counts[issue]}")
        print("Issues report:", out.resolve())
        print("NOTE: This audit does not test frontend/network availability.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
