"""Endpoints de autenticacion: registro, login y perfil."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import Token, UserLogin, UserOut, UserRegister
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Autenticacion"])


def _authenticate(db: Session, email: str, password: str) -> User:
    """Valida credenciales y devuelve el usuario, o lanza 401."""
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contrasena incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta deshabilitada",
        )
    return user


def _build_token(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id),
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un usuario nuevo",
    responses={409: {"description": "El correo ya esta registrado"}},
)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> UserOut:
    """Crea la cuenta. La contrasena se almacena unicamente como hash bcrypt."""
    exists = db.scalar(
        select(User).where(func.lower(User.email) == payload.email.lower())
    )
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya esta registrado",
        )

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        # El primer usuario registrado queda como administrador.
        is_admin=db.scalar(select(func.count(User.id))) == 0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesion",
    description=(
        "Acepta `application/x-www-form-urlencoded` (compatible con el boton "
        "**Authorize** de Swagger) o JSON con `email` y `password`."
    ),
)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Devuelve un JWT de acceso junto con los datos del usuario."""
    # OAuth2PasswordRequestForm usa el campo `username`: se acepta el correo.
    user = _authenticate(db, form.username, form.password)
    return _build_token(user)


@router.post(
    "/login/json",
    response_model=Token,
    summary="Iniciar sesion (JSON)",
)
def login_json(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Variante JSON del login, pensada para clientes que no usan formularios."""
    user = _authenticate(db, payload.email, payload.password)
    return _build_token(user)


@router.get("/me", response_model=UserOut, summary="Perfil del usuario actual")
def read_me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Devuelve el usuario asociado al token enviado en `Authorization`."""
    return UserOut.model_validate(current_user)
