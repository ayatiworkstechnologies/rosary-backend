"""Aggregate-only parent email readiness report.

This script performs SELECT queries only and never prints names, addresses,
student identifiers, or credentials.
"""

from pathlib import Path
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import text


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import engine


QUERY = text(
    """
    SELECT DISTINCT u.id, u.email
    FROM users AS u
    INNER JOIN parent_students AS ps ON ps.parent_user_id = u.id
    INNER JOIN students AS s ON s.id = ps.student_id
    WHERE u.role = 'PARENT'
      AND u.is_active = 1
      AND s.is_active = 1
    ORDER BY u.id
    """
)


def main() -> None:
    with engine.connect() as connection:
        rows = connection.execute(QUERY).mappings().all()

    missing = 0
    invalid = 0
    valid_emails: set[str] = set()
    duplicates = 0

    for row in rows:
        value = (row["email"] or "").strip()
        if not value:
            missing += 1
            continue
        try:
            normalized = validate_email(
                value, check_deliverability=False
            ).normalized.lower()
        except EmailNotValidError:
            invalid += 1
            continue
        if normalized in valid_emails:
            duplicates += 1
        valid_emails.add(normalized)

    print("Parent email readiness (aggregate only)")
    print(f"Active linked parent accounts : {len(rows)}")
    print(f"Missing email addresses       : {missing}")
    print(f"Invalid email addresses       : {invalid}")
    print(f"Unique syntactically valid    : {len(valid_emails)}")
    print(f"Duplicate normalized emails   : {duplicates}")
    print("Verified / preference enabled : not available until migration and approval")


if __name__ == "__main__":
    main()
