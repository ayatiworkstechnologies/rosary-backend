from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal
from app.models.school_class import SchoolClass


db = SessionLocal()

missing_classes = [
    ("I", "B"),
    ("I", "C"),
    ("I", "D"),
    ("VII", "B"),
    ("VII", "D"),
    ("XI", "B"),
    ("XII", "C"),
]

try:
    for name, section in missing_classes:
        existing = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.name == name,
                SchoolClass.section == section,
                SchoolClass.academic_year == "2026-2027",
            )
            .first()
        )

        if existing:
            print(f"EXISTS  : {name}-{section}")
        else:
            db.add(
                SchoolClass(
                    name=name,
                    section=section,
                    academic_year="2026-2027",
                    is_active=True,
                )
            )
            print(f"CREATED : {name}-{section}")

    db.commit()
    print("Done")

finally:
    db.close()