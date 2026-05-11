import secrets
import string


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)[:length]


# Crockford-style unambiguous alphabet – no I/O/0/1/L/U to avoid lookalikes and
# accidental words. 32 symbols, 10 chars => ~10^15 combos: not guessable.
PICKUP_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"


def generate_pickup_code(length: int = 10) -> str:
    return "".join(secrets.choice(PICKUP_ALPHABET) for _ in range(length))


def generate_job_number(seq: int) -> str:
    from datetime import datetime
    return f"J{datetime.utcnow():%y%m}-{seq:05d}"
