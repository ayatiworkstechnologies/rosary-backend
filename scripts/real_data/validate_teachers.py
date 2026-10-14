from pathlib import Path
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "input" / "Teacher_details.xlsx"


# ============================================================
# HELPERS
# ============================================================

def clean_column_name(value):
    return str(value).strip()


def find_column(df, possible_names):
    normalized = {
        str(col).strip().lower(): col
        for col in df.columns
    }

    for name in possible_names:
        key = name.strip().lower()

        if key in normalized:
            return normalized[key]

    return None


def empty_count(series):
    return (
        series.isna()
        | series.astype(str).str.strip().isin(["", "nan", "None"])
    ).sum()


# ============================================================
# VALIDATION
# ============================================================

def main():

    print("=" * 60)
    print("ROSARY - TEACHER EXCEL VALIDATION")
    print("=" * 60)

    # --------------------------------------------------------
    # File check
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        print(f"\n❌ Teacher Excel not found:")
        print(INPUT_FILE)
        return

    print(f"\n✅ Excel file found:")
    print(INPUT_FILE)

    # --------------------------------------------------------
    # Read Excel
    # --------------------------------------------------------

    try:
        df = pd.read_excel(INPUT_FILE)
    except Exception as exc:
        print("\n❌ Unable to read Excel file.")
        print(exc)
        return

    df.columns = [clean_column_name(col) for col in df.columns]

    # Remove completely empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    print(f"\nTotal teacher rows: {len(df)}")

    print("\nExcel columns found:")
    for column in df.columns:
        print(f"  - {column}")

    # --------------------------------------------------------
    # Detect important columns
    # --------------------------------------------------------

    column_map = {
        "teacher_id": find_column(
            df,
            [
                "Teacher ID / Employee ID",
                "Teacher Id",
                "Employee ID",
                "Employee Id",
                "Staff ID",
            ],
        ),

        "name": find_column(
            df,
            [
                "Teacher Name",
                "Name",
                "First Name",
                "Staff Name",
            ],
        ),

        "email": find_column(
            df,
            [
                "Email",
                "Email ID",
                "Email Id",
                "Email Address",
            ],
        ),

        "mobile": find_column(
            df,
            [
                "Mobile",
                "Mobile Number",
                "Phone",
                "Phone Number",
                "Contact Number",
            ],
        ),

        "dob": find_column(
            df,
            [
                "DOB",
                "Date of Birth",
                "Date Of Birth",
            ],
        ),

        "gender": find_column(
            df,
            [
                "Gender",
                "Sex",
            ],
        ),

        "designation": find_column(
            df,
            [
                "Designation",
                "Role",
            ],
        ),

        "subject": find_column(
            df,
            [
                "Specialization / Subject",
                "Subject",
                "Specialization",
                "Subject / Specialization",
            ],
        ),

        "joining_date": find_column(
            df,
            [
                "Joining Date",
                "Date of Joining",
                "Date Of Joining",
            ],
        ),

        "mapping": find_column(
            df,
            [
                "Class & Section Mapping",
                "Class and Section Mapping",
                "Class Section Mapping",
                "Class & Section",
            ],
        ),
    }

    # --------------------------------------------------------
    # Required columns
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("COLUMN DETECTION")
    print("=" * 60)

    for key, column in column_map.items():
        if column:
            print(f"✅ {key:<15} -> {column}")
        else:
            print(f"⚠️  {key:<15} -> NOT FOUND")

    required = [
        "teacher_id",
        "name",
        "email",
        "mobile",
    ]

    missing_required_columns = [
        key
        for key in required
        if not column_map[key]
    ]

    if missing_required_columns:
        print("\n❌ Required columns missing:")
        for item in missing_required_columns:
            print(f"  - {item}")

        print("\nStop here and check the Excel headers.")
        return

    # --------------------------------------------------------
    # Missing values
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("MISSING VALUE CHECK")
    print("=" * 60)

    problems = 0

    for key in required:

        column = column_map[key]

        count = int(empty_count(df[column]))

        if count:
            print(f"❌ {column}: {count} empty row(s)")
            problems += count
        else:
            print(f"✅ {column}: complete")

    # --------------------------------------------------------
    # Duplicate checks
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("DUPLICATE CHECK")
    print("=" * 60)

    duplicate_fields = [
        "teacher_id",
        "email",
        "mobile",
    ]

    for key in duplicate_fields:

        column = column_map.get(key)

        if not column:
            continue

        values = df[column].astype(str).str.strip()

        duplicate_mask = (
            values.ne("")
            & values.ne("nan")
            & values.duplicated(keep=False)
        )

        duplicates = df.loc[duplicate_mask, column]

        if duplicates.empty:

            print(f"✅ {column}: no duplicates")

        else:

            print(f"❌ {column}: duplicate values found")

            for value in sorted(duplicates.unique()):
                print(f"    - {value}")

            problems += len(duplicates)

    # --------------------------------------------------------
    # Mapping check
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("CLASS & SECTION MAPPING")
    print("=" * 60)

    mapping_column = column_map["mapping"]

    if mapping_column:

        missing_mapping = int(
            empty_count(df[mapping_column])
        )

        if missing_mapping:

            print(
                f"⚠️ {missing_mapping} record(s) have "
                "empty class/section mapping."
            )

        else:

            print(
                "✅ All records have a Class & Section Mapping value."
            )

        print("\nMapping samples:")

        for value in (
            df[mapping_column]
            .dropna()
            .astype(str)
            .head(10)
        ):
            print(f"  {value}")

    else:

        print("❌ Class & Section Mapping column not found.")
        problems += 1

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print("\n" + "=" * 60)

    if problems == 0:

        print("✅ TEACHER EXCEL VALIDATION PASSED")

    else:

        print(
            f"⚠️ TEACHER EXCEL VALIDATION COMPLETED "
            f"WITH {problems} ISSUE(S)"
        )

    print("=" * 60)


if __name__ == "__main__":
    main()