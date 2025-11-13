from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List, Optional

from ..db import get_db
from ..models import (
    User as UserModel,
    EvaluatorAssignment,
    Evaluation as EvaluationModel,
    EvaluationResult as EvaluationResultModel,
    EvaluatorComment as EvaluatorCommentModel,
)
from ..schemas import (
    User as UserSchema,
    Evaluation as EvaluationSchema,
    EvaluationResult as EvaluationResultSchema,
    EvaluatorComment as EvaluatorCommentSchema,
    EvaluatorCommentBase,
    UserUpdate,
)
from ..deps import get_current_user

router = APIRouter(
    prefix="/evaluator",
    tags=["evaluator"],
    responses={404: {"description": "Not found"}},
)

# Verificar que el usuario es evaluador
def get_current_evaluator(current_user: UserModel = Depends(get_current_user)):
    if current_user.role != "evaluator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de evaluador"
        )
    return current_user

# Obtener perfil del evaluador actual
@router.get("/me", response_model=UserSchema)
def read_evaluator_profile(
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db)
):
    return current_evaluator

# Actualizar perfil del evaluador
@router.put("/me", response_model=UserSchema)
def update_evaluator_profile(
    user_update: UserUpdate,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db)
):
    # Actualizar campos permitidos
    if user_update.full_name is not None:
        current_evaluator.full_name = user_update.full_name
    if user_update.email is not None:
        # Verificar que el email no esté en uso
        # Comprobar colisión de email sin sensibilidad a mayúsculas/minúsculas
        existing_user = db.query(UserModel).filter(func.lower(UserModel.email) == user_update.email.lower()).first()
        if existing_user and existing_user.user_id != current_evaluator.user_id:
            raise HTTPException(status_code=400, detail="Email ya está en uso")
        current_evaluator.email = user_update.email.lower()
    if user_update.educational_institution is not None:
        current_evaluator.educational_institution = user_update.educational_institution

    # No permitir cambios de rol ni estado desde este endpoint
    # (user_update.role, user_update.is_active se ignoran)

    db.commit()
    db.refresh(current_evaluator)
    return current_evaluator

# Obtener estudiantes asignados al evaluador
@router.get("/assignments", response_model=List[UserSchema])
def get_assigned_students(
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db)
):
    # Obtener IDs de estudiantes asignados
    assignments = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == current_evaluator.user_id
    ).all()

    student_ids = [assignment.student_id for assignment in assignments]

    # Obtener información de los estudiantes
    students = db.query(UserModel).filter(
        UserModel.user_id.in_(student_ids),
        UserModel.role == "student"
    ).all()

    return students

# Obtener evaluaciones de un estudiante específico
@router.get("/students/{student_id}/evaluations", response_model=List[EvaluationSchema])
def get_student_evaluations(
    student_id: int,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db)
):
    # Verificar que el estudiante está asignado a este evaluador
    assignment = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == current_evaluator.user_id,
        EvaluatorAssignment.student_id == student_id
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este estudiante no está asignado a ti"
        )

    # Obtener evaluaciones del estudiante
    evaluations = db.query(EvaluationModel).filter(
        EvaluationModel.user_id == student_id
    ).all()

    return evaluations

# Obtener resultados detallados de una evaluación
@router.get("/evaluations/{evaluation_id}/results", response_model=EvaluationResultSchema)
def get_evaluation_results(
    evaluation_id: int,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db)
):
    # Obtener la evaluación
    evaluation = db.query(EvaluationModel).filter(
        EvaluationModel.evaluation_id == evaluation_id
    ).first()

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    # Verificar que el estudiante está asignado a este evaluador
    assignment = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == current_evaluator.user_id,
        EvaluatorAssignment.student_id == evaluation.user_id
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta evaluación"
        )

    # Obtener resultados de la evaluación
    results = db.query(EvaluationResultModel).filter(
        EvaluationResultModel.evaluation_id == evaluation_id
    ).first()

    if not results:
        raise HTTPException(status_code=404, detail="Resultados no encontrados")

    return results

# Listar resultados de estudiantes asignados al evaluador
@router.get("/assigned/results", response_model=List[EvaluationResultSchema])
def list_assigned_results(
    skip: int = 0,
    limit: int = 100,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db)
):
    assignments = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == current_evaluator.user_id
    ).all()
    student_ids = [a.student_id for a in assignments]
    if not student_ids:
        return []

    results = db.query(EvaluationResultModel).join(
        EvaluationModel, EvaluationResultModel.evaluation_id == EvaluationModel.evaluation_id
    ).filter(
        EvaluationModel.user_id.in_(student_ids)
    ).order_by(EvaluationModel.completed_at.desc()).offset(skip).limit(limit).all()
    return results

# Listar resultados de un estudiante asignado específico
@router.get("/students/{student_id}/results", response_model=List[EvaluationResultSchema])
def get_student_results(
    student_id: int,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db)
):
    assignment = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == current_evaluator.user_id,
        EvaluatorAssignment.student_id == student_id
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este estudiante no está asignado a ti"
        )
    results = db.query(EvaluationResultModel).join(
        EvaluationModel, EvaluationResultModel.evaluation_id == EvaluationModel.evaluation_id
    ).filter(
        EvaluationModel.user_id == student_id
    ).order_by(EvaluationModel.completed_at.desc()).all()
    return results

# Agregar comentario del evaluador a una evaluación
@router.post("/evaluations/{evaluation_id}/comments", response_model=EvaluatorCommentSchema)
def add_evaluation_comment(
    evaluation_id: int,
    payload: EvaluatorCommentBase,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db)
):
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    assignment = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == current_evaluator.user_id,
        EvaluatorAssignment.student_id == evaluation.user_id
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta evaluación"
        )
    comment = EvaluatorCommentModel(
        evaluation_id=evaluation_id,
        evaluator_id=current_evaluator.user_id,
        comment_text=payload.comment_text,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

# Listar comentarios de una evaluación
@router.get("/evaluations/{evaluation_id}/comments", response_model=List[EvaluatorCommentSchema])
def list_evaluation_comments(
    evaluation_id: int,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db)
):
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    assignment = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == current_evaluator.user_id,
        EvaluatorAssignment.student_id == evaluation.user_id
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta evaluación"
        )
    comments = db.query(EvaluatorCommentModel).filter(EvaluatorCommentModel.evaluation_id == evaluation_id).order_by(EvaluatorCommentModel.created_at.desc()).all()
    return comments