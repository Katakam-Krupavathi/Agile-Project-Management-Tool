import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_password_hasher = PasswordHasher()
_SESSION_SALT = "agile-pm-session-v1"


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def create_session_token(user_id: str, secret_key: str, token_version: int = 0) -> str:
    serializer = URLSafeTimedSerializer(secret_key, salt=_SESSION_SALT)
    return serializer.dumps({"uid": user_id, "tv": int(token_version)})


def verify_session_token_payload(
    token: str,
    secret_key: str,
    max_age_seconds: int,
) -> tuple[str, int] | None:
    serializer = URLSafeTimedSerializer(secret_key, salt=_SESSION_SALT)
    try:
        data = serializer.loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    user_id = data.get("uid")
    token_version = data.get("tv", 0)
    if not isinstance(user_id, str) or not user_id:
        return None
    if not isinstance(token_version, int) or isinstance(token_version, bool):
        return None
    return user_id, token_version


def verify_session_token(token: str, secret_key: str, max_age_seconds: int) -> str | None:
    payload = verify_session_token_payload(token, secret_key, max_age_seconds)
    return payload[0] if payload is not None else None


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_token: str | None, header_token: str | None) -> bool:
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)
