from pathlib import Path
import sys
import re
from datetime import datetime

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
from app.core.security import hash_password


# ============================================================
# SETTINGS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "input" / "Teacher_details.xlsx"

ACADEMIC_YEAR = "2026-2027"

# Initial teacher login password
DEFAULT_PASSWORD = "Rosary@123"


# ============================================================
# HELPERS
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


def find_column(df, possible_names):
    normalized = {
        normalize_header(col).lower(): col
        for col in df.columns
    }

    for name in possible_names:
        key = normalize_header(
            name
        ).lower()

        if key in normalized:
            return normalized[key]

    return None


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

    return re.sub(
        r"\s+",
        "",
        value,
    )


def parse_date(value):
    if pd.isna(value):
        return None

    if isinstance(value, datetime):
        return value.date()

    try:
        parsed = pd.to_datetime(
            value,
            dayfirst=True,
            errors="coerce",
        )

        if pd.isna(parsed):
            return None

        return parsed.date()

    except Exception:
        return None


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


GRADE_ORDER = [
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
# MAPPING PARSER
# ============================================================

def parse_mapping(raw_value, class_lookup):
    raw = clean(raw_value).upper()

    if not raw:
        return [], [
            "EMPTY MAPPING"
        ]

    # Remove subject notes
    raw = re.sub(
        r"\([^)]*\)",
        "",
        raw,
    )

    raw = re.sub(
        r"\(.*$",
        "",
        raw,
    )

    raw = raw.replace(
        "STANDARD",
        "",
    )

    raw = raw.replace(
        "STD.",
        "",
    )

    raw = raw.replace(
        "STD",
        "",
    )

    raw = raw.replace(
        "–",
        "-",
    )

    raw = raw.replace(
        "—",
        "-",
    )

    raw = raw.replace(
        ";",
        ",",
    )

    raw = raw.replace(
        "/",
        ",",
    )

    grade_pattern = (
        r"(LKG|UKG|XII|XI|VIII|VII|VI|IX|IV|III|II|X|V|I)"
    )

    # Fix cases like:
    # X-C STD IX-B
    raw = re.sub(
        rf"([A-Z0-9])\s+(?={grade_pattern}\s*[- ]\s*[A-Z])",
        r"\1, ",
        raw,
    )

    mappings = []
    errors = []

    # ========================================================
    # GRADE RANGE
    # ========================================================

    range_match = re.fullmatch(
        rf"\s*{grade_pattern}\s*-\s*{grade_pattern}\s*",
        raw,
    )

    if range_match:

        start_grade = range_match.group(1)
        end_grade = range_match.group(2)

        try:
            start_index = GRADE_ORDER.index(
                start_grade
            )

            end_index = GRADE_ORDER.index(
                end_grade
            )

        except ValueError:
            return [], [
                f"INVALID RANGE: {raw}"
            ]

        grades = GRADE_ORDER[
            start_index:
            end_index + 1
        ]

        for grade in grades:

            sections = sorted(
                {
                    section
                    for g, section
                    in class_lookup.keys()
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

        return (
            list(
                dict.fromkeys(
                    mappings
                )
            ),
            [],
        )

    # ========================================================
    # NORMALIZE &
    # ========================================================

    raw = raw.replace(
        "&",
        ",",
    )

    parts = [
        part.strip()
        for part in raw.split(",")
        if part.strip()
    ]

    # ========================================================
    # GRADE ONLY LIST
    #
    # I, II, III, IV
    # ========================================================

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
                    for g, section
                    in class_lookup.keys()
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

        return (
            list(
                dict.fromkeys(
                    mappings
                )
            ),
            [],
        )

    # ========================================================
    # CLASS + SECTION
    # ========================================================

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
        # C
        # C1
        # B
        #
        # inherit previous class
        # ----------------------------------------------------

        if re.fullmatch(
            r"[A-Z][0-9]*",
            part,
        ):

            if current_grade:

                mappings.append(
                    (
                        current_grade,
                        normalize_section(
                            part
                        ),
                    )
                )

                continue

        errors.append(
            f"UNRECOGNIZED: {part}"
        )

    return (
        list(
            dict.fromkeys(
                mappings
            )
        ),
        errors,
    )


# ============================================================
# MAIN IMPORT
# ============================================================

def main():

    print("=" * 75)
    print(
        "ROSARY REAL TEACHER IMPORT"
    )
    print("=" * 75)

    if not INPUT_FILE.exists():

        print(
            "Teacher Excel file not found:"
        )

        print(
            INPUT_FILE
        )

        return

    # ========================================================
    # READ EXCEL
    # ========================================================

    df = pd.read_excel(
        INPUT_FILE
    )

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

    # ========================================================
    # COLUMNS
    # ========================================================

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

    dob_col = find_column(
        df,
        [
            "Date of Birth",
            "DOB",
        ],
    )

    gender_col = find_column(
        df,
        [
            "Gender",
        ],
    )

    email_col = find_column(
        df,
        [
            "Email",
        ],
    )

    mobile_col = find_column(
        df,
        [
            "Mobile",
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
        ],
    )

    designation_col = find_column(
        df,
        [
            "Designation",
        ],
    )

    joining_date_col = find_column(
        df,
        [
            "Joining Date",
        ],
    )

    mapping_col = find_column(
        df,
        [
            "Class & Section Mapping",
            "Class and Section Mapping",
        ],
    )

    # ========================================================
    # DATABASE
    # ========================================================

    db = SessionLocal()

    users_created = 0
    users_updated = 0

    profiles_created = 0
    profiles_updated = 0

    mappings_created = 0
    mappings_existing = 0

    skipped_staff = 0

    try:

        # ====================================================
        # CLASS LOOKUP
        # ====================================================

        school_classes = (
            db.query(
                SchoolClass
            )
            .filter(
                SchoolClass.is_active.is_(
                    True
                ),
                SchoolClass.academic_year
                == ACADEMIC_YEAR,
            )
            .all()
        )

        class_lookup = {
            class_key(
                item.name,
                item.section,
            ): item
            for item in school_classes
        }

        # ====================================================
        # PROCESS TEACHERS
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

            phone = normalize_phone(
                row[
                    mobile_col
                ]
            )

            date_of_birth = (
                parse_date(
                    row[
                        dob_col
                    ]
                )
                if dob_col
                else None
            )

            gender = (
                clean(
                    row[
                        gender_col
                    ]
                )
                if gender_col
                else None
            )

            qualification = (
                clean(
                    row[
                        qualification_col
                    ]
                )
                if qualification_col
                else None
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

            joining_date = (
                parse_date(
                    row[
                        joining_date_col
                    ]
                )
                if joining_date_col
                else None
            )

            raw_mapping = clean(
                row[
                    mapping_col
                ]
            )

            print()
            print(
                f"[{excel_row}] "
                f"{employee_id} | {name}"
            )

            # =================================================
            # USER
            # =================================================

            user = (
                db.query(
                    User
                )
                .filter(
                    User.username
                    == employee_id
                )
                .first()
            )

            if not user:

                # Check email uniqueness before insert
                email_owner = None

                if email:

                    email_owner = (
                        db.query(
                            User
                        )
                        .filter(
                            func.lower(
                                User.email
                            )
                            == email.lower()
                        )
                        .first()
                    )

                if email_owner:
                    print(
                        f"  EMAIL CONFLICT: {email} "
                        f"already used by {email_owner.role} "
                        f"({email_owner.username})"
                    )
                    email = None

                user = User(
                    name=name,
                    username=employee_id,
                    email=email or None,
                    password_hash=hash_password(
                        DEFAULT_PASSWORD
                    ),
                    role="teacher",
                    is_active=True,
                )

                db.add(
                    user
                )

                db.flush()

                users_created += 1

                print(
                    "  USER CREATED"
                )

            else:

                user.name = name

                if email:

                    email_owner = (
                        db.query(
                            User
                        )
                        .filter(
                            func.lower(
                                User.email
                            )
                            == email.lower(),
                            User.id != user.id,
                        )
                        .first()
                    )

                    if email_owner:

                        raise ValueError(
                            f"Email already belongs "
                            f"to another user: {email}"
                        )

                    user.email = email

                user.role = "teacher"
                user.is_active = True

                users_updated += 1

                print(
                    "  USER UPDATED"
                )

            # =================================================
            # TEACHER PROFILE
            # =================================================

            profile = (
                db.query(
                    TeacherProfile
                )
                .filter(
                    TeacherProfile.employee_id
                    == employee_id
                )
                .first()
            )

            if not profile:

                profile = TeacherProfile(
                    user_id=user.id,
                    employee_id=employee_id,
                    date_of_birth=date_of_birth,
                    gender=gender or None,
                    phone=phone or None,
                    designation=designation or None,
                    department=None,
                    qualification=qualification or None,
                    specialization=subject or None,
                    joining_date=joining_date,
                )

                db.add(
                    profile
                )

                profiles_created += 1

                print(
                    "  PROFILE CREATED"
                )

            else:

                profile.user_id = user.id
                profile.date_of_birth = date_of_birth
                profile.gender = gender or None
                profile.phone = phone or None
                profile.designation = designation or None
                profile.qualification = qualification or None
                profile.specialization = subject or None
                profile.joining_date = joining_date

                profiles_updated += 1

                print(
                    "  PROFILE UPDATED"
                )

            # =================================================
            # STAFF WITHOUT CLASS
            # =================================================

            if is_non_class_mapping(
                raw_mapping
            ):

                skipped_staff += 1

                print(
                    "  CLASS MAPPING SKIPPED"
                )

                continue

            # =================================================
            # PARSE MAPPING
            # =================================================

            parsed_mappings, errors = (
                parse_mapping(
                    raw_mapping,
                    class_lookup,
                )
            )

            if errors:

                raise ValueError(
                    f"Mapping parser error for "
                    f"{employee_id}: {errors}"
                )

            # =================================================
            # CREATE CLASS MAPPINGS
            # =================================================

            for grade, section in parsed_mappings:

                school_class = (
                    class_lookup.get(
                        (
                            grade,
                            section,
                        )
                    )
                )

                if not school_class:

                    raise ValueError(
                        f"Class not found: "
                        f"{grade}-{section} "
                        f"for {employee_id}"
                    )

                existing_mapping = (
                    db.query(
                        TeacherClass
                    )
                    .filter(
                        TeacherClass.teacher_user_id
                        == user.id,
                        TeacherClass.class_id
                        == school_class.id,
                        TeacherClass.subject
                        == subject,
                    )
                    .first()
                )

                if existing_mapping:

                    mappings_existing += 1

                    continue

                mapping = TeacherClass(
                    teacher_user_id=user.id,
                    class_id=school_class.id,
                    subject=subject or None,
                    is_class_teacher=False,
                )

                db.add(
                    mapping
                )

                mappings_created += 1

        # ====================================================
        # COMMIT ALL
        # ====================================================

        db.commit()

        print()
        print("=" * 75)
        print(
            "TEACHER IMPORT COMPLETED"
        )
        print("=" * 75)

        print(
            f"Excel rows               : "
            f"{len(df)}"
        )

        print(
            f"Users created            : "
            f"{users_created}"
        )

        print(
            f"Users updated            : "
            f"{users_updated}"
        )

        print(
            f"Profiles created         : "
            f"{profiles_created}"
        )

        print(
            f"Profiles updated         : "
            f"{profiles_updated}"
        )

        print(
            f"Class mappings created   : "
            f"{mappings_created}"
        )

        print(
            f"Mappings already existed : "
            f"{mappings_existing}"
        )

        print(
            f"Staff mappings skipped   : "
            f"{skipped_staff}"
        )

        print()
        print(
            "DATABASE CHANGES         : COMMITTED"
        )

        print("=" * 75)

    except Exception as exc:

        db.rollback()

        print()
        print("=" * 75)
        print(
            "TEACHER IMPORT FAILED"
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
            "DATABASE CHANGES         : ROLLED BACK"
        )

        print("=" * 75)

    finally:

        db.close()


if __name__ == "__main__":
    main()