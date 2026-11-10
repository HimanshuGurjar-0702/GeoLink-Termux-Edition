import secrets
import time
import hmac


def create_pairing_credentials():
    return {
        "pairing_code": f"{secrets.randbelow(100_000_000):08d}",
        "access_token": secrets.token_urlsafe(32),
        "expires_at": time.time() + 600
    }


def verify_pairing_code(candidate, expected, expires_at):
    if time.time() > expires_at:
        return False

    if not isinstance(candidate, str):
        return False

    return hmac.compare_digest(candidate, expected)


def verify_access_token(candidate, expected):
    if not isinstance(candidate, str):
        return False

    if not isinstance(expected, str):
        return False

    return hmac.compare_digest(candidate, expected)
