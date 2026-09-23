from getpass import getpass

from app.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password, verify_password


db = SessionLocal()

try:
    user = (
        db.query(User)
        .filter(User.username == "ADMIN001")
        .first()
    )

    if not user:
        print("ERROR: ADMIN001 does not exist.")
        raise SystemExit(1)

    print("Found:", user.username)
    print("Role:", user.role)
    print("Active:", user.is_active)

    password = getpass("Enter NEW password: ")
    confirm = getpass("Confirm NEW password: ")

    if password != confirm:
        print("ERROR: Passwords do not match.")
        raise SystemExit(1)

    if len(password) < 8:
        print("ERROR: Minimum 8 characters required.")
        raise SystemExit(1)

    user.password_hash = hash_password(password)
    user.role = "ADMIN"
    user.is_active = True

    db.commit()
    db.refresh(user)

    result = verify_password(
        password,
        user.password_hash,
    )

    print("Password verification:", result)
    print("Username:", user.username)
    print("Role:", user.role)
    print("Active:", user.is_active)

finally:
    db.close()