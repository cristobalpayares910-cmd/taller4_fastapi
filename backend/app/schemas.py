"""Esquemas Pydantic: contrato de entrada/salida de la API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ---------------------------------------------------------------------------
# Autenticacion
# ---------------------------------------------------------------------------


class UserRegister(BaseModel):
    """Datos necesarios para registrar un usuario nuevo."""

    email: EmailStr = Field(..., examples=["vecina@correo.cl"])
    full_name: str = Field(..., min_length=3, max_length=120, examples=["Ana Soto"])
    password: str = Field(..., min_length=8, max_length=72, examples=["Recicla2026"])


class UserLogin(BaseModel):
    """Credenciales para el endpoint JSON de login."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)


class UserOut(BaseModel):
    """Usuario expuesto por la API (nunca incluye la contrasena)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime


class Token(BaseModel):
    """Respuesta estandar del endpoint de login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Segundos de vigencia del token")
    user: UserOut
