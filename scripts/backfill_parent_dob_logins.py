"""Create missing admission-number + DOB parent logins.

The command is a dry run unless ``--apply`` is supplied. Existing parent
links and accounts are never replaced, so sibling/shared parent accounts and
changed passwords remain intact.
"""

import argparse

from sqlalchemy import func

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.parent_profile import ParentProfile
from app.models.parent_student import ParentStudent
from app.models.student import Student
from app.models.user import User


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backfill missing parent DOB logins",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the backfill (the default is a dry run)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    with SessionLocal() as db:
        linked_student_ids = {
            student_id
            for (student_id,) in (
                db.query(
                ParentStudent.student_id,
                )
                .join(
                    User,
                    User.id == ParentStudent.parent_user_id,
                )
                .filter(func.upper(User.role) == "PARENT")
                .all()
            )
        }

        students = (
            db.query(Student)
            .filter(Student.date_of_birth.is_not(None))
            .order_by(Student.id.asc())
            .all()
        )
        missing_dob_count = (
            db.query(Student)
            .filter(Student.date_of_birth.is_(None))
            .count()
        )
        unlinked_students = [
            student
            for student in students
            if student.id not in linked_student_ids
        ]

        inactive_generated_accounts = (
            db.query(User)
            .join(
                ParentStudent,
                ParentStudent.parent_user_id == User.id,
            )
            .join(
                Student,
                Student.id == ParentStudent.student_id,
            )
            .filter(
                Student.date_of_birth.is_not(None),
                Student.is_active.is_(True),
                User.is_active.is_(False),
                func.lower(User.username)
                == func.lower(
                    func.concat(
                        "PARENT_",
                        Student.admission_no,
                    )
                ),
            )
            .distinct()
            .all()
        )

        collisions = []
        reusable_accounts = 0

        for student in unlinked_students:
            parent_username = f"PARENT_{student.admission_no}"
            candidate = (
                db.query(User)
                .filter(
                    func.lower(User.username)
                    == parent_username.lower()
                )
                .first()
            )
            if candidate and candidate.role.strip().upper() != "PARENT":
                collisions.append(parent_username)
            elif candidate:
                reusable_accounts += 1

        print(f"Students with DOB: {len(students)}")
        print(f"Already linked: {len(linked_student_ids)}")
        print(f"Missing links to create: {len(unlinked_students)}")
        print(f"Existing parent accounts to reuse: {reusable_accounts}")
        print(
            "Inactive generated accounts to reactivate: "
            f"{len(inactive_generated_accounts)}"
        )
        print(f"Students missing DOB: {missing_dob_count}")

        if collisions:
            print(f"Stopped: {len(collisions)} username collision(s)")
            db.rollback()
            raise SystemExit(1)

        if not args.apply:
            print("Dry run only; use --apply to commit")
            return

        created_users = 0
        created_profiles = 0
        created_links = 0

        for user in inactive_generated_accounts:
            user.is_active = True

        try:
            for index, student in enumerate(unlinked_students, start=1):
                parent_username = f"PARENT_{student.admission_no}"
                user = (
                    db.query(User)
                    .filter(
                        func.lower(User.username)
                        == parent_username.lower()
                    )
                    .first()
                )

                if user is None:
                    dob_password = student.date_of_birth.strftime("%d%m%Y")
                    user = User(
                        name=f"Parent of {student.full_name}",
                        username=parent_username,
                        email=None,
                        password_hash=hash_password(dob_password),
                        role="PARENT",
                        is_active=bool(student.is_active),
                    )
                    db.add(user)
                    db.flush()
                    created_users += 1

                profile = (
                    db.query(ParentProfile)
                    .filter(ParentProfile.user_id == user.id)
                    .first()
                )
                if profile is None:
                    db.add(ParentProfile(user_id=user.id))
                    created_profiles += 1

                db.add(
                    ParentStudent(
                        parent_user_id=user.id,
                        student_id=student.id,
                        relationship="Guardian",
                    )
                )
                created_links += 1

                if index % 25 == 0 or index == len(unlinked_students):
                    print(f"Prepared {index}/{len(unlinked_students)} logins")

            db.commit()
        except Exception:
            db.rollback()
            raise

        print(f"Created users: {created_users}")
        print(f"Created profiles: {created_profiles}")
        print(f"Created links: {created_links}")
        print(f"Reactivated accounts: {len(inactive_generated_accounts)}")
        print("Backfill committed")


if __name__ == "__main__":
    main()
