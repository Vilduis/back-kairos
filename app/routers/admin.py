from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from ..db import get_db
from ..models import User as UserModel, EvaluatorAssignment, StudentFeedback as StudentFeedbackModel
from ..schemas import User as UserSchema, UserCreate, UserUpdate, EvaluatorAssignment as EvaluatorAssignmentSchema, StudentFeedback as StudentFeedbackSchema
from ..deps import get_current_admin, check_email_available, apply_profile_update
from ..security import get_password_hash
from ..enums import UserRole

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)


@router.get("/me", response_model=UserSchema)
def read_admin_profile(current_admin: UserModel = Depends(get_current_admin)):
    return current_admin


@router.put("/me", response_model=UserSchema)
def update_admin_profile(
    user_update: UserUpdate,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    apply_profile_update(current_admin, user_update.full_name, user_update.email, user_update.educational_institution, db)
    db.commit()
    db.refresh(current_admin)
    return current_admin


@router.post("/users", response_model=UserSchema)
def create_user(
    user: UserCreate,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if user.role not in [UserRole.EVALUATOR, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol no válido. Debe ser 'evaluator' o 'admin'")
    check_email_available(user.email, db)
    db_user = UserModel(
        full_name=user.full_name,
        email=user.email.lower(),
        password_hash=get_password_hash(user.password),
        educational_institution=user.educational_institution,
        role=user.role,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/users", response_model=List[UserSchema])
def get_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    q: Optional[str] = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
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
    if order_dir.lower() == "asc":
        query = query.order_by(column.asc())
    else:
        query = query.order_by(column.desc())

    return query.offset(skip).limit(limit).all()


@router.get("/users/{user_id}", response_model=UserSchema)
def get_user(
    user_id: int,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return user


@router.put("/users/{user_id}", response_model=UserSchema)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    apply_profile_update(user, user_update.full_name, user_update.email, user_update.educational_institution, db)

    if user_update.role is not None:
        if user_update.role not in [UserRole.STUDENT, UserRole.EVALUATOR, UserRole.ADMIN]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol no válido")
        user.role = user_update.role
    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def deactivate_user(
    user_id: int,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if user.user_id == current_admin.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes desactivar tu propia cuenta")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario ya se encuentra desactivado")
    user.is_active = False
    db.commit()
    return {"detail": "Usuario desactivado correctamente. Sus datos han sido conservados."}


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
def assign_student_to_evaluator(
    student_id: int,
    evaluator_id: int,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    student = db.query(UserModel).filter(UserModel.user_id == student_id, UserModel.role == UserRole.STUDENT).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado")
    evaluator = db.query(UserModel).filter(UserModel.user_id == evaluator_id, UserModel.role == UserRole.EVALUATOR).first()
    if not evaluator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluador no encontrado")
    existing = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.student_id == student_id,
        EvaluatorAssignment.evaluator_id == evaluator_id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esta asignación ya existe")
    db.add(EvaluatorAssignment(student_id=student_id, evaluator_id=evaluator_id))
    db.commit()
    return {"detail": "Asignación creada exitosamente"}


@router.get("/assignments", response_model=List[EvaluatorAssignmentSchema])
def list_assignments(
    evaluator_id: Optional[int] = None,
    student_id: Optional[int] = None,
    assignment_status: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.student_id.isnot(None),
        EvaluatorAssignment.evaluator_id.isnot(None),
    )
    if evaluator_id is not None:
        query = query.filter(EvaluatorAssignment.evaluator_id == evaluator_id)
    if student_id is not None:
        query = query.filter(EvaluatorAssignment.student_id == student_id)
    if assignment_status is not None:
        if assignment_status not in ["active", "inactive"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado no válido")
        query = query.filter(EvaluatorAssignment.status == assignment_status)
    return query.offset(skip).limit(limit).all()


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: int,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    assignment = db.query(EvaluatorAssignment).filter(EvaluatorAssignment.assignment_id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asignación no encontrada")
    db.delete(assignment)
    db.commit()


@router.get("/feedback", response_model=List[StudentFeedbackSchema])
def list_student_feedback(
    student_id: Optional[int] = None,
    evaluation_id: Optional[int] = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    order_dir: str = "desc",
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(StudentFeedbackModel).filter(StudentFeedbackModel.user_id.isnot(None))
    if student_id is not None:
        query = query.filter(StudentFeedbackModel.user_id == student_id)
    if evaluation_id is not None:
        query = query.filter(StudentFeedbackModel.evaluation_id == evaluation_id)
    if order_dir.lower() == "asc":
        query = query.order_by(StudentFeedbackModel.created_at.asc())
    else:
        query = query.order_by(StudentFeedbackModel.created_at.desc())
    return query.offset(skip).limit(limit).all()


@router.delete("/feedback/orphans")
def delete_orphan_feedback(
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(StudentFeedbackModel).filter(StudentFeedbackModel.user_id.is_(None))
    deleted = query.count()
    if deleted == 0:
        return {"detail": "No hay feedback huérfano para eliminar", "deleted": 0}
    query.delete(synchronize_session=False)
    db.commit()
    return {"detail": "Feedback huérfano eliminado correctamente", "deleted": deleted}
