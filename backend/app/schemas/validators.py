"""Field validators shared by the sign-up schemas (patient, doctor)."""

PASSWORD_MIN_LENGTH = 8
BCRYPT_MAX_BYTES = 72


def validate_password(value: str) -> str:
    # Length over complexity rules (NIST SP 800-63B). The byte cap exists
    # because bcrypt ignores everything after 72 bytes; Arabic characters
    # take 2 bytes each in UTF-8, so this is checked in bytes, not chars.
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"password must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"password must be at most {BCRYPT_MAX_BYTES} bytes")
    return value
