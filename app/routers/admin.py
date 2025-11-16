from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import or_
from typing import List, Optional

from ..db import get_db
from ..models import User as UserModel, EvaluatorAssignment, StudentFeedback as StudentFeedbackModel
from ..schemas import User as UserSchema, UserCreate, UserUpdate, EvaluatorAssignment as EvaluatorAssignmentSchema, StudentFeedback as StudentFeedbackSchema
from ..deps import get_current_user
from ..security import get_password_hash

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)

# Verificar que el usuario es administrador
def get_current_admin(current_user: UserModel = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de administrador"
        )
    return current_user

# Obtener perfil del administrador actual
@router.get("/me", response_model=UserSchema)
def read_admin_profile(
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return current_admin

# Actualizar perfil del administrador
@router.put("/me", response_model=UserSchema)
def update_admin_profile(
    user_update: UserUpdate,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Actualizar campos permitidos
    if user_update.full_name is not None:
        current_admin.full_name = user_update.full_name
    if user_update.email is not None:
        # Verificar que el email no esté en uso
        # Comprobar colisión de email sin sensibilidad a mayúsculas/minúsculas
        existing_user = db.query(UserModel).filter(func.lower(UserModel.email) == user_update.email.lower()).first()
        if existing_user and existing_user.user_id != current_admin.user_id:
            raise HTTPException(status_code=400, detail="Email ya está en uso")
        current_admin.email = user_update.email.lower()
    if user_update.educational_institution is not None:
        current_admin.educational_institution = user_update.educational_institution

    # No permitir cambios de rol ni estado desde este endpoint
    # (user_update.role, user_update.is_active se ignoran)

    db.commit()
    db.refresh(current_admin)
    return current_admin

# Crear un nuevo evaluador o administrador
@router.post("/users", response_model=UserSchema)
def create_user(
    user: UserCreate,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Verificar si el usuario ya existe
    # Verificar si el usuario ya existe (búsqueda case-insensitive)
    db_user = db.query(UserModel).filter(func.lower(UserModel.email) == user.email.lower()).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
    # Verificar que el rol sea válido
    if user.role not in ["evaluator", "admin"]:
        raise HTTPException(status_code=400, detail="Rol no válido. Debe ser 'evaluator' o 'admin'")
    
    hashed_password = get_password_hash(user.password)
    db_user = UserModel(
        full_name=user.full_name,
        email=user.email.lower(),
        password_hash=hashed_password,
        educational_institution=user.educational_institution,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Obtener lista de usuarios
@router.get("/users", response_model=List[UserSchema])
def get_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    q: Optional[str] = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    skip: int = 0,
    limit: int = 100,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(UserModel)
    if role:
        query = query.filter(UserModel.role == role)
    if is_active is not None:
        query = query.filter(UserModel.is_active == is_active)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(UserModel.full_name.ilike(like), UserModel.email.ilike(like)))

    allowed_order_by = {
        "created_at": UserModel.created_at,
        "full_name": UserModel.full_name,
        "email": UserModel.email,
        "role": UserModel.role,
        "last_login": UserModel.last_login,
    }
    column = allowed_order_by.get(order_by, UserModel.created_at)
    direction = order_dir.lower()
    if direction == "asc":
        query = query.order_by(column.asc())
    else:
        query = query.order_by(column.desc())

    return query.offset(skip).limit(limit).all()

# Obtener un usuario específico
@router.get("/users/{user_id}", response_model=UserSchema)
def get_user(
    user_id: int,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user

# Actualizar un usuario
@router.put("/users/{user_id}", response_model=UserSchema)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Actualizar campos
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.email is not None:
        # Verificar que el email no esté en uso
        # Comprobar colisión de email sin sensibilidad a mayúsculas/minúsculas
        existing_user = db.query(UserModel).filter(func.lower(UserModel.email) == user_update.email.lower()).first()
        if existing_user and existing_user.user_id != user_id:
            raise HTTPException(status_code=400, detail="Email ya está en uso")
        user.email = user_update.email.lower()
    if user_update.educational_institution is not None:
        user.educational_institution = user_update.educational_institution
    if user_update.role is not None:
        if user_update.role not in ["student", "evaluator", "admin"]:
            raise HTTPException(status_code=400, detail="Rol no válido")
        user.role = user_update.role
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    
    db.commit()
    db.refresh(user)
    return user

# Eliminar un usuario
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Evitar que un administrador se elimine a sí mismo
    if user.user_id == current_admin.user_id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    
    db.delete(user)
    db.commit()
    return {"detail": "Usuario eliminado"}

# Asignar un estudiante a un evaluador
@router.post("/assignments", status_code=status.HTTP_201_CREATED)
def assign_student_to_evaluator(
    student_id: int,
    evaluator_id: int,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Verificar que el estudiante existe
    student = db.query(UserModel).filter(UserModel.user_id == student_id, UserModel.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    
    # Verificar que el evaluador existe
    evaluator = db.query(UserModel).filter(UserModel.user_id == evaluator_id, UserModel.role == "evaluator").first()
    if not evaluator:
        raise HTTPException(status_code=404, detail="Evaluador no encontrado")
    
    # Verificar si ya existe una asignación
    existing_assignment = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.student_id == student_id,
        EvaluatorAssignment.evaluator_id == evaluator_id
    ).first()
    
    if existing_assignment:
        raise HTTPException(status_code=400, detail="Esta asignación ya existe")
    
    # Crear la asignación
    assignment = EvaluatorAssignment(
        student_id=student_id,
        evaluator_id=evaluator_id
    )
    db.add(assignment)
    db.commit()
    
    return {"detail": "Asignación creada exitosamente"}

# Listar asignaciones con filtros
@router.get("/assignments", response_model=List[EvaluatorAssignmentSchema])
def list_assignments(
    evaluator_id: Optional[int] = None,
    student_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(EvaluatorAssignment)
    if evaluator_id is not None:
        query = query.filter(EvaluatorAssignment.evaluator_id == evaluator_id)
    if student_id is not None:
        query = query.filter(EvaluatorAssignment.student_id == student_id)
    if status is not None:
        if status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Estado no válido")
        query = query.filter(EvaluatorAssignment.status == status)

    # Sanitizar filas inválidas que rompen la validación del esquema
    query = query.filter(
        EvaluatorAssignment.student_id.isnot(None),
        EvaluatorAssignment.evaluator_id.isnot(None)
    )

    return query.offset(skip).limit(limit).all()

# Eliminar una asignación
@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: int,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    assignment = db.query(EvaluatorAssignment).filter(EvaluatorAssignment.assignment_id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    db.delete(assignment)
    db.commit()
    return {"detail": "Asignación eliminada"}

# Listar feedback de estudiantes con filtros opcionales
@router.get("/feedback", response_model=List[StudentFeedbackSchema])
def list_student_feedback(
    student_id: Optional[int] = None,
    evaluation_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    order_dir: str = "desc",
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(StudentFeedbackModel)

    # Sanitizar filas inválidas que rompen la validación del esquema (user_id nulo)
    query = query.filter(StudentFeedbackModel.user_id.isnot(None))

    if student_id is not None:
        query = query.filter(StudentFeedbackModel.user_id == student_id)
    if evaluation_id is not None:
        query = query.filter(StudentFeedbackModel.evaluation_id == evaluation_id)

    # Ordenar por fecha de creación
    if order_dir.lower() == "asc":
        query = query.order_by(StudentFeedbackModel.created_at.asc())
    else:
        query = query.order_by(StudentFeedbackModel.created_at.desc())

    return query.offset(skip).limit(limit).all()