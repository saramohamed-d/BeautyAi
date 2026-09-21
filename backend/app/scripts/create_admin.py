"""
Create a platform admin login.

    python -m app.scripts.create_admin admin@example.com

Platform admins can't sign up through the API (by design), so this is
how the first admin of a real deployment gets created. The password is
read interactively and never appears in shell history or logs.
"""

import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.core.security import hash_password
from app.schemas.auth import _validate_password
from app.services.auth_service import normalize_email


async def create_admin(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        if await db.scalar(select(User).where(User.email == email)):
            raise SystemExit(f"A user with email {email} already exists.")
        db.add(User(email=email, password_hash=hash_password(password), role=UserRole.PLATFORM_ADMIN))
        await db.commit()
    print(f"Platform admin {email} created.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    email = normalize_email(parser.parse_args().email)

    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords don't match.")
    try:
        _validate_password(password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    asyncio.run(create_admin(email, password))


if __name__ == "__main__":
    main()
