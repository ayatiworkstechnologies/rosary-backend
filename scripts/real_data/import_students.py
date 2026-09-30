from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from app.database import SessionLocal
from app.models.school_class import SchoolClass
from app.models.student import Student

from dry_run_students import (
    clean_admission_no,
    clean_text,
    normalize_class_value,
    read_class_files,
    read_structured_files,
    resolve_students,
    validate_student,
)


def main():

    print("=" * 75)
    print("ROSARY REAL STUDENT IMPORT")
    print("=" * 75)

    # --------------------------------------------------
    # READ EXCEL DATA
    # --------------------------------------------------

    structured_records = (
        read_structured_files()
    )

    class_file_records = (
        read_class_files()
    )

    source_records = (
        structured_records
        + class_file_records
    )

    (
        resolved_students,
        same_student_duplicates,
        conflicts,
        missing_admission,
    ) = resolve_students(
        source_records
    )

    # --------------------------------------------------
    # VALIDATE
    # --------------------------------------------------

    valid_students = []
    invalid_students = []

    for record in resolved_students:

        errors = validate_student(
            record
        )

        if errors:
            invalid_students.append(
                (
                    record,
                    errors,
                )
            )
        else:
            valid_students.append(
                record
            )

    print()
    print(
        f"Source rows              : "
        f"{len(source_records)}"
    )

    print(
        f"Resolved students        : "
        f"{len(resolved_students)}"
    )

    print(
        f"Same-student duplicates  : "
        f"{len(same_student_duplicates)}"
    )

    print(
        f"Conflicting Admissions   : "
        f"{len(conflicts)}"
    )

    print(
        f"Missing Admission Nos    : "
        f"{len(missing_admission)}"
    )

    print(
        f"Valid students           : "
        f"{len(valid_students)}"
    )

    print(
        f"Invalid students         : "
        f"{len(invalid_students)}"
    )

    # --------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------

    if invalid_students:
        print()
        print(
            "IMPORT STOPPED: "
            "Invalid student records found."
        )
        return

    if missing_admission:
        print()
        print(
            "IMPORT STOPPED: "
            "Records without Admission No found."
        )
        return

    # --------------------------------------------------
    # DATABASE
    # --------------------------------------------------

    db = SessionLocal()

    try:

        # ----------------------------------------------
        # LOAD CLASSES
        # ----------------------------------------------

        school_classes = (
            db.query(
                SchoolClass
            )
            .all()
        )

        class_map = {}

        for school_class in school_classes:

            key = (
                normalize_class_value(
                    school_class.name
                ),
                normalize_class_value(
                    school_class.section
                ),
                clean_text(
                    school_class.academic_year
                ),
            )

            if key in class_map:
                raise RuntimeError(
                    "Duplicate class mapping found: "
                    f"{key}"
                )

            class_map[
                key
            ] = school_class.id

        # ----------------------------------------------
        # LOAD EXISTING STUDENTS
        # ----------------------------------------------

        existing_students = (
            db.query(
                Student
            )
            .all()
        )

        existing_admissions = {
            clean_admission_no(
                student.admission_no
            )
            for student
            in existing_students
        }

        # ----------------------------------------------
        # PREPARE INSERTS
        # ----------------------------------------------

        students_to_insert = []

        skipped_existing = []

        missing_classes = []

        for record in valid_students:

            admission_no = (
                record["admission_no"]
            )

            # Existing Admission No:
            # never overwrite automatically.
            if (
                admission_no
                in existing_admissions
            ):
                skipped_existing.append(
                    record
                )
                continue

            class_key = (
                record["class_name"],
                record["section"],
                record["academic_year"],
            )

            class_id = class_map.get(
                class_key
            )

            if class_id is None:

                missing_classes.append(
                    (
                        record,
                        class_key,
                    )
                )

                continue

            student = Student(
                admission_no=
                    admission_no,

                roll_no=
                    record["roll_no"],

                full_name=
                    record["full_name"],

                date_of_birth=
                    record["date_of_birth"],

                gender=
                    record["gender"],

                class_id=
                    class_id,

                is_active=True,
            )

            students_to_insert.append(
                student
            )

        # ----------------------------------------------
        # FINAL SAFETY CHECK
        # ----------------------------------------------

        if missing_classes:

            print()
            print("=" * 75)
            print("IMPORT STOPPED")
            print("=" * 75)

            print(
                f"Missing class mappings: "
                f"{len(missing_classes)}"
            )

            for (
                record,
                class_key,
            ) in missing_classes[:20]:

                print(
                    f"{record['admission_no']} "
                    f"| "
                    f"{record['full_name']} "
                    f"| "
                    f"{class_key}"
                )

            db.rollback()
            return

        print()
        print("=" * 75)
        print("IMPORT PLAN")
        print("=" * 75)

        print(
            f"Existing DB students    : "
            f"{len(existing_students)}"
        )

        print(
            f"Existing skipped        : "
            f"{len(skipped_existing)}"
        )

        print(
            f"Students to insert      : "
            f"{len(students_to_insert)}"
        )

        print(
            f"Conflicts excluded      : "
            f"{len(conflicts)}"
        )

        # ----------------------------------------------
        # INSERT
        # ----------------------------------------------

        db.add_all(
            students_to_insert
        )

        db.commit()

        print()
        print("=" * 75)
        print("IMPORT SUCCESSFUL")
        print("=" * 75)

        print(
            f"Inserted students       : "
            f"{len(students_to_insert)}"
        )

        print(
            f"Skipped existing        : "
            f"{len(skipped_existing)}"
        )

        print(
            f"Conflicting IDs skipped : "
            f"{len(conflicts)}"
        )

        print()
        print(
            "Student import completed."
        )

    except Exception as exc:

        db.rollback()

        print()
        print("=" * 75)
        print("IMPORT FAILED - ROLLED BACK")
        print("=" * 75)

        print(
            f"Reason: {exc}"
        )

        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()