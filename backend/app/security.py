"""Contrasenas, hashing y emision/validacion de JWT."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(Exception):
    """Error de validacion de un token JWT."""


# --- Contrasenas -----------------------------------------------------------
def hash_password(plain_password: str) -> str:
    """Devuelve el hash bcrypt de una contrasena en texto plano."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara una contrasena con su hash bcrypt."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        # Hash corrupto o con formato inesperado: se trata como no valido.
        return False


# --- JWT -------------------------------------------------------------------
def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Genera un JWT firmado cuyo `sub` es el identificador del usuario."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": settings.app_name,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """Valida y decodifica un JWT, lanzando `TokenError` si es invalido."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except JWTError as exc:
        raise TokenError("Token invalido o expirado") from exc

    if not payload.get("sub"):
        raise TokenError("El token no contiene un sujeto valido")
    return payload
