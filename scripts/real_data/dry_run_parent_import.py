from collections import defaultdict
from pathlib import Path
import re
import sys


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from app.database import SessionLocal

from app.models.student import Student
from app.models.user import User
from app.models.parent_profile import ParentProfile
from app.models.parent_student import ParentStudent

from validate_complete_records import (
    read_structured_files,
    read_class_files,
    clean_phone,
    clean_text,
    clean_admission_no,
)


# =========================================================
# CLEANING
# =========================================================

def normalize_name(value):
    value = clean_text(value)

    if not value:
        return None

    return " ".join(
        value.upper().split()
    )


def normalize_email(value):
    value = clean_text(value)

    if not value:
        return None

    value = value.lower()

    pattern = (
        r"^[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+"
        r"\.[A-Za-z]{2,}$"
    )

    if not re.match(
        pattern,
        value,
    ):
        return None

    return value


def valid_phone(value):
    phone = clean_phone(value)

    if not phone:
        return None

    if (
        len(phone) != 10
        or not phone.isdigit()
    ):
        return None

    return phone


# =========================================================
# UNION FIND
# =========================================================

class UnionFind:
    def __init__(self, size):
        self.parent = list(
            range(size)
        )

    def find(self, value):
        if (
            self.parent[value]
            != value
        ):
            self.parent[value] = (
                self.find(
                    self.parent[value]
                )
            )

        return self.parent[value]

    def union(
        self,
        first,
        second,
    ):
        root_first = self.find(
            first
        )

        root_second = self.find(
            second
        )

        if root_first != root_second:
            self.parent[
                root_second
            ] = root_first


# =========================================================
# PREPARE RECORD
# =========================================================

def prepare_record(record):
    return {
        **record,

        "admission_no":
            clean_admission_no(
                record.get(
                    "admission_no"
                )
            ),

        "father_name_normalized":
            normalize_name(
                record.get(
                    "father_name"
                )
            ),

        "mother_name_normalized":
            normalize_name(
                record.get(
                    "mother_name"
                )
            ),

        "father_phone_valid":
            valid_phone(
                record.get(
                    "father_phone"
                )
            ),

        "mother_phone_valid":
            valid_phone(
                record.get(
                    "mother_phone"
                )
            ),

        "parent_email_valid":
            normalize_email(
                record.get(
                    "parent_email"
                )
            ),
    }


# =========================================================
# FAMILY MATCH
# =========================================================

def same_family(
    first,
    second,
):
    first_phones = {
        phone
        for phone in [
            first.get(
                "father_phone_valid"
            ),
            first.get(
                "mother_phone_valid"
            ),
        ]
        if phone
    }

    second_phones = {
        phone
        for phone in [
            second.get(
                "father_phone_valid"
            ),
            second.get(
                "mother_phone_valid"
            ),
        ]
        if phone
    }

    shared_phone = bool(
        first_phones
        & second_phones
    )

    same_email = (
        first.get(
            "parent_email_valid"
        )
        and
        first.get(
            "parent_email_valid"
        )
        ==
        second.get(
            "parent_email_valid"
        )
    )

    father_match = (
        first.get(
            "father_name_normalized"
        )
        and
        first.get(
            "father_name_normalized"
        )
        ==
        second.get(
            "father_name_normalized"
        )
    )

    mother_match = (
        first.get(
            "mother_name_normalized"
        )
        and
        first.get(
            "mother_name_normalized"
        )
        ==
        second.get(
            "mother_name_normalized"
        )
    )

    if (
        same_email
        and shared_phone
    ):
        return True

    if (
        shared_phone
        and (
            father_match
            or mother_match
        )
    ):
        return True

    if (
        father_match
        and mother_match
    ):
        return True

    return False


# =========================================================
# CHOOSE BEST SOURCE RECORD
# =========================================================

def record_score(record):
    fields = [
        "father_name",
        "mother_name",
        "father_phone_valid",
        "mother_phone_valid",
        "parent_email_valid",
        "address",
        "city",
        "state",
        "pincode",
    ]

    return sum(
        bool(
            record.get(field)
        )
        for field in fields
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 75)
    print("ROSARY FINAL PARENT IMPORT - DRY RUN")
    print("=" * 75)

    # -----------------------------------------------------
    # READ EXCEL
    # -----------------------------------------------------

    raw_records = (
        read_structured_files()
        + read_class_files()
    )

    # -----------------------------------------------------
    # ONE RECORD PER ADMISSION NUMBER
    # -----------------------------------------------------

    admission_groups = defaultdict(
        list
    )

    for raw_record in raw_records:

        record = prepare_record(
            raw_record
        )

        admission_no = (
            record["admission_no"]
        )

        if not admission_no:
            continue

        admission_groups[
            admission_no
        ].append(
            record
        )

    student_records = []

    conflicting_admissions = []

    for (
        admission_no,
        records,
    ) in admission_groups.items():

        student_names = {
            normalize_name(
                record.get(
                    "student_name"
                )
            )
            for record in records
        }

        student_names.discard(
            None
        )

        if len(student_names) > 1:

            conflicting_admissions.append(
                admission_no
            )

            continue

        chosen = max(
            records,
            key=record_score,
        )

        student_records.append(
            chosen
        )

    # -----------------------------------------------------
    # FAMILY GROUPING
    # -----------------------------------------------------

    union_find = UnionFind(
        len(student_records)
    )

    indexes = defaultdict(
        list
    )

    for index, record in enumerate(
        student_records
    ):

        phones = {
            phone
            for phone in [
                record.get(
                    "father_phone_valid"
                ),
                record.get(
                    "mother_phone_valid"
                ),
            ]
            if phone
        }

        for phone in phones:
            indexes[
                (
                    "PHONE",
                    phone,
                )
            ].append(
                index
            )

        email = record.get(
            "parent_email_valid"
        )

        if email:
            indexes[
                (
                    "EMAIL",
                    email,
                )
            ].append(
                index
            )

        father = record.get(
            "father_name_normalized"
        )

        mother = record.get(
            "mother_name_normalized"
        )

        if father and mother:
            indexes[
                (
                    "NAMES",
                    father,
                    mother,
                )
            ].append(
                index
            )

    for candidates in (
        indexes.values()
    ):

        if len(candidates) < 2:
            continue

        for position in range(
            len(candidates)
        ):

            first_index = (
                candidates[position]
            )

            for next_position in range(
                position + 1,
                len(candidates),
            ):

                second_index = (
                    candidates[
                        next_position
                    ]
                )

                if same_family(
                    student_records[
                        first_index
                    ],
                    student_records[
                        second_index
                    ],
                ):
                    union_find.union(
                        first_index,
                        second_index,
                    )

    family_groups = defaultdict(
        list
    )

    for index, record in enumerate(
        student_records
    ):

        root = union_find.find(
            index
        )

        family_groups[
            root
        ].append(
            record
        )

    # -----------------------------------------------------
    # DETECT EMAILS SHARED BETWEEN DIFFERENT FAMILIES
    # -----------------------------------------------------

    email_to_families = defaultdict(
        set
    )

    for family_id, records in (
        family_groups.items()
    ):

        for record in records:

            email = record.get(
                "parent_email_valid"
            )

            if email:

                email_to_families[
                    email
                ].add(
                    family_id
                )

    shared_emails = {
        email
        for email, families
        in email_to_families.items()
        if len(families) > 1
    }

    # -----------------------------------------------------
    # DATABASE DATA
    # -----------------------------------------------------

    db = SessionLocal()

    try:

        db_students = (
            db.query(Student)
            .all()
        )

        student_by_admission = {
            clean_admission_no(
                student.admission_no
            ):
            student

            for student
            in db_students
        }

        existing_users = (
            db.query(User)
            .all()
        )

        existing_usernames = {
            user.username.lower()
            for user in existing_users
        }

        existing_emails = {
            user.email.lower()
            for user in existing_users
            if user.email
        }

        existing_links = (
            db.query(
                ParentStudent
            )
            .all()
        )

        linked_student_ids = {
            link.student_id
            for link in existing_links
        }

        # -------------------------------------------------
        # BUILD IMPORT PLAN
        # -------------------------------------------------

        proposed_accounts = []

        username_collisions = []

        missing_students = []

        already_linked_students = []

        proposed_links = 0

        null_email_accounts = 0

        unique_email_accounts = 0

        used_new_emails = set()

        sibling_families = 0

        for (
            family_id,
            family_records,
        ) in family_groups.items():

            if len(
                family_records
            ) > 1:
                sibling_families += 1

            family_records = sorted(
                family_records,
                key=lambda item:
                    item["admission_no"],
            )

            primary_record = max(
                family_records,
                key=record_score,
            )

            primary_admission = (
                primary_record[
                    "admission_no"
                ]
            )

            internal_username = (
                f"PARENT_"
                f"{primary_admission}"
            )

            if (
                internal_username.lower()
                in existing_usernames
            ):
                username_collisions.append(
                    internal_username
                )

            # ---------------------------------------------
            # EMAIL
            # ---------------------------------------------

            candidate_email = None

            family_emails = []

            for record in (
                family_records
            ):

                email = record.get(
                    "parent_email_valid"
                )

                if (
                    email
                    and email
                    not in family_emails
                ):
                    family_emails.append(
                        email
                    )

            for email in family_emails:

                if email in shared_emails:
                    continue

                if email in existing_emails:
                    continue

                if email in used_new_emails:
                    continue

                candidate_email = email
                break

            if candidate_email:

                unique_email_accounts += 1

                used_new_emails.add(
                    candidate_email
                )

            else:
                null_email_accounts += 1

            # ---------------------------------------------
            # CONTACT
            # ---------------------------------------------

            primary_phone = (
                primary_record.get(
                    "father_phone_valid"
                )
                or
                primary_record.get(
                    "mother_phone_valid"
                )
            )

            alternate_phone = None

            possible_phones = [
                primary_record.get(
                    "father_phone_valid"
                ),
                primary_record.get(
                    "mother_phone_valid"
                ),
            ]

            for phone in possible_phones:

                if (
                    phone
                    and phone
                    != primary_phone
                ):
                    alternate_phone = (
                        phone
                    )
                    break

            # ---------------------------------------------
            # PARENT NAME
            # ---------------------------------------------

            parent_name = (
                clean_text(
                    primary_record.get(
                        "father_name"
                    )
                )
                or
                clean_text(
                    primary_record.get(
                        "mother_name"
                    )
                )
                or
                (
                    "Parent of "
                    + str(
                        primary_record.get(
                            "student_name"
                        )
                    )
                )
            )

            # ---------------------------------------------
            # STUDENT LINKS
            # ---------------------------------------------

            family_student_ids = []

            for record in (
                family_records
            ):

                admission_no = (
                    record[
                        "admission_no"
                    ]
                )

                student = (
                    student_by_admission.get(
                        admission_no
                    )
                )

                if not student:

                    missing_students.append(
                        admission_no
                    )

                    continue

                if (
                    student.id
                    in linked_student_ids
                ):
                    already_linked_students.append(
                        admission_no
                    )

                    continue

                family_student_ids.append(
                    student.id
                )

                proposed_links += 1

            proposed_accounts.append(
                {
                    "username":
                        internal_username,

                    "parent_name":
                        parent_name,

                    "email":
                        candidate_email,

                    "phone":
                        primary_phone,

                    "alternate_phone":
                        alternate_phone,

                    "student_ids":
                        family_student_ids,

                    "admission_numbers":
                        [
                            record[
                                "admission_no"
                            ]
                            for record
                            in family_records
                        ],
                }
            )

        # -------------------------------------------------
        # OUTPUT
        # -------------------------------------------------

        print()
        print("=" * 75)
        print("FINAL PARENT IMPORT PLAN")
        print("=" * 75)

        print(
            f"Usable students                : "
            f"{len(student_records)}"
        )

        print(
            f"Conflicting admissions held    : "
            f"{len(conflicting_admissions)}"
        )

        print()
        print(
            f"Parent accounts to create      : "
            f"{len(proposed_accounts)}"
        )

        print(
            f"Sibling families               : "
            f"{sibling_families}"
        )

        print(
            f"Parent-child links to create   : "
            f"{proposed_links}"
        )

        print()
        print(
            f"Accounts with unique email     : "
            f"{unique_email_accounts}"
        )

        print(
            f"Accounts with email = NULL     : "
            f"{null_email_accounts}"
        )

        print(
            f"Shared emails ignored          : "
            f"{len(shared_emails)}"
        )

        print()
        print(
            f"Username collisions            : "
            f"{len(username_collisions)}"
        )

        print(
            f"Students missing from DB       : "
            f"{len(missing_students)}"
        )

        print(
            f"Already-linked real students   : "
            f"{len(already_linked_students)}"
        )

        print()
        print(
            "DATABASE CHANGES               : 0"
        )

        print(
            "MODE                           : DRY RUN ONLY"
        )

        # -------------------------------------------------
        # SAFETY STATUS
        # -------------------------------------------------

        print()
        print("=" * 75)
        print("SAFETY STATUS")
        print("=" * 75)

        if (
            username_collisions
            or missing_students
            or already_linked_students
        ):
            print(
                "NOT READY FOR IMPORT"
            )

        else:
            print(
                "READY FOR PARENT IMPORT"
            )

        # -------------------------------------------------
        # FIRST 10
        # -------------------------------------------------

        print()
        print("=" * 75)
        print("FIRST 10 PARENT ACCOUNTS")
        print("=" * 75)

        for account in (
            proposed_accounts[:10]
        ):

            print()

            print(
                f"Username      : "
                f"{account['username']}"
            )

            print(
                f"Parent Name   : "
                f"{account['parent_name']}"
            )

            print(
                f"Email         : "
                f"{account['email']}"
            )

            print(
                f"Phone         : "
                f"{account['phone']}"
            )

            print(
                f"Children      : "
                f"{', '.join(account['admission_numbers'])}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()