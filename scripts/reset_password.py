"""
Set a new password for an existing account (and clear any login lockout).

    python -m scripts.reset_password you@example.com
    python -m scripts.reset_password you@example.com --admin   # also make admin

If the account does not exist, use scripts.create_admin instead.
"""

import argparse
import getpass
import sys

from dotenv import load_dotenv

load_dotenv()

from database.login_attempts_repository import clear_failed_logins  # noqa: E402
from database.user_repository import (  # noqa: E402
    get_user_by_email,
    set_user_admin,
    update_password,
)
from security.hashing import hash_password  # noqa: E402
from security.password_policy import validate_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--admin", action="store_true", help="also grant admin rights")
    args = parser.parse_args()

    email = args.email.strip().lower()
    user = get_user_by_email(email)

    if user is None:
        print(f"No account for {email}. Create it with: python -m scripts.create_admin {email}")
        return 1

    password = getpass.getpass("New password: ")
    error = validate_password(password, email=email, username=user.get("username"))

    if error:
        print(error)
        return 1

    if password != getpass.getpass("Repeat new password: "):
        print("Passwords do not match.")
        return 1

    update_password(user["id"], hash_password(password))
    clear_failed_logins(email)

    if args.admin:
        set_user_admin(user["id"], True)

    print(f"Password updated for {email}. You can sign in now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
