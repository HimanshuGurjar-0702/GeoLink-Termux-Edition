
import secrets
import time
import hmac


def generate_pairing_code():
    """Generate an 8-digit temporary pairing code."""
    return f"{secrets.randbelow(100_000_000):08d}"


def generate_access_token():
    """Generate a cryptographically secure access token."""
    return secrets.token_urlsafe(32)


def create_pairing_credentials():
    """Create temporary pairing credentials."""
    return {
        "pairing_code": generate_pairing_code(),
        "access_token": generate_access_token(),
        "expires_at": time.time() + 600
    }


def verify_pairing_code(candidate, expected, expires_at):
    """Verify pairing code and expiration."""
    if time.time() > expires_at:
        return False

    if not isinstance(candidate, str):
        return False

    return hmac.compare_digest(candidate, expected)


def verify_access_token(candidate, expected):
    """Verify receiver access token."""
    if not isinstance(candidate, str):
        return False

    return hmac.compare_digest(candidate, expected)
