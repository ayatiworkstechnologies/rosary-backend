"""READ-ONLY production integrity audit.

Intentionally performs only SELECT/COUNT style aggregate statements.
Prints counts and ratios only -- no names, phone numbers, or credentials.

Usage (server):
    <release-dir>/venv/bin/python production_db_audit.py <release-dir>
"""

import os
import re
import sys

from sqlalchemy import create_engine, text

release_dir = sys.argv[1] if len(sys.argv) > 1 else "."
env_path = os.path.join(release_dir, ".env")

database_url = None
with open(env_path) as handle:
    for line in handle:
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            database_url = line.split("=", 1)[1].strip().strip("'\"")
            break

if not database_url:
    print("DATABASE_URL_NOT_FOUND")
    sys.exit(1)

print("DB host in URL: 127.0.0.1:3307", "yes" if "127.0.0.1:3307" in database_url else "unexpected-host")


def boldify(url: str) -> str:
    """Do not print credentials; announce the DB name only."""
    match = re.search(r"/([a-z_0-9]+)(\?|$)", url)
    return match.group(1) if match else "unknown"


engine = create_engine(database_url)

QUERIES = {
    "total_students": "SELECT COUNT(*) FROM students",
    "active_students": "SELECT COUNT(*) FROM students WHERE is_active = 1",
    "students_without_admission_no": "SELECT COUNT(*) FROM students WHERE admission_no IS NULL OR admission_no = ''",
    "duplicate_admission_groups": "SELECT COUNT(*) FROM (SELECT admission_no FROM students WHERE admission_no IS NOT NULL AND admission_no != '' GROUP BY admission_no HAVING COUNT(*) > 1) t",
    "duplicate_admission_rows": "SELECT COUNT(*) FROM students WHERE admission_no IN (SELECT admission_no FROM students WHERE admission_no IS NOT NULL AND admission_no != '' GROUP BY admission_no HAVING COUNT(*) > 1)",
    "parent_users": "SELECT COUNT(*) FROM users WHERE role = 'PARENT'",
    "active_parent_users": "SELECT COUNT(*) FROM users WHERE role = 'PARENT' AND is_active = 1",
    "parent_profiles": "SELECT COUNT(*) FROM parent_profiles",
    "users_without_profile": "SELECT COUNT(*) FROM users u WHERE u.role = 'PARENT' AND NOT EXISTS (SELECT 1 FROM parent_profiles pp WHERE pp.user_id = u.id)",
    "link_rows": "SELECT COUNT(*) FROM parent_students",
    "linked_students": "SELECT COUNT(DISTINCT student_id) FROM parent_students",
    "active_linked_students": "SELECT COUNT(*) FROM students s WHERE s.is_active = 1 AND EXISTS (SELECT 1 FROM parent_students ps WHERE ps.student_id = s.id)",
    "unlinked_active_students": "SELECT COUNT(*) FROM students s WHERE s.is_active = 1 AND NOT EXISTS (SELECT 1 FROM parent_students ps WHERE ps.student_id = s.id)",
    "orphan_links_missing_parent_user": "SELECT COUNT(*) FROM parent_students ps WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = ps.parent_user_id)",
    "orphan_links_missing_student": "SELECT COUNT(*) FROM parent_students ps WHERE NOT EXISTS (SELECT 1 FROM students s WHERE s.id = ps.student_id)",
    "duplicate_link_groups": "SELECT COUNT(*) FROM (SELECT parent_user_id, student_id FROM parent_students GROUP BY parent_user_id, student_id HAVING COUNT(*) > 1) t",
    "parents_with_multiple_children": "SELECT COUNT(*) FROM (SELECT parent_user_id FROM parent_students GROUP BY parent_user_id HAVING COUNT(DISTINCT student_id) > 1) t",
    "classes": "SELECT COUNT(*) FROM school_classes",
    "teacher_users": "SELECT COUNT(*) FROM users WHERE role = 'TEACHER'",
    "active_teacher_users": "SELECT COUNT(*) FROM users WHERE role = 'TEACHER' AND is_active = 1",
    "teacher_mapping_rows": "SELECT COUNT(*) FROM teacher_classes",
    "teachers_without_class_mapping": "SELECT COUNT(*) FROM users u WHERE u.role = 'TEACHER' AND u.is_active = 1 AND NOT EXISTS (SELECT 1 FROM teacher_classes tc WHERE tc.teacher_user_id = u.id)",
    "orphan_teacher_mappings_missing_teacher": "SELECT COUNT(*) FROM teacher_classes tc WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = tc.teacher_user_id)",
    "orphan_teacher_mappings_missing_class": "SELECT COUNT(*) FROM teacher_classes tc WHERE NOT EXISTS (SELECT 1 FROM school_classes sc WHERE sc.id = tc.class_id)",
    "students_without_class": "SELECT COUNT(*) FROM students WHERE class_id IS NULL",
    "orphan_students_missing_class": "SELECT COUNT(*) FROM students s WHERE s.class_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM school_classes sc WHERE sc.id = s.class_id)",
    "fee_rows": "SELECT COUNT(*) FROM student_fees",
    "fee_rows_without_student": "SELECT COUNT(*) FROM student_fees f WHERE NOT EXISTS (SELECT 1 FROM students s WHERE s.id = f.student_id)",
    "notification_rows": "SELECT COUNT(*) FROM notifications",
    "active_admins": "SELECT COUNT(*) FROM users WHERE role = 'ADMIN' AND is_active = 1",
}

with engine.connect() as connection:
    print("database:", boldify(database_url))
    print("table_count:", 19, "(informational)")
    for label, sql in QUERIES.items():
        try:
            result = connection.execute(text(sql))
            print(f"{label}: {result.scalar()}")
        except Exception as exc:  # noqa: BLE001 - report, stay read-only
            print(f"{label}: ERROR {type(exc).__name__}")
    # duplicate admission examples, no-op list gate
    try:
        dupes = connection.execute(
            text(
                "SELECT admission_no, COUNT(*) AS c FROM students "
                "WHERE admission_no IS NOT NULL AND admission_no != '' "
                "GROUP BY admission_no HAVING c > 1 ORDER BY c DESC LIMIT 5"
            )
        ).all()
        print("top_duplicate_admissions(count_only):", [(d[1]) for d in dupes])
    except Exception:  # noqa: BLE001
        print("top_duplicate_admissions: ERROR")

print("audit complete (read-only)")
