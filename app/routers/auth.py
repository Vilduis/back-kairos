import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from datetime import datetime, timedelta, timezone
import secrets

logger = logging.getLogger(__name__)

from ..db import get_db
from ..models import User as UserModel, PasswordReset as PasswordResetModel
from ..schemas import User as UserSchema, UserCreate, TokenWithUser, PasswordResetRequest, PasswordResetConfirm
from ..security import verify_password, get_password_hash, create_access_token
from ..deps import get_current_user, find_reactivatable_user
from ..config import settings
from ..services.email_service import send_password_reset_email
from ..enums import UserRole

router = APIRouter(
    tags=["authentication"],
    responses={404: {"description": "Not found"}},
)


@router.get("/me", response_model=UserSchema)
def read_me(current_user: UserModel = Depends(get_current_user)):
    return current_user


@router.post("/token", response_model=TokenWithUser)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(func.lower(UserModel.email) == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    access_token = create_access_token(data={"sub": user.email.lower()})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
        },
    }


@router.post("/signup", response_model=UserSchema)
def create_student(user: UserCreate, db: Session = Depends(get_db)):
    # Si el email pertenece a una cuenta dada de baja (borrado lógico), se reactiva
    # en lugar de bloquear el registro. Si pertenece a una cuenta activa, lanza 400.
    existing = find_reactivatable_user(user.email, db)
    if existing:
        existing.full_name = user.full_name
        existing.password_hash = get_password_hash(user.password)
        existing.educational_institution = user.educational_institution
        existing.role = UserRole.STUDENT
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    db_user = UserModel(
        full_name=user.full_name,
        email=user.email.lower(),
        password_hash=get_password_hash(user.password),
        educational_institution=user.educational_institution,
        role=UserRole.STUDENT,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(func.lower(UserModel.email) == payload.email.lower()).first()
    if user:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
        db.add(PasswordResetModel(user_id=user.user_id, token=token, expires_at=expires_at))
        db.commit()
        try:
            send_password_reset_email(user.email, token)
        except Exception as e:
            logger.error("Error enviando email de reset a %s: %s", user.email, e)
        if settings.DEBUG:
            logger.debug("Password reset token for %s: %s", user.email, token)
    return {"detail": "Si el correo existe, se ha enviado un enlace"}


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    reset = db.query(PasswordResetModel).filter(PasswordResetModel.token == payload.token).first()
    if not reset:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    if reset.expires_at < datetime.now(timezone.utc):
        db.delete(reset)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token expirado")
    user = db.query(UserModel).filter(UserModel.user_id == reset.user_id).first()
    if not user:
        db.delete(reset)
        db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    user.password_hash = get_password_hash(payload.new_password)
    db.delete(reset)
    db.add(user)
    db.commit()
    return {"detail": "Contraseña actualizada"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: UserModel = Depends(get_current_user)):
    return
