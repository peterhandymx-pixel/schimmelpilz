"""Local account authentication using password hashes and opaque cookie sessions."""

import hashlib
import hmac
import re
import secrets
import os
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator, model_validator

COOKIE_NAME = "schimmelpilz_session"
SESSION_DAYS = 7
failed_logins: dict[str, list[datetime]] = {}


class RegisterInput(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)
    audience: Literal["consumer", "business", "law_firm"]
    full_name: str = Field(min_length=3, max_length=160)
    organisation: str = Field(default="", max_length=160)
    street: str = Field(min_length=3, max_length=200)
    postal_code: str = Field(min_length=2, max_length=20)
    city: str = Field(min_length=2, max_length=100)
    country: str = Field(min_length=2, max_length=100)
    phone: str = Field(default="", max_length=60)

    @field_validator("email", "full_name", "organisation", "street", "postal_code", "city", "country", "phone", mode="before")
    @classmethod
    def strip_input(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("A valid email is required")
        return value.lower()

    @model_validator(mode="after")
    def require_organisation(self):
        if self.audience != "consumer" and not self.organisation:
            raise ValueError("Business and law firm accounts require an organisation")
        return self


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


def password_hash(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), n=16384, r=8, p=1, maxmem=64 * 1024 * 1024).hex()


def verify_password(password: str, salt: str, expected: str) -> bool:
    return hmac.compare_digest(password_hash(password, salt), expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_user(row) -> dict:
    return {key: row[key] for key in ("id", "email", "audience", "full_name", "organisation", "street", "postal_code", "city", "country", "phone", "created_at")}


def set_session(connection, user_id: str, request: Request, response: Response) -> None:
    timestamp = datetime.now(UTC)
    connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (timestamp.isoformat(),))
    # Replacing a cookie also revokes its former session.
    old = request.cookies.get(COOKIE_NAME)
    if old:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(old),))
    token = secrets.token_urlsafe(32)
    connection.execute("INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)", (token_hash(token), user_id, (timestamp + timedelta(days=SESSION_DAYS)).isoformat()))
    secure_cookie = request.url.scheme == "https" or os.getenv("COOKIE_SECURE", "").lower() == "true"
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, httponly=True, secure=secure_cookie, samesite="strict", path="/")


def check_login_limit(request: Request) -> str:
    key = request.client.host if request.client else "local"
    cutoff = datetime.now(UTC) - timedelta(minutes=15)
    # Bound memory while allowing old client entries to expire.
    for address in list(failed_logins):
        failed_logins[address] = [time for time in failed_logins[address] if time > cutoff]
        if not failed_logins[address]:
            del failed_logins[address]
    if len(failed_logins.get(key, [])) >= 10:
        raise HTTPException(status_code=429, detail="Too many login attempts", headers={"Retry-After": "900"})
    return key
