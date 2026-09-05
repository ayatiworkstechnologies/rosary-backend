import sys
from pathlib import Path


# Allow this file to be run directly from any working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, Base, engine
from app.models.user import User
from app.core.security import hash_password


Base.metadata.create_all(bind=engine)

db = SessionLocal()


def create_user(
    name,
    username,
    email,
    password,
    role
):
    existing_user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if existing_user:
        print(
            f"{username} already exists"
        )
        return

    user = User(
        name=name,
        username=username,
        email=email,
        password_hash=hash_password(
            password
        ),
        role=role,
        is_active=True
    )

    db.add(user)

    print(
        f"{role} created: {username}"
    )


create_user(
    name="Rajesh Parent",
    username="PARENT001",
    email="parent@rosaryschool.com",
    password="Parent@123",
    role="PARENT"
)

create_user(
    name="Sarah Teacher",
    username="TEACHER001",
    email="teacher@rosaryschool.com",
    password="Teacher@123",
    role="TEACHER"
)


db.commit()
db.close()

print("Seed completed")
