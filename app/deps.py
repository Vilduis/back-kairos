from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import Optional

from .db import get_db
from . import models
from . import security
from .enums import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    email = security.verify_token(token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de autenticación inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(models.User).filter(func.lower(models.User.email) == email.lower()).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requieren privilegios de administrador")
    return current_user


def get_current_evaluator(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != UserRole.EVALUATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requieren privilegios de evaluador")
    return current_user


def get_current_student(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso solo para estudiantes")
    return current_user


def check_email_available(email: str, db: Session, exclude_user_id: Optional[int] = None) -> None:
    query = db.query(models.User).filter(func.lower(models.User.email) == email.lower())
    if exclude_user_id is not None:
        query = query.filter(models.User.user_id != exclude_user_id)
    if query.first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email ya registrado")


def find_reactivatable_user(email: str, db: Session) -> Optional[models.User]:
    """Resuelve un email para registro respetando el borrado lógico.

    - Devuelve el usuario INACTIVO dueño del email (candidato a reactivación).
    - Lanza 400 si el email pertenece a un usuario ACTIVO.
    - Devuelve None si el email está libre (registro nuevo).
    """
    user = db.query(models.User).filter(func.lower(models.User.email) == email.lower()).first()
    if user is None:
        return None
    if user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email ya registrado")
    return user


def apply_profile_update(user: models.User, full_name, email, educational_institution, db: Session) -> None:
    if full_name is not None:
        user.full_name = full_name
    if email is not None:
        check_email_available(email, db, exclude_user_id=user.user_id)
        user.email = email.lower()
    if educational_institution is not None:
        user.educational_institution = educational_institution
