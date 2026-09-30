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
# NORMALIZATION
# =========================================================

def normalize_name(value):
    value = clean_text(value)

    if not value:
        return None

    value = " ".join(
        value.upper().split()
    )

    return value


def normalize_email(value):
    value = clean_text(value)

    if not value:
        return None

    value = value.lower()

    if not re.match(
        r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
        value,
    ):
        return None

    return value


def valid_phone(value):
    phone = clean_phone(value)

    if not phone:
        return None

    if len(phone) != 10:
        return None

    if not phone.isdigit():
        return None

    return phone


# =========================================================
# UNION-FIND FOR SIBLING GROUPING
# =========================================================

class UnionFind:
    def __init__(self, size):
        self.parent = list(
            range(size)
        )

    def find(self, value):
        while (
            self.parent[value]
            != value
        ):
            self.parent[value] = (
                self.parent[
                    self.parent[value]
                ]
            )

            value = self.parent[value]

        return value

    def union(self, first, second):
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
# RECORD PREPARATION
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
# CHECK WHETHER TWO STUDENTS BELONG TO SAME FAMILY
# =========================================================

def same_family(first, second):

    # -----------------------------------------------------
    # ALL VALID PARENT PHONES
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # PARENT NAMES
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # FAMILY RULES
    # -----------------------------------------------------

    # Same email + at least one shared parent phone.
    # Handles swapped Father/Mother phone columns.
    if (
        same_email
        and shared_phone
    ):
        return True

    # Shared phone + matching father/mother name.
    if (
        shared_phone
        and (
            father_match
            or mother_match
        )
    ):
        return True

    # Both parent names exactly match.
    if (
        father_match
        and mother_match
    ):
        return True

    return False


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 75)
    print("ROSARY PARENT IMPORT - DRY RUN")
    print("=" * 75)

    # -----------------------------------------------------
    # READ ALL EXCEL RECORDS
    # -----------------------------------------------------

    all_records = (
        read_structured_files()
        + read_class_files()
    )

    # -----------------------------------------------------
    # GROUP BY ADMISSION NUMBER
    # -----------------------------------------------------

    admission_records = defaultdict(
        list
    )

    for raw_record in all_records:

        record = prepare_record(
            raw_record
        )

        admission_no = (
            record["admission_no"]
        )

        if not admission_no:
            continue

        admission_records[
            admission_no
        ].append(
            record
        )

    # -----------------------------------------------------
    # KEEP ONLY NON-CONFLICTING STUDENTS
    # -----------------------------------------------------

    student_records = []

    conflicts = []

    for (
        admission_no,
        records,
    ) in admission_records.items():

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

            conflicts.append(
                admission_no
            )

            continue

        # Prefer record with most parent data.
        chosen = max(
            records,
            key=lambda record: sum(
                bool(
                    record.get(field)
                )
                for field in [
                    "father_name",
                    "father_phone",
                    "mother_name",
                    "mother_phone",
                    "parent_email",
                    "address",
                    "city",
                    "state",
                    "pincode",
                ]
            ),
        )

        student_records.append(
            chosen
        )

    print()
    print(
        f"Usable student records       : "
        f"{len(student_records)}"
    )

    print(
        f"Conflicting admissions held  : "
        f"{len(conflicts)}"
    )

    # -----------------------------------------------------
    # GROUP SIBLINGS
    # -----------------------------------------------------

    union_find = UnionFind(
        len(student_records)
    )

    # Build indexes so we don't compare every row
    # against every other row.

    indexes = defaultdict(
        list
    )

    for index, record in enumerate(
        student_records
    ):

        identifiers = []

        if (
            record[
                "father_phone_valid"
            ]
            and
            record[
                "father_name_normalized"
            ]
        ):
            identifiers.append(
                (
                    "FATHER",
                    record[
                        "father_phone_valid"
                    ],
                    record[
                        "father_name_normalized"
                    ],
                )
            )

        if (
            record[
                "mother_phone_valid"
            ]
            and
            record[
                "mother_name_normalized"
            ]
        ):
            identifiers.append(
                (
                    "MOTHER",
                    record[
                        "mother_phone_valid"
                    ],
                    record[
                        "mother_name_normalized"
                    ],
                )
            )

        if (
            record[
                "parent_email_valid"
            ]
        ):
            identifiers.append(
                (
                    "EMAIL",
                    record[
                        "parent_email_valid"
                    ],
                )
            )

        if (
            record[
                "father_name_normalized"
            ]
            and
            record[
                "mother_name_normalized"
            ]
        ):
            identifiers.append(
                (
                    "PARENT_NAMES",
                    record[
                        "father_name_normalized"
                    ],
                    record[
                        "mother_name_normalized"
                    ],
                )
            )

        for identifier in identifiers:
            indexes[
                identifier
            ].append(
                index
            )

    for indexes_list in (
        indexes.values()
    ):

        if len(indexes_list) < 2:
            continue

        first_index = (
            indexes_list[0]
        )

        for second_index in (
            indexes_list[1:]
        ):

            first = student_records[
                first_index
            ]

            second = student_records[
                second_index
            ]

            if same_family(
                first,
                second,
            ):
                union_find.union(
                    first_index,
                    second_index,
                )

    # -----------------------------------------------------
    # BUILD FAMILY GROUPS
    # -----------------------------------------------------

    family_groups = defaultdict(
        list
    )

    for index, record in enumerate(
        student_records
    ):

        family_root = (
            union_find.find(
                index
            )
        )

        family_groups[
            family_root
        ].append(
            record
        )

    sibling_families = [
        records
        for records
        in family_groups.values()
        if len(records) > 1
    ]

    single_child_families = [
        records
        for records
        in family_groups.values()
        if len(records) == 1
    ]

    # -----------------------------------------------------
    # DATABASE CHECK
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

        found_students = 0
        missing_students = []

        for record in student_records:

            if (
                record["admission_no"]
                in student_by_admission
            ):
                found_students += 1

            else:
                missing_students.append(
                    record["admission_no"]
                )

        existing_parent_users = (
            db.query(User)
            .filter(
                User.role == "PARENT"
            )
            .count()
        )

        existing_profiles = (
            db.query(
                ParentProfile
            )
            .count()
        )

        existing_links = (
            db.query(
                ParentStudent
            )
            .count()
        )

        # -------------------------------------------------
        # EMAIL DUPLICATE CHECK
        # -------------------------------------------------

        email_family_map = defaultdict(
            set
        )

        for family_id, records in (
            family_groups.items()
        ):

            for record in records:

                email = record[
                    "parent_email_valid"
                ]

                if email:
                    email_family_map[
                        email
                    ].add(
                        family_id
                    )

        shared_emails = {
            email: family_ids
            for email, family_ids
            in email_family_map.items()
            if len(family_ids) > 1
        }

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------

        print()
        print("=" * 75)
        print("PARENT DRY-RUN RESULT")
        print("=" * 75)

        print(
            f"Students found in DB         : "
            f"{found_students}"
        )

        print(
            f"Students missing from DB     : "
            f"{len(missing_students)}"
        )

        print()
        print(
            f"Proposed parent accounts     : "
            f"{len(family_groups)}"
        )

        print(
            f"Single-child families        : "
            f"{len(single_child_families)}"
        )

        print(
            f"Sibling families             : "
            f"{len(sibling_families)}"
        )

        print(
            f"Proposed parent-child links  : "
            f"{len(student_records)}"
        )

        print()
        print(
            f"Shared emails across families: "
            f"{len(shared_emails)}"
        )

        print()
        print(
            f"Existing parent users        : "
            f"{existing_parent_users}"
        )

        print(
            f"Existing parent profiles     : "
            f"{existing_profiles}"
        )

        print(
            f"Existing parent-child links  : "
            f"{existing_links}"
        )

        print()
        print(
            "DATABASE CHANGES             : 0"
        )

        print(
            "MODE                         : DRY RUN ONLY"
        )

        # -------------------------------------------------
        # SIBLING SAMPLE
        # -------------------------------------------------

        print()
        print("=" * 75)
        print("FIRST 10 SIBLING FAMILIES")
        print("=" * 75)

        for records in (
            sibling_families[:10]
        ):

            admissions = [
                record[
                    "admission_no"
                ]
                for record in records
            ]

            names = [
                record[
                    "student_name"
                ]
                for record in records
            ]

            print()

            print(
                "Admission Nos : "
                + ", ".join(
                    admissions
                )
            )

            print(
                "Students      : "
                + ", ".join(
                    str(name)
                    for name in names
                )
            )

            print(
                "Father        : "
                f"{records[0].get('father_name')}"
            )

            print(
                "Mother        : "
                f"{records[0].get('mother_name')}"
            )

        # -------------------------------------------------
        # SHARED EMAIL WARNINGS
        # -------------------------------------------------

        if shared_emails:

            print()
            print("=" * 75)
            print(
                "EMAILS USED BY MULTIPLE "
                "PARENT GROUPS"
            )
            print("=" * 75)

            for email in sorted(
                shared_emails
            ):
                print()
                print(
                    f"EMAIL: {email}"
                )

                family_ids = (
                    shared_emails[email]
                )

                for family_id in family_ids:

                    records = (
                        family_groups[
                            family_id
                        ]
                    )

                    for record in records:

                        print(
                            f"  Admission No : "
                            f"{record['admission_no']}"
                        )

                        print(
                            f"  Student      : "
                            f"{record['student_name']}"
                        )

                        print(
                            f"  Father       : "
                            f"{record.get('father_name')}"
                        )

                        print(
                            f"  Mother       : "
                            f"{record.get('mother_name')}"
                        )

                        print(
                            f"  Father Phone : "
                            f"{record.get('father_phone')}"
                        )

                        print(
                            f"  Mother Phone : "
                            f"{record.get('mother_phone')}"
                        )

                        print(
                            "  --------------------------"
                        )

    finally:
        db.close()


if __name__ == "__main__":
    main()