"""Create / upgrade the database schema (thin wrapper around the migrations)."""

from dotenv import load_dotenv

load_dotenv()

from database.migrate import apply_migrations  # noqa: E402

if __name__ == "__main__":
    applied = apply_migrations()
    print(
        "Database schema is up to date."
        if not applied
        else "Applied: " + ", ".join(applied)
    )
