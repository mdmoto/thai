"""
Authentication & Token Utilities for User Login, Registration, and Verification.
"""

import os
import base64
import binascii
import hmac
import time
import hashlib
import json
import secrets
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if APP_ENV == "production" and not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is required when APP_ENV=production")
SECRET_KEY = SECRET_KEY or "development-only-secret-change-before-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
TOKEN_ISSUER = "thailand-market-twin"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))

def hash_password(password: str) -> str:
    """Hash a password with a unique salt and PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(16)
    iterations = 600_000
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=32,
    )
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{_b64url_encode(salt)}${_b64url_encode(digest)}"
    )

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        scheme, iterations, salt, expected = hashed_password.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            _b64url_decode(salt),
            int(iterations),
            dklen=32,
        )
        return hmac.compare_digest(actual, _b64url_decode(expected))
    except (ValueError, TypeError, binascii.Error):
        return False

def create_access_token(user_id: str, email: str) -> str:
    expire = int(time.time()) + (ACCESS_TOKEN_EXPIRE_DAYS * 86400)
    header = {"alg": ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": int(time.time()),
        "iss": TOKEN_ISSUER,
    }
    encoded_header = _b64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    encoded_payload = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        expected = hmac.new(
            SECRET_KEY.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64url_decode(parts[2])):
            return None
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        data = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        if header.get("alg") != ALGORITHM:
            return None
        if data.get("iss") != TOKEN_ISSUER:
            return None
        if not data.get("exp") or time.time() > float(data["exp"]):
            return None
        return data
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        return None

def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id: str = payload.get("sub")
    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()

def get_current_user_required(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    user = get_current_user_optional(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录或注册账号",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
