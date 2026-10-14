from pathlib import Path
import sys
import re

import pandas as pd
from sqlalchemy import func


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# PROJECT IMPORTS
# ============================================================

from app.database import SessionLocal
from app.models.user import User
from app.models.teacher_profile import TeacherProfile
from app.models.teacher_class import TeacherClass
from app.models.school_class import SchoolClass


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "input" / "Teacher_details.xlsx"


# ============================================================
# EXPECTED EXCEL COLUMNS
# ============================================================

COL_EMPLOYEE_ID = "Teacher ID / Employee ID"
COL_NAME = "First Name"
COL_EMAIL = "Email"
COL_MOBILE = "Mobile"
COL_QUALIFICATION = "Qualification"
COL_SUBJECT = "Specialization / Subject"
COL_DESIGNATION = "Designation"
COL_ACADEMIC_YEAR = "Academic Year"
COL_MAPPING = "Class & Section Mapping"


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value):
    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.lower() in {
        "nan",
        "none",
        "null",
    }:
        return ""

    return value


def normalize_header(value):
    """
    Normalize Excel headers so hidden spaces / line breaks
    don't break matching.
    """

    value = str(value)

    value = value.replace("\n", " ")
    value = value.replace("\r", " ")
    value = value.replace("\t", " ")

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_employee_id(value):
    value = clean(value)

    if value.endswith(".0"):
        value = value[:-2]

    return value.strip()


def normalize_email(value):
    return clean(value).lower()


def normalize_phone(value):
    value = clean(value)

    if value.endswith(".0"):
        value = value[:-2]

    value = re.sub(
        r"\s+",
        "",
        value,
    )

    return value


def normalize_grade(value):
    value = clean(value).upper()

    value = value.replace(
        "STANDARD",
        "",
    )

    value = value.replace(
        "STD.",
        "",
    )

    value = value.replace(
        "STD",
        "",
    )

    value = value.replace(
        "CLASS",
        "",
    )

    value = value.strip(" -")

    value = re.sub(
        r"\s+",
        "",
        value,
    )

    return value


def normalize_section(value):
    value = clean(value).upper()

    value = value.strip(" -")

    value = re.sub(
        r"\s+",
        "",
        value,
    )

    return value


def class_key(name, section):
    return (
        normalize_grade(name),
        normalize_section(section),
    )


# ============================================================
# COLUMN RESOLUTION
# ============================================================

def find_column(df, possible_names):
    """
    Find a column using normalized header matching.
    """

    normalized_columns = {
        normalize_header(col).lower(): col
        for col in df.columns
    }

    for name in possible_names:
        normalized_name = normalize_header(
            name
        ).lower()

        if normalized_name in normalized_columns:
            return normalized_columns[
                normalized_name
            ]

    return None


# ============================================================
# VALID GRADES
# ============================================================

VALID_GRADES = {
    "LKG",
    "UKG",
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
    "XI",
    "XII",
}


# ============================================================
# NON-CLASS STAFF
# ============================================================

NON_CLASS_VALUES = {
    "PRINCIPAL",
    "RECORD CLERK",
    "JUNIOR ASSISTANT",
    "JUNIOR ASST",
    "JUNIOR ASST.",
    "LIBRARIAN",
    "OFFICE",
    "SCAVENGER",
    "BIOLOGY LAB ASSISTANT",
    "BIOLOGY LAB ASST",
    "BIOLOGY LAB ASST.",
}


def is_non_class_mapping(value):
    value = clean(value).upper()

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value in NON_CLASS_VALUES


# ============================================================
# CLASS / SECTION PARSER
# ============================================================

def parse_mapping(raw_value, class_lookup):
    raw = clean(raw_value).upper()

    if not raw:
        return [], ["EMPTY MAPPING"]

    # Remove subject notes inside brackets
    raw = re.sub(r"\([^)]*\)", "", raw)

    # Handle broken/open bracket text like:
    # III-B (MATHS & SOCIAL SCIENCE
    raw = re.sub(r"\(.*$", "", raw)

    # Normalize text
    raw = raw.replace("STANDARD", "")
    raw = raw.replace("STD.", "")
    raw = raw.replace("STD", "")

    raw = raw.replace("–", "-")
    raw = raw.replace("—", "-")
    raw = raw.replace(";", ",")
    raw = raw.replace("/", ",")

    # Fix cases like:
    # X-C IX-B
    grade_pattern = r"(LKG|UKG|XII|XI|VIII|VII|VI|IX|IV|III|II|X|V|I)"

    raw = re.sub(
        rf"([A-Z0-9])\s+(?={grade_pattern}\s*[- ]\s*[A-Z])",
        r"\1, ",
        raw,
    )

    mappings = []
    errors = []

    # --------------------------------------------------------
    # Grade ranges:
    # I - IV
    # I - VIII
    # --------------------------------------------------------

    grade_order = [
        "LKG",
        "UKG",
        "I",
        "II",
        "III",
        "IV",
        "V",
        "VI",
        "VII",
        "VIII",
        "IX",
        "X",
        "XI",
        "XII",
    ]

    range_match = re.fullmatch(
         rf"\s*{grade_pattern}\s*-\s*{grade_pattern}\s*",
        raw,
    )

    if range_match:
        start_grade = range_match.group(1)
        end_grade = range_match.group(2)

        try:
            start_index = grade_order.index(start_grade)
            end_index = grade_order.index(end_grade)

            for grade in grade_order[start_index:end_index + 1]:

                sections = sorted(
                    {
                        section
                        for g, section in class_lookup.keys()
                        if g == grade
                    }
                )

                for section in sections:
                    mappings.append((grade, section))

            return list(dict.fromkeys(mappings)), []

        except ValueError:
            return [], [f"INVALID RANGE: {raw}"]

    # --------------------------------------------------------
    # Grade-only list:
    # I, II, III, IV
    # --------------------------------------------------------

    raw_without_amp = raw.replace("&", ",")

    parts = [
        part.strip()
        for part in raw_without_amp.split(",")
        if part.strip()
    ]

    grade_only_parts = [
        normalize_grade(part)
        for part in parts
    ]

    if (
        grade_only_parts
        and all(
            grade in VALID_GRADES
            for grade in grade_only_parts
        )
    ):
        for grade in grade_only_parts:

            sections = sorted(
                {
                    section
                    for g, section in class_lookup.keys()
                    if g == grade
                }
            )

            for section in sections:
                mappings.append(
                    (
                        grade,
                        section,
                    )
                )

        return list(dict.fromkeys(mappings)), []

    # --------------------------------------------------------
    # Normal mapping
    # --------------------------------------------------------

    raw = raw.replace("&", ",")

    parts = [
        part.strip()
        for part in raw.split(",")
        if part.strip()
    ]

    current_grade = None

    for part in parts:

        part = re.sub(
            r"\s+",
            " ",
            part,
        ).strip()

        part = part.strip("- ")

        # ----------------------------------------------------
        # VI-A
        # VI A
        # XII-C1
        # XI-A1
        # ----------------------------------------------------

        match = re.fullmatch(
            rf"{grade_pattern}\s*[- ]\s*([A-Z][0-9]*)",
            part,
        )

        if match:
            grade = normalize_grade(
                match.group(1)
            )

            section = normalize_section(
                match.group(2)
            )

            current_grade = grade

            mappings.append(
                (
                    grade,
                    section,
                )
            )

            continue

        # ----------------------------------------------------
        # VIA
        # XII C1 handled above
        # ----------------------------------------------------

        match = re.fullmatch(
            rf"{grade_pattern}([A-Z][0-9]*)",
            part,
        )

        if match:
            grade = normalize_grade(
                match.group(1)
            )

            section = normalize_section(
                match.group(2)
            )

            current_grade = grade

            mappings.append(
                (
                    grade,
                    section,
                )
            )

            continue

        # ----------------------------------------------------
        # Inherit previous grade:
        #
        # XII-C, C1
        # XI-C, C1
        # VI-A, B, C
        # ----------------------------------------------------

        if re.fullmatch(
            r"[A-Z][0-9]*",
            part,
        ):
            if current_grade:

                mappings.append(
                    (
                        current_grade,
                        normalize_section(part),
                    )
                )

                continue

            errors.append(
                f"SECTION WITHOUT CLASS: {part}"
            )

            continue

        errors.append(
            f"UNRECOGNIZED: {part}"
        )

    mappings = list(
        dict.fromkeys(
            mappings
        )
    )

    return mappings, errors

# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 75)
    print(
        "ROSARY REAL TEACHER IMPORT - DRY RUN"
    )
    print("=" * 75)

    # --------------------------------------------------------
    # FILE CHECK
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        print()
        print(
            "ERROR: Teacher Excel file not found"
        )

        print(
            INPUT_FILE
        )

        return

    print()
    print(
        "Excel file:"
    )

    print(
        INPUT_FILE
    )

    # --------------------------------------------------------
    # LOAD EXCEL
    # --------------------------------------------------------

    try:
        df = pd.read_excel(
            INPUT_FILE
        )

    except Exception as exc:
        print()
        print(
            "ERROR: Unable to read teacher Excel"
        )

        print(
            exc
        )

        return

    # --------------------------------------------------------
    # NORMALIZE HEADERS
    # --------------------------------------------------------

    df.columns = [
        normalize_header(
            col
        )
        for col in df.columns
    ]

    df = (
        df
        .dropna(
            how="all"
        )
        .reset_index(
            drop=True
        )
    )

    print()
    print(
        f"Teacher Excel rows       : {len(df)}"
    )

    # --------------------------------------------------------
    # DEBUG: SHOW HEADERS
    # --------------------------------------------------------

    print()
    print("=" * 75)
    print(
        "EXCEL COLUMNS DETECTED"
    )
    print("=" * 75)

    for col in df.columns:
        print(
            f"  - [{col}]"
        )

    # --------------------------------------------------------
    # RESOLVE COLUMNS
    # --------------------------------------------------------

    employee_id_col = find_column(
        df,
        [
            "Teacher ID / Employee ID",
            "Teacher ID",
            "Employee ID",
        ],
    )

    name_col = find_column(
        df,
        [
            "First Name",
            "Teacher Name",
            "Name",
        ],
    )

    email_col = find_column(
        df,
        [
            "Email",
            "Email ID",
            "Email Address",
        ],
    )

    mobile_col = find_column(
        df,
        [
            "Mobile",
            "Mobile Number",
            "Phone",
            "Phone Number",
        ],
    )

    qualification_col = find_column(
        df,
        [
            "Qualification",
        ],
    )

    subject_col = find_column(
        df,
        [
            "Specialization / Subject",
            "Subject",
            "Specialization",
        ],
    )

    designation_col = find_column(
        df,
        [
            "Designation",
            "Role",
        ],
    )

    academic_year_col = find_column(
        df,
        [
            "Academic Year",
        ],
    )

    mapping_col = find_column(
        df,
        [
            "Class & Section Mapping",
            "Class and Section Mapping",
            "Class Section Mapping",
            "Class & Section",
        ],
    )

    # --------------------------------------------------------
    # SHOW RESOLVED COLUMNS
    # --------------------------------------------------------

    print()
    print("=" * 75)
    print(
        "COLUMN RESOLUTION"
    )
    print("=" * 75)

    resolved_columns = {
        "employee_id": employee_id_col,
        "name": name_col,
        "email": email_col,
        "mobile": mobile_col,
        "qualification": qualification_col,
        "subject": subject_col,
        "designation": designation_col,
        "academic_year": academic_year_col,
        "mapping": mapping_col,
    }

    for key, value in resolved_columns.items():

        if value:
            print(
                f"OK  {key:<15} -> {value}"
            )

        else:
            print(
                f"NO  {key:<15} -> NOT FOUND"
            )

    # --------------------------------------------------------
    # REQUIRED COLUMNS
    # --------------------------------------------------------

    required_columns = {
        "employee_id": employee_id_col,
        "name": name_col,
        "email": email_col,
        "mobile": mobile_col,
        "subject": subject_col,
        "designation": designation_col,
        "mapping": mapping_col,
    }

    missing_required = [
        key
        for key, value
        in required_columns.items()
        if not value
    ]

    if missing_required:
        print()
        print(
            "ERROR: Missing required Excel columns"
        )

        for key in missing_required:
            print(
                f"  - {key}"
            )

        return

    # --------------------------------------------------------
    # DB CONNECTION
    # --------------------------------------------------------

    db = SessionLocal()

    try:

        # ====================================================
        # LOAD ACTIVE SCHOOL CLASSES
        # ====================================================

        db_classes = (
            db.query(
                SchoolClass
            )
            .filter(
                SchoolClass.is_active.is_(
                    True
                )
            )
            .all()
        )

        class_lookup = {}

        duplicate_class_keys = []

        for school_class in db_classes:

            key = class_key(
                school_class.name,
                school_class.section,
            )

            if key in class_lookup:
                duplicate_class_keys.append(
                    key
                )

            class_lookup[
                key
            ] = school_class

        # ====================================================
        # EXISTING TEACHER USERS
        # ====================================================

        existing_teacher_users = {
            str(
                user.username
            ).strip(): user

            for user in (
                db.query(
                    User
                )
                .filter(
                    func.lower(
                        User.role
                    ) == "teacher"
                )
                .all()
            )
        }

        # ====================================================
        # EXISTING PROFILES
        # ====================================================

        existing_profiles = {
            str(
                profile.employee_id
            ).strip(): profile

            for profile in (
                db.query(
                    TeacherProfile
                )
                .all()
            )
        }

        # ====================================================
        # EXISTING CLASS MAPPINGS
        # ====================================================

        existing_teacher_classes = (
            db.query(
                TeacherClass
            )
            .all()
        )

        existing_mapping_keys = {
            (
                item.teacher_user_id,
                item.class_id,
                clean(
                    item.subject
                ).lower(),
            )

            for item
            in existing_teacher_classes
        }

        # ====================================================
        # COUNTERS
        # ====================================================

        users_to_create = 0
        users_existing = 0

        profiles_to_create = 0
        profiles_existing = 0

        mappings_found = 0
        mappings_existing = 0
        mappings_to_create = 0

        skipped_staff = 0

        unmatched = []
        parse_errors = []

        ready_teachers = []

        # ====================================================
        # PROCESS EACH TEACHER
        # ====================================================

        for index, row in df.iterrows():

            excel_row = index + 2

            employee_id = normalize_employee_id(
                row[
                    employee_id_col
                ]
            )

            name = clean(
                row[
                    name_col
                ]
            )

            email = normalize_email(
                row[
                    email_col
                ]
            )

            mobile = normalize_phone(
                row[
                    mobile_col
                ]
            )

            qualification = ""

            if qualification_col:
                qualification = clean(
                    row[
                        qualification_col
                    ]
                )

            subject = clean(
                row[
                    subject_col
                ]
            )

            designation = clean(
                row[
                    designation_col
                ]
            )

            academic_year = ""

            if academic_year_col:
                academic_year = clean(
                    row[
                        academic_year_col
                    ]
                )

            raw_mapping = clean(
                row[
                    mapping_col
                ]
            )

            # -----------------------------------------------
            # USER CHECK
            # -----------------------------------------------

            existing_user = (
                existing_teacher_users.get(
                    employee_id
                )
            )

            if existing_user:
                users_existing += 1

            else:
                users_to_create += 1

            # -----------------------------------------------
            # PROFILE CHECK
            # -----------------------------------------------

            existing_profile = (
                existing_profiles.get(
                    employee_id
                )
            )

            if existing_profile:
                profiles_existing += 1

            else:
                profiles_to_create += 1

            # -----------------------------------------------
            # NON-CLASS STAFF
            # -----------------------------------------------

            if is_non_class_mapping(
                raw_mapping
            ):

                skipped_staff += 1

                ready_teachers.append(
                    {
                        "employee_id": employee_id,
                        "name": name,
                        "mapping": raw_mapping,
                        "status":
                            "STAFF - NO CLASS MAPPING",
                    }
                )

                continue

            # -----------------------------------------------
            # PARSE MAPPING
            # -----------------------------------------------

            parsed_mappings, errors = (
                parse_mapping(
                    raw_mapping,
                    class_lookup,
                )
            )

            if errors:

                for error in errors:

                    parse_errors.append(
                        {
                            "row": excel_row,
                            "employee_id": employee_id,
                            "name": name,
                            "raw_mapping": raw_mapping,
                            "error": error,
                        }
                    )

            # -----------------------------------------------
            # MATCH CLASS / SECTION
            # -----------------------------------------------

            teacher_mapping_count = 0

            for grade, section in parsed_mappings:

                key = class_key(
                    grade,
                    section,
                )

                school_class = (
                    class_lookup.get(
                        key
                    )
                )

                if not school_class:

                    unmatched.append(
                        {
                            "row": excel_row,
                            "employee_id": employee_id,
                            "name": name,
                            "subject": subject,
                            "raw_mapping": raw_mapping,
                            "grade": grade,
                            "section": section,
                        }
                    )

                    continue

                mappings_found += 1
                teacher_mapping_count += 1

                # Teacher does not exist yet.
                # Therefore mapping will be created
                # after user creation.
                if not existing_user:

                    mappings_to_create += 1

                    continue

                mapping_key = (
                    existing_user.id,
                    school_class.id,
                    subject.lower(),
                )

                if (
                    mapping_key
                    in existing_mapping_keys
                ):

                    mappings_existing += 1

                else:

                    mappings_to_create += 1

            ready_teachers.append(
                {
                    "employee_id": employee_id,
                    "name": name,
                    "email": email,
                    "mobile": mobile,
                    "qualification": qualification,
                    "subject": subject,
                    "designation": designation,
                    "academic_year": academic_year,
                    "mapping": raw_mapping,
                    "resolved":
                        teacher_mapping_count,
                }
            )

        # ====================================================
        # SUMMARY
        # ====================================================

        print()
        print("=" * 75)
        print(
            "DATABASE DRY-RUN RESULT"
        )
        print("=" * 75)

        print()

        print(
            f"Existing DB teacher users : "
            f"{len(existing_teacher_users)}"
        )

        print(
            f"Existing teacher profiles : "
            f"{len(existing_profiles)}"
        )

        print(
            f"Existing teacher mappings : "
            f"{len(existing_teacher_classes)}"
        )

        print()

        print(
            f"Users to create            : "
            f"{users_to_create}"
        )

        print(
            f"Users already existing     : "
            f"{users_existing}"
        )

        print(
            f"Profiles to create         : "
            f"{profiles_to_create}"
        )

        print(
            f"Profiles already existing  : "
            f"{profiles_existing}"
        )

        print()

        print(
            f"Valid class mappings found : "
            f"{mappings_found}"
        )

        print(
            f"Mappings already existing  : "
            f"{mappings_existing}"
        )

        print(
            f"Mappings to create         : "
            f"{mappings_to_create}"
        )

        print(
            f"Skipped non-class staff    : "
            f"{skipped_staff}"
        )

        print(
            f"Unmatched class mappings   : "
            f"{len(unmatched)}"
        )

        print(
            f"Mapping parse warnings     : "
            f"{len(parse_errors)}"
        )

        print(
            f"Duplicate DB class keys    : "
            f"{len(set(duplicate_class_keys))}"
        )

        # ====================================================
        # UNMATCHED
        # ====================================================

        if unmatched:

            print()
            print("=" * 75)
            print(
                "UNMATCHED CLASS / SECTION MAPPINGS"
            )
            print("=" * 75)

            for item in unmatched:

                print()

                print(
                    f"Excel Row    : "
                    f"{item['row']}"
                )

                print(
                    f"Employee ID  : "
                    f"{item['employee_id']}"
                )

                print(
                    f"Teacher      : "
                    f"{item['name']}"
                )

                print(
                    f"Subject      : "
                    f"{item['subject']}"
                )

                print(
                    f"Raw Mapping  : "
                    f"{item['raw_mapping']}"
                )

                print(
                    f"Parsed       : "
                    f"{item['grade']}-"
                    f"{item['section']}"
                )

        # ====================================================
        # PARSE WARNINGS
        # ====================================================

        if parse_errors:

            print()
            print("=" * 75)
            print(
                "MAPPING PARSE WARNINGS"
            )
            print("=" * 75)

            for item in parse_errors:

                print()

                print(
                    f"Excel Row    : "
                    f"{item['row']}"
                )

                print(
                    f"Employee ID  : "
                    f"{item['employee_id']}"
                )

                print(
                    f"Teacher      : "
                    f"{item['name']}"
                )

                print(
                    f"Raw Mapping  : "
                    f"{item['raw_mapping']}"
                )

                print(
                    f"Problem      : "
                    f"{item['error']}"
                )

        # ====================================================
        # FIRST 10
        # ====================================================

        print()
        print("=" * 75)
        print(
            "FIRST 10 TEACHERS"
        )
        print("=" * 75)

        for teacher in ready_teachers[:10]:

            print()

            print(
                f"{teacher['employee_id']} | "
                f"{teacher['name']}"
            )

            print(
                f"Mapping: "
                f"{teacher['mapping']}"
            )

            if "resolved" in teacher:

                print(
                    f"Resolved mappings: "
                    f"{teacher['resolved']}"
                )

            else:

                print(
                    f"Status: "
                    f"{teacher['status']}"
                )

        # ====================================================
        # FINAL
        # ====================================================

        print()
        print("=" * 75)

        if (
            len(unmatched) == 0
            and len(parse_errors) == 0
            and len(
                set(
                    duplicate_class_keys
                )
            ) == 0
        ):

            print(
                "TEACHER DRY RUN PASSED"
            )

            print()

            print(
                f"READY USERS              : "
                f"{users_to_create}"
            )

            print(
                f"READY PROFILES           : "
                f"{profiles_to_create}"
            )

            print(
                f"READY CLASS MAPPINGS     : "
                f"{mappings_to_create}"
            )

            print()

            print(
                "DATABASE CHANGES          : 0"
            )

            print(
                "MODE                      : "
                "DRY RUN ONLY"
            )

        else:

            print(
                "TEACHER DRY RUN NEEDS REVIEW"
            )

            print()

            print(
                "Do not run the real import "
                "until all mapping issues "
                "are resolved."
            )

            print()

            print(
                "DATABASE CHANGES          : 0"
            )

        print("=" * 75)

    except Exception as exc:

        print()
        print("=" * 75)
        print(
            "DRY RUN ERROR"
        )
        print("=" * 75)

        print()

        print(
            type(exc).__name__
        )

        print(
            exc
        )

        print()

        print(
            "DATABASE CHANGES: 0"
        )

    finally:

        db.close()


if __name__ == "__main__":
    main()