"""
Authentication & Token Utilities for User Login, Registration, and Verification.
"""

import os
import json
import base64
import time
import hashlib
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "market-twin-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/login", auto_error=False)

def hash_password(password: str) -> str:
    """Hashes a password securely using PBKDF2-HMAC-SHA256."""
    salt = b"thailand_market_twin_salt_2026"
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000).hex()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

def create_access_token(user_id: str, email: str) -> str:
    expire = int(time.time()) + (ACCESS_TOKEN_EXPIRE_DAYS * 86400)
    payload = {"sub": user_id, "email": email, "exp": expire}

    if HAS_JWT:
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    # Lightweight fallback token
    raw = json.dumps(payload).encode("utf-8")
    sig = hashlib.sha256(raw + SECRET_KEY.encode("utf-8")).hexdigest()[:16]
    return base64.urlsafe_b64encode(raw).decode("utf-8") + "." + sig

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    if HAS_JWT:
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except Exception:
            return None

    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        raw = base64.urlsafe_b64decode(parts[0].encode("utf-8"))
        sig = hashlib.sha256(raw + SECRET_KEY.encode("utf-8")).hexdigest()[:16]
        if sig != parts[1]:
            return None
        data = json.loads(raw.decode("utf-8"))
        if data.get("exp") and time.time() > data["exp"]:
            return None
        return data
    except Exception:
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
