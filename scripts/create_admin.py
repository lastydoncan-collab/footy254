"""
Create an administrator, or promote an existing user.

    python -m scripts.create_admin you@example.com
    python -m scripts.create_admin you@example.com --demote

If the account does not exist you are prompted for its details and password
(the password is never passed on the command line, so it stays out of shell
history). Administrators can run /api/sync/*, /api/admin/* and bypass the
subscription paywall.
"""

import argparse
import getpass
import sys

from dotenv import load_dotenv

load_dotenv()

from database.migrate import apply_migrations  # noqa: E402
from database.user_repository import (  # noqa: E402
    create_user,
    get_user_by_email,
    set_user_admin,
)
from security.hashing import hash_password  # noqa: E402
from security.password_policy import validate_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--demote", action="store_true", help="remove admin rights")
    args = parser.parse_args()

    email = args.email.strip().lower()

    apply_migrations()

    user = get_user_by_email(email)

    if user is None:
        if args.demote:
            print("No such user.")
            return 1

        print(f"No account for {email}; creating one.")
        first = input("First name: ").strip()
        last = input("Last name: ").strip()
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")

        error = validate_password(password, email=email, username=username)

        if error or not (first and last and username):
            print(error or "All fields are required.")
            return 1

        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match.")
            return 1

        user_id = create_user(first, last, username, email, hash_password(password))
    else:
        user_id = user["id"]

    set_user_admin(user_id, not args.demote)
    print(f"{email} is now {'a regular user' if args.demote else 'an administrator'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
