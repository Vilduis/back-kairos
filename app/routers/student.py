from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List

from ..db import get_db
from ..models import User as UserModel, Evaluation as EvaluationModel, EvaluationResult as EvaluationResultModel, StudentFeedback as StudentFeedbackModel
from ..schemas import User as UserSchema, UserCreate, UserUpdate, Evaluation as EvaluationSchema, EvaluationResult as EvaluationResultSchema, StudentFeedbackSubmit, StudentFeedback as StudentFeedbackSchema
from ..deps import get_current_user

router = APIRouter(
    prefix="/students",
    tags=["students"],
    responses={404: {"description": "Not found"}},
)

# Obtener perfil del estudiante actual
@router.get("/me", response_model=UserSchema)
def read_student_profile(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Acceso solo para estudiantes")
    return current_user

# Actualizar perfil del estudiante
@router.put("/me", response_model=UserSchema)
def update_student_profile(
    user_update: UserUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Acceso solo para estudiantes")
    
    # Actualizar campos
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    if user_update.email is not None:
        # Verificar que el email no esté en uso
        # Comprobar colisión de email sin sensibilidad a mayúsculas/minúsculas
        existing_user = db.query(UserModel).filter(func.lower(UserModel.email) == user_update.email.lower()).first()
        if existing_user and existing_user.user_id != current_user.user_id:
            raise HTTPException(status_code=400, detail="Email ya está en uso")
        current_user.email = user_update.email.lower()
    if user_update.educational_institution is not None:
        current_user.educational_institution = user_update.educational_institution
    
    db.commit()
    db.refresh(current_user)
    return current_user

# Listar mis evaluaciones
@router.get("/me/evaluations", response_model=List[EvaluationSchema])
def list_my_evaluations(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Acceso solo para estudiantes")
    evaluations = db.query(EvaluationModel).filter(EvaluationModel.user_id == current_user.user_id).order_by(EvaluationModel.started_at.desc()).all()
    return evaluations

# Ver resultados de una evaluación propia
@router.get("/evaluations/{evaluation_id}/results", response_model=EvaluationResultSchema)
def get_my_evaluation_results(
    evaluation_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id, EvaluationModel.user_id == current_user.user_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    result = db.query(EvaluationResultModel).filter(EvaluationResultModel.evaluation_id == evaluation_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Resultados no generados aún")
    return result

# Enviar feedback sobre recomendaciones
@router.post("/evaluations/{evaluation_id}/feedback", response_model=StudentFeedbackSchema)
def submit_feedback(
    evaluation_id: int,
    payload: StudentFeedbackSubmit,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Acceso solo para estudiantes")
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id, EvaluationModel.user_id == current_user.user_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
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

# Obtener feedback del estudiante para una evaluación (último registrado)
@router.get("/evaluations/{evaluation_id}/feedback", response_model=StudentFeedbackSchema)
def get_my_feedback(
    evaluation_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Acceso solo para estudiantes")
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id, EvaluationModel.user_id == current_user.user_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    feedback = db.query(StudentFeedbackModel).filter(
        StudentFeedbackModel.evaluation_id == evaluation_id,
        StudentFeedbackModel.user_id == current_user.user_id,
    ).order_by(StudentFeedbackModel.created_at.desc()).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback no encontrado")
    return feedback