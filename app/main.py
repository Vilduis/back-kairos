from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

from .db import get_db, engine
from .models import Base
from . import schemas
from . import security
from . import models
from .routers import auth, student, admin, evaluator, chat, recommendation
from .config import settings
from .deps import get_current_user
import logging
from .services.model_service import init_recommender_artifacts
from .db import SessionLocal
from .seeds import seed_riasec_questions, seed_default_admins

# Create tables solo en desarrollo
if settings.DEBUG:
    Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vocational Chatbot API", debug=settings.DEBUG)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Loggear las CORS origins efectivas para verificación en producción
try:
    logging.getLogger(__name__).info(f"CORS_ORIGINS configuradas: {settings.CORS_ORIGINS}")
except Exception:
    pass

# Incluir routers
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(admin.router)
app.include_router(evaluator.router)
app.include_router(chat.router)
app.include_router(recommendation.router)

# Hook de startup para ejecutar semillas en desarrollo
@app.on_event("startup")
def _startup_seed():
    # Cargar artefactos del recomendador (siempre)
    try:
        init_recommender_artifacts()
    except Exception:
        pass
    # Ejecutar semillas solo si DEBUG está activo o el flag explícito lo permite
    if not (settings.DEBUG or getattr(settings, "SEED_ON_STARTUP", False)):
        return
    try:
        db = SessionLocal()
        # Asegurar admins y preguntas guiadas
        try:
            seed_default_admins(db)
        except Exception:
            pass
        try:
            seed_riasec_questions(db)
        except Exception:
            pass
    except Exception:
        pass
    finally:
        try:
            db.close()
        except Exception:
            pass

# get_current_user se centraliza en app/deps.py

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de Kairos - Chatbot Vocacional"}

# Evaluation endpoints
@app.post("/evaluations/", response_model=schemas.Evaluation)
def create_evaluation(
    evaluation: schemas.EvaluationCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_evaluation = models.Evaluation(
        user_id=current_user.user_id,
        session_id=evaluation.session_id,
        evaluation_mode=evaluation.evaluation_mode
    )
    db.add(db_evaluation)
    db.commit()
    db.refresh(db_evaluation)
    return db_evaluation

@app.post("/user-answers/", response_model=schemas.UserAnswer)
def create_user_answer(
    user_answer: schemas.UserAnswerCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_user_answer = models.UserAnswer(
        evaluation_id=user_answer.evaluation_id,
        question_id=user_answer.question_id,
        answer_text=user_answer.answer_text,
        selected_options=user_answer.selected_options
    )
    db.add(db_user_answer)
    db.commit()
    db.refresh(db_user_answer)
    return db_user_answer

@app.post("/evaluation-results/", response_model=schemas.EvaluationResult)
def create_evaluation_result(
    result: schemas.EvaluationResultCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_result = models.EvaluationResult(
        evaluation_id=result.evaluation_id,
        riasec_scores=result.riasec_scores,
        top_careers=result.top_careers,
        metrics=result.metrics
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)