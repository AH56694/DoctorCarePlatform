"""Create the first administrator interactively; never use a seeded password."""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.db.models import AdminLog, User, UserRole
from backend.app.db.session import SessionLocal
from backend.app.schemas.accounts import UserRegister
from backend.app.services.auth import hash_password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--name", default="平台管理员")
    args = parser.parse_args()
    password = getpass.getpass("Administrator password (at least 12 characters): ")
    if len(password) < 12 or password != getpass.getpass("Repeat password: "):
        raise SystemExit("Password too short or confirmation does not match")
    payload = UserRegister(phone=args.phone, password=password, display_name=args.name)
    with SessionLocal.begin() as db:
        if db.query(User).filter(User.phone == payload.phone).first():
            raise SystemExit("Account already exists; no permissions were changed")
        user = User(
            phone=payload.phone, password_hash=hash_password(password),
            display_name=payload.display_name, active_role="admin",
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role="admin", is_active=True, verification_status="approved"))
        db.add(AdminLog(
            admin_id=user.id, action="admin.bootstrap", target_type="user", target_id=user.id,
        ))
    print("Administrator created; the operation was recorded in the audit log.")


if __name__ == "__main__":
    main()
