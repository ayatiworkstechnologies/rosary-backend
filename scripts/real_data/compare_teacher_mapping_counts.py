from pathlib import Path
import sys
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal
from app.models.teacher_profile import TeacherProfile
from app.models.teacher_class import TeacherClass
from app.models.school_class import SchoolClass

from scripts.real_data.dry_run_teachers import (
    clean,
    normalize_employee_id,
    class_key,
    parse_mapping,
    is_non_class_mapping,
)


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "input" / "Teacher_details.xlsx"

EMPLOYEE_COL = "Teacher ID / Employee ID"
NAME_COL = "First Name"
MAPPING_COL = "Class & Section Mapping"


def main():
    df = pd.read_excel(INPUT_FILE)
    df.columns = [
        str(col)
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
        .strip()
        for col in df.columns
    ]

    df = df.dropna(how="all").reset_index(drop=True)

    db = SessionLocal()

    try:
        classes = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.is_active.is_(True),
                SchoolClass.academic_year == "2026-2027",
            )
            .all()
        )

        class_lookup = {
            class_key(c.name, c.section): c
            for c in classes
        }

        total_expected = 0
        total_actual = 0

        print("=" * 75)
        print("TEACHER MAPPING COUNT COMPARISON")
        print("=" * 75)

        for _, row in df.iterrows():
            employee_id = normalize_employee_id(
                row[EMPLOYEE_COL]
            )

            name = clean(
                row[NAME_COL]
            )

            raw_mapping = clean(
                row[MAPPING_COL]
            )

            if is_non_class_mapping(raw_mapping):
                expected = 0
            else:
                parsed, errors = parse_mapping(
                    raw_mapping,
                    class_lookup,
                )

                if errors:
                    print(
                        f"PARSE ERROR: {employee_id} | "
                        f"{name} | {errors}"
                    )
                    continue

                expected = len(parsed)

            profile = (
                db.query(TeacherProfile)
                .filter(
                    TeacherProfile.employee_id
                    == employee_id
                )
                .first()
            )

            if not profile:
                print(
                    f"PROFILE MISSING: "
                    f"{employee_id} | {name}"
                )
                continue

            actual = (
                db.query(TeacherClass)
                .filter(
                    TeacherClass.teacher_user_id
                    == profile.user_id
                )
                .count()
            )

            total_expected += expected
            total_actual += actual

            if expected != actual:
                print()
                print(
                    f"{employee_id} | {name}"
                )
                print(
                    f"Expected mappings : {expected}"
                )
                print(
                    f"Actual mappings   : {actual}"
                )
                print(
                    f"Difference        : {actual - expected}"
                )
                print(
                    f"Excel mapping     : {raw_mapping}"
                )

        print()
        print("=" * 75)
        print(
            f"TOTAL EXPECTED : {total_expected}"
        )
        print(
            f"TOTAL ACTUAL   : {total_actual}"
        )
        print(
            f"DIFFERENCE     : {total_actual - total_expected}"
        )
        print("=" * 75)

    finally:
        db.close()


if __name__ == "__main__":
    main()