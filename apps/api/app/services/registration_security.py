"""Email verification, Turnstile validation, and durable registration limits."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict

import httpx
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.auth import hash_password
from app.db.models import PendingRegistration, RegistrationAttempt, User


TURNSTILE_VERIFY_URL = (
    "https://challenges.cloudflare.com/turnstile/v0/siteverify"
)
RESEND_EMAIL_URL = "https://api.resend.com/emails"


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def verification_is_required() -> bool:
    return _enabled(os.environ.get("EMAIL_VERIFICATION_REQUIRED"))


def public_auth_config() -> Dict[str, Any]:
    required = verification_is_required()
    return {
        "email_verification_required": required,
        "turnstile_site_key": (
            os.environ.get("TURNSTILE_SITE_KEY", "").strip()
            if required
            else None
        ),
    }


def ensure_verification_configured() -> None:
    if not verification_is_required():
        return
    required = (
        "TURNSTILE_SITE_KEY",
        "TURNSTILE_SECRET_KEY",
        "TURNSTILE_EXPECTED_HOSTNAMES",
        "RESEND_API_KEY",
        "REGISTRATION_SECURITY_KEY",
        "VERIFICATION_FROM_EMAIL",
    )
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError(
            "Email verification is enabled but required configuration is missing: "
            + ", ".join(missing)
        )


def _security_key() -> bytes:
    key = os.environ.get("REGISTRATION_SECURITY_KEY", "").strip()
    if not key:
        key = os.environ.get("JWT_SECRET_KEY", "development-registration-key")
    return key.encode("utf-8")


def _fingerprint(value: str) -> str:
    return hmac.new(
        _security_key(),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _request_ip(request: Request) -> str:
    candidate = request.client.host if request.client else "unknown"
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        forwarded = request.headers.get("x-forwarded-for", "")
        for item in reversed(forwarded.split(",")):
            try:
                return str(ipaddress.ip_address(item.strip()))
            except ValueError:
                continue
    return candidate[:120]


def _subnet_for(ip_value: str) -> str:
    try:
        address = ipaddress.ip_address(ip_value)
    except ValueError:
        return ip_value
    prefix = 24 if address.version == 4 else 56
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


def enforce_registration_limits(
    db: Session,
    request: Request,
    email: str,
) -> str:
    """Count every verification request before external work is performed."""
    now = datetime.utcnow()
    ip_value = _request_ip(request)
    ip_hash = _fingerprint(f"ip:{ip_value}")
    subnet_hash = _fingerprint(f"subnet:{_subnet_for(ip_value)}")
    email_hash = _fingerprint(f"email:{email}")
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    retention_cutoff = now - timedelta(days=7)

    db.query(RegistrationAttempt).filter(
        RegistrationAttempt.created_at < retention_cutoff
    ).delete(synchronize_session=False)
    db.query(PendingRegistration).filter(
        PendingRegistration.expires_at < day_ago
    ).delete(synchronize_session=False)

    ip_limit = int(os.environ.get("REGISTRATION_IP_HOURLY_LIMIT", "3"))
    email_limit = int(os.environ.get("REGISTRATION_EMAIL_HOURLY_LIMIT", "3"))
    subnet_limit = int(os.environ.get("REGISTRATION_SUBNET_DAILY_LIMIT", "10"))

    ip_count = (
        db.query(RegistrationAttempt)
        .filter(
            RegistrationAttempt.ip_hash == ip_hash,
            RegistrationAttempt.created_at >= hour_ago,
        )
        .count()
    )
    email_count = (
        db.query(RegistrationAttempt)
        .filter(
            RegistrationAttempt.email_hash == email_hash,
            RegistrationAttempt.created_at >= hour_ago,
        )
        .count()
    )
    subnet_count = (
        db.query(RegistrationAttempt)
        .filter(
            RegistrationAttempt.subnet_hash == subnet_hash,
            RegistrationAttempt.created_at >= day_ago,
        )
        .count()
    )
    if (
        ip_count >= ip_limit
        or email_count >= email_limit
        or subnet_count >= subnet_limit
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证码请求过于频繁，请稍后再试",
            headers={"Retry-After": "3600"},
        )

    db.add(
        RegistrationAttempt(
            ip_hash=ip_hash,
            subnet_hash=subnet_hash,
            email_hash=email_hash,
            outcome="REQUESTED",
        )
    )
    db.commit()
    return ip_value


async def verify_turnstile(token: str, remote_ip: str) -> None:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请完成人机验证",
        )
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(
            TURNSTILE_VERIFY_URL,
            data={
                "secret": os.environ["TURNSTILE_SECRET_KEY"],
                "response": token,
                "remoteip": remote_ip,
                "idempotency_key": secrets.token_hex(16),
            },
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="人机验证服务暂时不可用，请稍后再试",
        )
    result = response.json()
    allowed_hosts = {
        item.strip().lower()
        for item in os.environ["TURNSTILE_EXPECTED_HOSTNAMES"].split(",")
        if item.strip()
    }
    hostname = str(result.get("hostname") or "").lower()
    action = str(result.get("action") or "")
    if (
        not result.get("success")
        or hostname not in allowed_hosts
        or action != "register"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="人机验证未通过，请刷新后重试",
        )


def _code_digest(challenge_id: str, email: str, code: str) -> str:
    return hmac.new(
        _security_key(),
        f"{challenge_id}:{email}:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def _send_verification_email(email: str, code: str) -> None:
    payload = {
        "from": os.environ["VERIFICATION_FROM_EMAIL"],
        "to": [email],
        "subject": "Chiang Mai AI Center 邮箱验证码",
        "text": (
            f"您的注册验证码是：{code}\n\n"
            "验证码 10 分钟内有效。如果不是您本人操作，请忽略此邮件。"
        ),
        "html": (
            "<div style=\"font-family:Arial,sans-serif;color:#171717;"
            "max-width:520px;margin:auto;padding:28px\">"
            "<h2 style=\"margin:0 0 16px\">Chiang Mai AI Center</h2>"
            "<p>您的注册验证码：</p>"
            f"<div style=\"font-size:32px;font-weight:700;letter-spacing:8px;"
            f"padding:18px 0\">{code}</div>"
            "<p style=\"color:#666\">验证码 10 分钟内有效。"
            "如果不是您本人操作，请忽略此邮件。</p></div>"
        ),
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            RESEND_EMAIL_URL,
            headers={
                "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code not in {200, 201}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="验证码邮件暂时无法发送，请稍后再试",
        )


async def create_registration_challenge(
    db: Session,
    request: Request,
    *,
    email: str,
    password: str,
    name: str | None,
    company: str | None,
    invite_code: str | None,
    turnstile_token: str,
) -> PendingRegistration:
    ensure_verification_configured()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="该邮箱已被注册")
    remote_ip = enforce_registration_limits(db, request, email)
    await verify_turnstile(turnstile_token, remote_ip)

    challenge = PendingRegistration(
        email=email,
        password_hash=hash_password(password),
        name=name,
        company=company,
        invite_code=invite_code,
        code_digest="pending",
        attempts_remaining=5,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(challenge)
    db.flush()
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge.code_digest = _code_digest(challenge.id, email, code)
    try:
        await _send_verification_email(email, code)
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(challenge)
    return challenge


def consume_registration_challenge(
    db: Session,
    challenge_id: str,
    code: str,
) -> PendingRegistration:
    challenge = (
        db.query(PendingRegistration)
        .filter(PendingRegistration.id == challenge_id)
        .with_for_update()
        .first()
    )
    now = datetime.utcnow()
    if (
        not challenge
        or challenge.consumed_at is not None
        or challenge.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码已失效，请重新获取",
        )
    if challenge.attempts_remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证码错误次数过多，请重新获取",
        )
    expected = _code_digest(challenge.id, challenge.email, code)
    if not hmac.compare_digest(expected, challenge.code_digest):
        challenge.attempts_remaining -= 1
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码不正确",
        )
    return challenge
