"""
Authentication module for AERS admin panel.
Uses hashed password verification for security.
"""

import os
import hashlib
import secrets
from typing import Optional
from datetime import datetime, timedelta

# Admin password - change this via environment variable
# Default is hashed version of "aers2024" - CHANGE IN PRODUCTION!
_DEFAULT_PASSWORD_HASH = "1610e9630835f9451836c5835e6bc7363ea0331f080c403ff472b9ecf28b8169"
ADMIN_PASSWORD_HASH = os.environ.get("AERS_ADMIN_PASSWORD_HASH", _DEFAULT_PASSWORD_HASH)

# Session tokens storage
ACTIVE_SESSIONS: dict[str, dict] = {}

# Session expiry time (hours)
SESSION_EXPIRY_HOURS = 24


def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str) -> bool:
    """Verify admin password against stored hash."""
    if not password:
        return False
    return hash_password(password) == ADMIN_PASSWORD_HASH


def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)


def create_session(username: str = "admin") -> tuple[str, datetime]:
    """Create a new admin session."""
    token = generate_token()
    created_at = datetime.now()
    expires_at = created_at + timedelta(hours=SESSION_EXPIRY_HOURS)

    ACTIVE_SESSIONS[token] = {
        "username": username,
        "created_at": created_at,
        "expires_at": expires_at,
    }
    return token, expires_at


def validate_session(token: str) -> bool:
    """Validate if session token is active and not expired."""
    if not token or token not in ACTIVE_SESSIONS:
        return False

    session = ACTIVE_SESSIONS[token]
    if datetime.now() > session.get("expires_at", datetime.now()):
        # Token expired
        destroy_session(token)
        return False

    return True


def destroy_session(token: str) -> None:
    """Destroy a session."""
    if token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]


def get_session_info(token: str) -> Optional[dict]:
    """Get session information."""
    if token in ACTIVE_SESSIONS:
        return ACTIVE_SESSIONS[token]
    return None


def cleanup_expired_sessions() -> int:
    """Remove expired sessions. Returns count of removed sessions."""
    now = datetime.now()
    expired = [
        token for token, session in ACTIVE_SESSIONS.items()
        if now > session.get("expires_at", now)
    ]
    for token in expired:
        del ACTIVE_SESSIONS[token]
    return len(expired)