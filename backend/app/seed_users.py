
import argparse
from sqlalchemy import select
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User

DEMO_PASSWORD = "demo1234"
DEMO_USERS = [
    ("demo-admin", "admin@anatolens.dev", "SUPER_ADMIN", "Sara Admin"),
    ("demo-editor", "editor@anatolens.dev", "CONTENT_EDITOR", "Karim Editor"),
    ("demo-reviewer", "reviewer@anatolens.dev", "MEDICAL_REVIEWER", "Dr. Nadia Reviewer"),
    ("demo-teacher", "teacher@anatolens.dev", "TEACHER", "Youssef Teacher"),
    ("demo-student-amira", "amira@anatolens.dev", "STUDENT", "Amira (student)"),
    ("demo-student-omar", "omar@anatolens.dev", "STUDENT", "Omar (student)"),
    ("demo-student-lina", "lina@anatolens.dev", "STUDENT", "Lina (student)"),
]

def seed_users(db, password: str = DEMO_PASSWORD) -> list[User]:
    hashed = hash_password(password)
    out = []
    for uid, email, role, name in DEMO_USERS:
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none() or User(id=uid, email=email)
        u.password_hash, u.role, u.display_name = hashed, role, name
        db.add(u)
        out.append(u)
    db.commit()
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--password", default=DEMO_PASSWORD)
    args = ap.parse_args()
    with SessionLocal() as db:
        for u in seed_users(db, args.password):
            print(f"{u.role:<17} {u.email:<26} {u.display_name}")
    print(f"password for all: {args.password}")
