"""Authentication service — password hashing, verification, JWT token handling, and input validation."""
import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import jwt

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-production-rent-ease-agent-jwt-key-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$")


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a unique 16-byte random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Verify password against salt:key string using constant-time comparison."""
    if not plain_password or not hashed_password:
        return False
    try:
        parts = hashed_password.split(":")
        if len(parts) != 2:
            return False
        salt, key_hex = parts
        new_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return hmac.compare_digest(new_key.hex(), key_hex)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def validate_email(email: Optional[str]) -> Tuple[bool, str]:
    """Validate email address format and non-empty check."""
    if not email or not isinstance(email, str):
        return False, "Email address is required."
    clean = email.strip()
    if len(clean) > 254:
        return False, "Email address is too long."
    if not EMAIL_REGEX.match(clean):
        return False, "Please enter a valid email address (e.g. name@example.com)."
    return True, ""


def validate_password(password: Optional[str]) -> Tuple[bool, str]:
    """Validate password strength (minimum 6 chars, contains letter and digit)."""
    if not password or not isinstance(password, str):
        return False, "Password is required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    if len(password) > 128:
        return False, "Password must not exceed 128 characters."
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not has_letter or not has_digit:
        return False, "Password must contain at least one letter and one number."
    return True, ""


def validate_phone(phone: Optional[str]) -> Tuple[bool, str]:
    """Validate phone number format if provided."""
    if not phone:
        return True, ""  # Phone is optional
    clean = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if len(clean) < 7 or len(clean) > 15 or not clean.replace("+", "").isdigit():
        return False, "Please enter a valid phone number (at least 10 digits)."
    return True, ""


def validate_signup_payload(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate complete sign-up payload."""
    name = (payload.get("name") or "").strip()
    if not name or len(name) < 2:
        return False, "Please provide your full name (at least 2 characters)."
    if len(name) > 100:
        return False, "Name is too long."

    valid_email, err_email = validate_email(payload.get("email"))
    if not valid_email:
        return False, err_email

    valid_pw, err_pw = validate_password(payload.get("password"))
    if not valid_pw:
        return False, err_pw

    confirm = payload.get("confirm_password")
    if confirm is not None and confirm != payload.get("password"):
        return False, "Passwords do not match."

    phone = payload.get("phone")
    if phone:
        valid_phone, err_phone = validate_phone(phone)
        if not valid_phone:
            return False, err_phone

    return True, ""


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify JWT access token."""
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return decoded
    except jwt.ExpiredSignatureError:
        logger.warning("Access token has expired.")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid access token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error decoding access token: {e}")
        return None
