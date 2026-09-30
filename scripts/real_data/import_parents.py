from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import csv
import secrets
import string
import sys


# =========================================================
# PATH SETUP
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
REPORTS_DIR = BASE_DIR / "reports"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =========================================================
# PROJECT IMPORTS
# =========================================================

from app.database import SessionLocal
from app.models.student import Student
from app.models.user import User
from app.models.parent_profile import ParentProfile
from app.models.parent_student import ParentStudent
from app.core.security import hash_password

from validate_complete_records import (
    read_structured_files,
    read_class_files,
    clean_admission_no,
    clean_text,
)

from dry_run_parent_import import (
    prepare_record,
    same_family,
    record_score,
    UnionFind,
    normalize_name,
)


# =========================================================
# CONFIG
# =========================================================

PROGRESS_EVERY = 25
CREDENTIALS_FILE = REPORTS_DIR / "parent_login_credentials.csv"
CREDENTIALS_TEMP_FILE = REPORTS_DIR / "parent_login_credentials.tmp.csv"


# =========================================================
# TEMP PASSWORD
# =========================================================


def generate_password() -> str:
    """Generate a temporary password satisfying the >= 8 char schema rule."""
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(10))
    return f"Rsy@{random_part}"


# =========================================================
# BUILD STUDENT RECORDS
# =========================================================


def build_student_records():
    raw_records = read_structured_files() + read_class_files()

    admission_groups = defaultdict(list)

    for raw_record in raw_records:
        record = prepare_record(raw_record)
        admission_no = record.get("admission_no")

        if not admission_no:
            continue

        admission_groups[admission_no].append(record)

    student_records = []
    conflicting_admissions = []

    for admission_no, records in admission_groups.items():
        student_names = {
            normalize_name(record.get("student_name"))
            for record in records
        }
        student_names.discard(None)

        # Same admission number pointing to more than one student name = hold back.
        if len(student_names) > 1:
            conflicting_admissions.append(admission_no)
            continue

        chosen = max(records, key=record_score)
        student_records.append(chosen)

    return student_records, conflicting_admissions


# =========================================================
# GROUP SIBLINGS
# =========================================================


def build_family_groups(student_records):
    union_find = UnionFind(len(student_records))
    indexes = defaultdict(list)

    for index, record in enumerate(student_records):
        phones = {
            phone
            for phone in (
                record.get("father_phone_valid"),
                record.get("mother_phone_valid"),
            )
            if phone
        }

        for phone in phones:
            indexes[("PHONE", phone)].append(index)

        email = record.get("parent_email_valid")
        if email:
            indexes[("EMAIL", email)].append(index)

        father = record.get("father_name_normalized")
        mother = record.get("mother_name_normalized")

        if father and mother:
            indexes[("NAMES", father, mother)].append(index)

    for candidates in indexes.values():
        if len(candidates) < 2:
            continue

        for position in range(len(candidates)):
            first_index = candidates[position]

            for next_position in range(position + 1, len(candidates)):
                second_index = candidates[next_position]

                if same_family(
                    student_records[first_index],
                    student_records[second_index],
                ):
                    union_find.union(first_index, second_index)

    family_groups = defaultdict(list)

    for index, record in enumerate(student_records):
        root = union_find.find(index)
        family_groups[root].append(record)

    return family_groups


# =========================================================
# SHARED EMAILS
# =========================================================


def get_shared_emails(family_groups):
    email_to_families = defaultdict(set)

    for family_id, records in family_groups.items():
        for record in records:
            email = record.get("parent_email_valid")
            if email:
                email_to_families[email].add(family_id)

    return {
        email
        for email, families in email_to_families.items()
        if len(families) > 1
    }


# =========================================================
# HELPERS
# =========================================================


def pick_parent_name(primary_record):
    return (
        clean_text(primary_record.get("father_name"))
        or clean_text(primary_record.get("mother_name"))
        or f"Parent of {clean_text(primary_record.get('student_name')) or 'Student'}"
    )


def pick_candidate_email(
    family_records,
    shared_emails,
    existing_emails,
    used_new_emails,
):
    family_emails = []

    for record in family_records:
        email = record.get("parent_email_valid")
        if email and email not in family_emails:
            family_emails.append(email)

    for email in family_emails:
        if email in shared_emails:
            continue
        if email in existing_emails:
            continue
        if email in used_new_emails:
            continue
        return email

    return None


def pick_family_phones(family_records):
    family_phones = []

    for record in family_records:
        for phone in (
            record.get("father_phone_valid"),
            record.get("mother_phone_valid"),
        ):
            if phone and phone not in family_phones:
                family_phones.append(phone)

    primary_phone = family_phones[0] if family_phones else None
    alternate_phone = family_phones[1] if len(family_phones) > 1 else None

    return primary_phone, alternate_phone


def pick_relationship(primary_record):
    if clean_text(primary_record.get("father_name")):
        return "Father"
    if clean_text(primary_record.get("mother_name")):
        return "Mother"
    return "Guardian"


def write_credentials_csv(credentials, destination):
    fieldnames = [
        "parent_user_id",
        "internal_username",
        "login_admission_numbers",
        "student_names",
        "parent_name",
        "phone",
        "email",
        "initial_password",
    ]

    with destination.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(credentials)


# =========================================================
# MAIN IMPORT
# =========================================================


def main():
    print("=" * 75, flush=True)
    print("ROSARY REAL PARENT IMPORT", flush=True)
    print("=" * 75, flush=True)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    student_records, conflicting_admissions = build_student_records()
    family_groups = build_family_groups(student_records)
    shared_emails = get_shared_emails(family_groups)

    total_families = len(family_groups)

    print(f"Usable student records : {len(student_records)}", flush=True)
    print(f"Family accounts planned: {total_families}", flush=True)
    print(f"Shared emails ignored  : {len(shared_emails)}", flush=True)
    print(flush=True)

    db = SessionLocal()
    credentials = []

    # If an old temp file exists from an interrupted run, remove it first.
    if CREDENTIALS_TEMP_FILE.exists():
        CREDENTIALS_TEMP_FILE.unlink()

    try:
        # -------------------------------------------------
        # DATABASE LOOKUPS
        # -------------------------------------------------

        db_students = db.query(Student).all()

        student_by_admission = {
            clean_admission_no(student.admission_no): student
            for student in db_students
        }

        existing_users = db.query(User).all()

        existing_usernames = {
            user.username.lower()
            for user in existing_users
            if user.username
        }

        existing_emails = {
            user.email.lower()
            for user in existing_users
            if user.email
        }

        existing_links = db.query(ParentStudent).all()
        linked_student_ids = {link.student_id for link in existing_links}

        # -------------------------------------------------
        # SAFETY CHECKS - NO DB CHANGES YET
        # -------------------------------------------------

        missing_students = []
        username_collisions = []
        already_linked = []
        planned_usernames = set()

        for family_records in family_groups.values():
            primary_record = max(family_records, key=record_score)
            username = f"PARENT_{primary_record['admission_no']}"
            username_lower = username.lower()

            if (
                username_lower in existing_usernames
                or username_lower in planned_usernames
            ):
                username_collisions.append(username)

            planned_usernames.add(username_lower)

            for record in family_records:
                admission_no = record["admission_no"]
                student = student_by_admission.get(admission_no)

                if not student:
                    missing_students.append(admission_no)
                    continue

                if student.id in linked_student_ids:
                    already_linked.append(admission_no)

        if missing_students or username_collisions or already_linked:
            print("IMPORT STOPPED", flush=True)
            print(f"Missing students    : {len(missing_students)}", flush=True)
            print(f"Username collisions : {len(username_collisions)}", flush=True)
            print(f"Already linked      : {len(already_linked)}", flush=True)
            db.rollback()
            return

        # -------------------------------------------------
        # IMPORT - ONE TRANSACTION
        # -------------------------------------------------

        used_new_emails = set()
        created_users = 0
        created_profiles = 0
        created_links = 0
        sibling_families = 0

        for family_index, family_records in enumerate(
            family_groups.values(),
            start=1,
        ):
            family_records = sorted(
                family_records,
                key=lambda item: item["admission_no"],
            )

            if len(family_records) > 1:
                sibling_families += 1

            primary_record = max(family_records, key=record_score)
            primary_admission = primary_record["admission_no"]
            internal_username = f"PARENT_{primary_admission}"
            parent_name = pick_parent_name(primary_record)

            candidate_email = pick_candidate_email(
                family_records=family_records,
                shared_emails=shared_emails,
                existing_emails=existing_emails,
                used_new_emails=used_new_emails,
            )

            if candidate_email:
                used_new_emails.add(candidate_email)

            primary_phone, alternate_phone = pick_family_phones(family_records)
            relationship = pick_relationship(primary_record)

            temporary_password = generate_password()

            # IMPORTANT: print before Argon2 hashing, because hashing is the slow step.
            if (
                family_index == 1
                or family_index % PROGRESS_EVERY == 0
                or family_index == total_families
            ):
                print(
                    f"Processing parent {family_index}/{total_families}...",
                    flush=True,
                )

            password_hash_value = hash_password(temporary_password)

            user = User(
                name=parent_name,
                username=internal_username,
                email=candidate_email,
                password_hash=password_hash_value,
                role="PARENT",
                is_active=True,
            )

            db.add(user)
            db.flush()  # obtain user.id without committing
            created_users += 1

            profile = ParentProfile(
                user_id=user.id,
                phone=primary_phone,
                alternate_phone=alternate_phone,
                occupation=None,
                address=clean_text(primary_record.get("address")),
                city=clean_text(primary_record.get("city")),
                state=clean_text(primary_record.get("state")),
                pincode=clean_text(primary_record.get("pincode")),
                profile_image_url=None,
            )

            db.add(profile)
            created_profiles += 1

            admission_numbers = []
            student_names = []

            for record in family_records:
                admission_no = record["admission_no"]
                student = student_by_admission[admission_no]

                db.add(
                    ParentStudent(
                        parent_user_id=user.id,
                        student_id=student.id,
                        relationship=relationship,
                    )
                )

                created_links += 1
                admission_numbers.append(admission_no)
                student_names.append(
                    str(record.get("student_name") or "")
                )

            credentials.append(
                {
                    "parent_user_id": user.id,
                    "internal_username": internal_username,
                    "login_admission_numbers": ", ".join(admission_numbers),
                    "student_names": ", ".join(student_names),
                    "parent_name": parent_name,
                    "phone": primary_phone or "",
                    "email": candidate_email or "",
                    "initial_password": temporary_password,
                }
            )

        # -------------------------------------------------
        # WRITE CREDENTIALS BEFORE COMMIT
        # -------------------------------------------------
        # If CSV writing fails, the database transaction is still rolled back.

        write_credentials_csv(credentials, CREDENTIALS_TEMP_FILE)

        # -------------------------------------------------
        # COMMIT DATABASE
        # -------------------------------------------------

        print("Committing database transaction...", flush=True)
        db.commit()

        # Commit succeeded. Publish the final credentials file atomically-ish.
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()

        CREDENTIALS_TEMP_FILE.replace(CREDENTIALS_FILE)

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        print(flush=True)
        print("=" * 75, flush=True)
        print("PARENT IMPORT SUCCESSFUL", flush=True)
        print("=" * 75, flush=True)
        print(f"Parent users created    : {created_users}", flush=True)
        print(f"Parent profiles created : {created_profiles}", flush=True)
        print(f"Parent-child links      : {created_links}", flush=True)
        print(f"Sibling families        : {sibling_families}", flush=True)
        print(f"Conflicting IDs skipped : {len(conflicting_admissions)}", flush=True)
        print(f"Credentials CSV         : {CREDENTIALS_FILE}", flush=True)

    except KeyboardInterrupt:
        db.rollback()

        if CREDENTIALS_TEMP_FILE.exists():
            CREDENTIALS_TEMP_FILE.unlink()

        print(flush=True)
        print("=" * 75, flush=True)
        print("IMPORT CANCELLED - DATABASE ROLLED BACK", flush=True)
        print("=" * 75, flush=True)
        print("No parent import was committed.", flush=True)

    except Exception as exc:
        db.rollback()

        if CREDENTIALS_TEMP_FILE.exists():
            CREDENTIALS_TEMP_FILE.unlink()

        print(flush=True)
        print("=" * 75, flush=True)
        print("PARENT IMPORT FAILED - DATABASE ROLLED BACK", flush=True)
        print("=" * 75, flush=True)
        print(f"Reason: {exc}", flush=True)
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
