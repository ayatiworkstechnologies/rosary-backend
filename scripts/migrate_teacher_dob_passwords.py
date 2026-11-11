"""Replace teacher password hashes with DOB passwords in DDMMYYYY format."""

import argparse

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.teacher_profile import TeacherProfile
from app.models.user import User


def parse_args():
    parser = argparse.ArgumentParser(
        description="Migrate teacher passwords to DOB",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the migration (the default is a dry run)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    with SessionLocal() as db:
        teachers = (
            db.query(User, TeacherProfile)
            .join(
                TeacherProfile,
                TeacherProfile.user_id == User.id,
            )
            .filter(User.role.ilike("TEACHER"))
            .order_by(User.id.asc())
            .all()
        )
        eligible = [
            (user, profile)
            for user, profile in teachers
            if profile.date_of_birth is not None
        ]
        missing_dob = len(teachers) - len(eligible)

        print(f"Teacher accounts: {len(teachers)}")
        print(f"Ready to migrate: {len(eligible)}")
        print(f"Missing DOB: {missing_dob}")

        if not args.apply:
            print("Dry run only; use --apply to commit")
            return

        try:
            for index, (user, profile) in enumerate(eligible, start=1):
                password = profile.date_of_birth.strftime("%d%m%Y")
                user.password_hash = hash_password(password)

                if index % 10 == 0 or index == len(eligible):
                    print(f"Prepared {index}/{len(eligible)} password hashes")

            db.commit()
        except Exception:
            db.rollback()
            raise

        print(f"Migrated password hashes: {len(eligible)}")
        print("Migration committed")


if __name__ == "__main__":
    main()
