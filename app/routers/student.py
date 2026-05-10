from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..db import get_db
from ..models import User as UserModel, Evaluation as EvaluationModel, EvaluationResult as EvaluationResultModel, StudentFeedback as StudentFeedbackModel
from ..schemas import User as UserSchema, UserUpdate, Evaluation as EvaluationSchema, EvaluationResult as EvaluationResultSchema, StudentFeedbackSubmit, StudentFeedback as StudentFeedbackSchema
from ..deps import get_current_student, apply_profile_update

router = APIRouter(
    prefix="/students",
    tags=["students"],
    responses={404: {"description": "Not found"}},
)


@router.get("/me", response_model=UserSchema)
def read_student_profile(current_user: UserModel = Depends(get_current_student)):
    return current_user


@router.put("/me", response_model=UserSchema)
def update_student_profile(
    user_update: UserUpdate,
    current_user: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    apply_profile_update(current_user, user_update.full_name, user_update.email, user_update.educational_institution, db)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/evaluations", response_model=List[EvaluationSchema])
def list_my_evaluations(
    current_user: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    return db.query(EvaluationModel).filter(
        EvaluationModel.user_id == current_user.user_id
    ).order_by(EvaluationModel.started_at.desc()).all()


@router.get("/evaluations/{evaluation_id}/results", response_model=EvaluationResultSchema)
def get_my_evaluation_results(
    evaluation_id: int,
    current_user: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    evaluation = db.query(EvaluationModel).filter(
        EvaluationModel.evaluation_id == evaluation_id,
        EvaluationModel.user_id == current_user.user_id,
    ).first()
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluación no encontrada")
    result = db.query(EvaluationResultModel).filter(
        EvaluationResultModel.evaluation_id == evaluation_id
    ).first()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resultados no generados aún")
    return result


@router.post("/evaluations/{evaluation_id}/feedback", response_model=StudentFeedbackSchema)
def submit_feedback(
    evaluation_id: int,
    payload: StudentFeedbackSubmit,
    current_user: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    evaluation = db.query(EvaluationModel).filter(
        EvaluationModel.evaluation_id == evaluation_id,
        EvaluationModel.user_id == current_user.user_id,
    ).first()
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluación no encontrada")
    feedback = StudentFeedbackModel(
        evaluation_id=evaluation_id,
        user_id=current_user.user_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/evaluations/{evaluation_id}/feedback", response_model=StudentFeedbackSchema)
def get_my_feedback(
    evaluation_id: int,
    current_user: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    evaluation = db.query(EvaluationModel).filter(
        EvaluationModel.evaluation_id == evaluation_id,
        EvaluationModel.user_id == current_user.user_id,
    ).first()
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluación no encontrada")
    feedback = db.query(StudentFeedbackModel).filter(
        StudentFeedbackModel.evaluation_id == evaluation_id,
        StudentFeedbackModel.user_id == current_user.user_id,
    ).order_by(StudentFeedbackModel.created_at.desc()).first()
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback no encontrado")
    return feedback
