from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

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
    UserUpdate,
    Evaluation as EvaluationSchema,
    EvaluationResult as EvaluationResultSchema,
    EvaluatorComment as EvaluatorCommentSchema,
    EvaluatorCommentBase,
)
from ..deps import get_current_evaluator, apply_profile_update
from ..enums import UserRole

router = APIRouter(
    prefix="/evaluator",
    tags=["evaluator"],
    responses={404: {"description": "Not found"}},
)


@router.get("/me", response_model=UserSchema)
def read_evaluator_profile(current_evaluator: UserModel = Depends(get_current_evaluator)):
    return current_evaluator


@router.put("/me", response_model=UserSchema)
def update_evaluator_profile(
    user_update: UserUpdate,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db),
):
    apply_profile_update(current_evaluator, user_update.full_name, user_update.email, user_update.educational_institution, db)
    db.commit()
    db.refresh(current_evaluator)
    return current_evaluator


@router.get("/assignments", response_model=List[UserSchema])
def get_assigned_students(
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db),
):
    assignments = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == current_evaluator.user_id
    ).all()
    student_ids = [a.student_id for a in assignments]
    return db.query(UserModel).filter(
        UserModel.user_id.in_(student_ids),
        UserModel.role == UserRole.STUDENT,
    ).all()


def _require_student_assigned(evaluator_id: int, student_id: int, db: Session) -> None:
    assignment = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == evaluator_id,
        EvaluatorAssignment.student_id == student_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Este estudiante no está asignado a ti")


@router.get("/students/{student_id}/evaluations", response_model=List[EvaluationSchema])
def get_student_evaluations(
    student_id: int,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db),
):
    _require_student_assigned(current_evaluator.user_id, student_id, db)
    return db.query(EvaluationModel).filter(EvaluationModel.user_id == student_id).all()


@router.get("/evaluations/{evaluation_id}/results", response_model=EvaluationResultSchema)
def get_evaluation_results(
    evaluation_id: int,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db),
):
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluación no encontrada")
    _require_student_assigned(current_evaluator.user_id, evaluation.user_id, db)
    results = db.query(EvaluationResultModel).filter(
        EvaluationResultModel.evaluation_id == evaluation_id
    ).first()
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resultados no encontrados")
    return results


@router.get("/assigned/results", response_model=List[EvaluationResultSchema])
def list_assigned_results(
    skip: int = 0,
    limit: int = 100,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db),
):
    assignments = db.query(EvaluatorAssignment).filter(
        EvaluatorAssignment.evaluator_id == current_evaluator.user_id
    ).all()
    student_ids = [a.student_id for a in assignments]
    if not student_ids:
        return []
    return db.query(EvaluationResultModel).join(
        EvaluationModel, EvaluationResultModel.evaluation_id == EvaluationModel.evaluation_id
    ).filter(
        EvaluationModel.user_id.in_(student_ids)
    ).order_by(EvaluationModel.completed_at.desc()).offset(skip).limit(limit).all()


@router.get("/students/{student_id}/results", response_model=List[EvaluationResultSchema])
def get_student_results(
    student_id: int,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db),
):
    _require_student_assigned(current_evaluator.user_id, student_id, db)
    return db.query(EvaluationResultModel).join(
        EvaluationModel, EvaluationResultModel.evaluation_id == EvaluationModel.evaluation_id
    ).filter(
        EvaluationModel.user_id == student_id
    ).order_by(EvaluationModel.completed_at.desc()).all()


def _require_evaluation_access(evaluator_id: int, evaluation_id: int, db: Session) -> EvaluationModel:
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluación no encontrada")
    _require_student_assigned(evaluator_id, evaluation.user_id, db)
    return evaluation


@router.post("/evaluations/{evaluation_id}/comments", response_model=EvaluatorCommentSchema)
def add_evaluation_comment(
    evaluation_id: int,
    payload: EvaluatorCommentBase,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db),
):
    _require_evaluation_access(current_evaluator.user_id, evaluation_id, db)
    comment = EvaluatorCommentModel(
        evaluation_id=evaluation_id,
        evaluator_id=current_evaluator.user_id,
        comment_text=payload.comment_text,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/evaluations/{evaluation_id}/comments", response_model=List[EvaluatorCommentSchema])
def list_evaluation_comments(
    evaluation_id: int,
    current_evaluator: UserModel = Depends(get_current_evaluator),
    db: Session = Depends(get_db),
):
    _require_evaluation_access(current_evaluator.user_id, evaluation_id, db)
    return db.query(EvaluatorCommentModel).filter(
        EvaluatorCommentModel.evaluation_id == evaluation_id
    ).order_by(EvaluatorCommentModel.created_at.desc()).all()
