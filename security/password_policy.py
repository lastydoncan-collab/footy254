"""Server-side password rules (the frontend mirrors the length rule only)."""

from config.settings import PASSWORD_MAX_BYTES, PASSWORD_MIN_LENGTH

# Small deny-list of the passwords attackers try first. Not exhaustive on
# purpose: the goal is to stop trivially guessable choices, not to ship a
# breach corpus.
_COMMON = frozenset(
    """
    password password1 password12 password123 passw0rd p@ssw0rd p@ssword
    12345678 123456789 1234567890 11111111 00000000 87654321 123123123
    qwertyui qwerty123 qwertyuiop 1q2w3e4r 1q2w3e4r5t abc12345 abcd1234
    iloveyou iloveyou1 letmein1 welcome1 welcome123 admin123 administrator
    football football1 football123 footy254 footy2540 kenya254 nairobi254
    arsenal1 chelsea1 liverpool manutd123 monkey123 dragon123 sunshine1
    changeme changeme1 trustno1 baseball1 superman1 michael123 jennifer1
    """.split()
)


def validate_password(
    password: str,
    *,
    email: str | None = None,
    username: str | None = None,
) -> str | None:
    """Return an error message, or ``None`` when the password is acceptable."""

    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."

    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return (
            f"Password must be at most {PASSWORD_MAX_BYTES} bytes "
            "(fewer characters if it contains accents or emoji)."
        )

    if password.isdigit():
        return "Password cannot be only numbers."

    lowered = password.lower()

    if lowered in _COMMON:
        return "That password is too common. Choose something harder to guess."

    for personal in (
        (email or "").split("@")[0],
        username or "",
    ):
        personal = personal.strip().lower()

        if len(personal) >= 4 and personal in lowered:
            return "Password must not contain your email name or username."

    return None
