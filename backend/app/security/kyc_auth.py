"""Backend-configured, non-production KYC authentication for the competition prototype."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Literal

from fastapi import Header, HTTPException, status

KYC_AUTH_SECRET_ENV = "UDYAMONE_KYC_AUTH_SECRET"
KYC_AUTH_USERS_ENV = "UDYAMONE_KYC_AUTH_USERS"
PASSWORD_HASH_ITERATIONS = 600_000
SESSION_LIFETIME_SECONDS = 1_800
_MIN_SECRET_BYTES = 32
_MIN_PASSWORD_HASH_ITERATIONS = 100_000
_MAX_PASSWORD_HASH_ITERATIONS = 2_000_000
_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,99}")
_APPLICANT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")

KycRole = Literal["CUSTOMER", "REVIEWER"]


class KycAuthConfigurationError(ValueError):
    """Raised when backend authentication configuration is missing or malformed."""


@dataclass(frozen=True)
class KycAuthAccount:
    username: str
    role: KycRole
    password_hash: str
    applicant_ids: frozenset[str]


@dataclass(frozen=True)
class KycPrincipal:
    username: str
    role: KycRole
    applicant_ids: frozenset[str]
    expires_at: int


@dataclass(frozen=True)
class KycAuthConfiguration:
    secret: bytes
    accounts: dict[str, KycAuthAccount]


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _parse_password_hash(value: str) -> tuple[int, bytes, bytes]:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = value.split("$")
        iterations = int(raw_iterations)
        salt = _b64decode(raw_salt)
        digest = _b64decode(raw_digest)
    except (ValueError, TypeError, binascii.Error) as error:
        raise KycAuthConfigurationError(
            "KYC authentication configuration contains an invalid password hash."
        ) from error
    if (
        algorithm != "pbkdf2_sha256"
        or not _MIN_PASSWORD_HASH_ITERATIONS <= iterations <= _MAX_PASSWORD_HASH_ITERATIONS
        or len(salt) < 16
        or len(digest) != hashlib.sha256().digest_size
    ):
        raise KycAuthConfigurationError(
            "KYC authentication configuration contains an invalid password hash."
        )
    return iterations, salt, digest


def hash_password(password: str) -> str:
    """Create a salted PBKDF2-SHA256 hash for local backend configuration."""
    if len(password) < 12:
        raise ValueError("Prototype passwords must contain at least 12 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}"
        f"${_b64encode(salt)}${_b64encode(digest)}"
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    iterations, salt, expected_digest = _parse_password_hash(encoded_hash)
    actual_digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def load_kyc_auth_configuration() -> KycAuthConfiguration:
    """Load accounts and signing secret from backend-only environment variables."""
    secret = os.getenv(KYC_AUTH_SECRET_ENV, "")
    raw_accounts = os.getenv(KYC_AUTH_USERS_ENV, "")
    if len(secret.encode("utf-8")) < _MIN_SECRET_BYTES or not raw_accounts.strip():
        raise KycAuthConfigurationError(
            "KYC authentication is not configured on this backend."
        )
    try:
        entries = json.loads(raw_accounts)
    except json.JSONDecodeError as error:
        raise KycAuthConfigurationError(
            "KYC authentication configuration is invalid."
        ) from error
    if not isinstance(entries, list) or not entries:
        raise KycAuthConfigurationError(
            "KYC authentication configuration is invalid."
        )

    accounts: dict[str, KycAuthAccount] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise KycAuthConfigurationError(
                "KYC authentication configuration is invalid."
            )
        username = entry.get("username")
        role = entry.get("role")
        password_hash = entry.get("password_hash")
        applicant_ids = entry.get("applicant_ids", [])
        if (
            not isinstance(username, str)
            or not _USERNAME_PATTERN.fullmatch(username)
            or not isinstance(role, str)
            or role not in {"CUSTOMER", "REVIEWER"}
            or not isinstance(password_hash, str)
            or not isinstance(applicant_ids, list)
            or any(
                not isinstance(applicant_id, str)
                or not _APPLICANT_ID_PATTERN.fullmatch(applicant_id)
                for applicant_id in applicant_ids
            )
            or (role == "CUSTOMER" and not applicant_ids)
            or username in accounts
        ):
            raise KycAuthConfigurationError(
                "KYC authentication configuration is invalid."
            )
        _parse_password_hash(password_hash)
        accounts[username] = KycAuthAccount(
            username=username,
            role=role,
            password_hash=password_hash,
            applicant_ids=frozenset(applicant_ids),
        )
    if not any(account.role == "CUSTOMER" for account in accounts.values()) or not any(
        account.role == "REVIEWER" for account in accounts.values()
    ):
        raise KycAuthConfigurationError(
            "KYC authentication requires configured customer and reviewer accounts."
        )
    return KycAuthConfiguration(secret=secret.encode("utf-8"), accounts=accounts)


def authenticate_account(
    username: str,
    password: str,
    configuration: KycAuthConfiguration,
) -> KycAuthAccount | None:
    account = configuration.accounts.get(username)
    if account is None or not verify_password(password, account.password_hash):
        return None
    return account


def create_session_token(
    account: KycAuthAccount,
    secret: bytes,
    *,
    now: int | None = None,
    lifetime_seconds: int = SESSION_LIFETIME_SECONDS,
) -> tuple[str, int]:
    issued_at = int(time.time()) if now is None else now
    expires_at = issued_at + lifetime_seconds
    payload = _b64encode(
        json.dumps(
            {"sub": account.username, "role": account.role, "iat": issued_at, "exp": expires_at},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    signing_input = f"v1.{payload}".encode("ascii")
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return f"v1.{payload}.{_b64encode(signature)}", expires_at


def decode_session_token(
    token: str,
    configuration: KycAuthConfiguration,
    *,
    now: int | None = None,
) -> KycPrincipal:
    try:
        version, payload, signature = token.split(".")
        signing_input = f"{version}.{payload}".encode("ascii")
        supplied_signature = _b64decode(signature)
        expected_signature = hmac.new(
            configuration.secret, signing_input, hashlib.sha256
        ).digest()
        claims = json.loads(_b64decode(payload))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as error:
        raise ValueError("The session is invalid or expired.") from error
    if version != "v1" or not hmac.compare_digest(supplied_signature, expected_signature):
        raise ValueError("The session is invalid or expired.")
    if not isinstance(claims, dict):
        raise ValueError("The session is invalid or expired.")
    username = claims.get("sub")
    role = claims.get("role")
    issued_at = claims.get("iat")
    expires_at = claims.get("exp")
    current_time = int(time.time()) if now is None else now
    account = configuration.accounts.get(username) if isinstance(username, str) else None
    if (
        account is None
        or role != account.role
        or not isinstance(issued_at, int)
        or not isinstance(expires_at, int)
        or issued_at > current_time + 60
        or expires_at <= current_time
        or expires_at <= issued_at
    ):
        raise ValueError("The session is invalid or expired.")
    return KycPrincipal(
        username=account.username,
        role=account.role,
        applicant_ids=account.applicant_ids,
        expires_at=expires_at,
    )


def get_current_kyc_principal(
    authorization: str | None = Header(default=None),
) -> KycPrincipal:
    try:
        configuration = load_kyc_auth_configuration()
    except KycAuthConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to access KYC records.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_session_token(authorization[7:], configuration)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def require_kyc_role(principal: KycPrincipal, role: KycRole) -> None:
    if principal.role != role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires the {role.lower()} role.",
        )


def require_applicant_access(principal: KycPrincipal, applicant_id: str) -> None:
    if principal.role == "CUSTOMER" and applicant_id not in principal.applicant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this applicant's KYC records.",
        )


def current_auth_configuration() -> KycAuthConfiguration:
    """Return config for the auth endpoint, using an HTTP error when misconfigured."""
    try:
        return load_kyc_auth_configuration()
    except KycAuthConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
