from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from ..db import get_db
from ..models import User as UserModel, ChatSession as ChatSessionModel, ChatMessage as ChatMessageModel, Question as QuestionModel, Evaluation as EvaluationModel, UserAnswer as UserAnswerModel, EvaluationResult as EvaluationResultModel, StudentFeedback as StudentFeedbackModel, EvaluatorComment as EvaluatorCommentModel
from ..schemas import ChatSession as ChatSessionSchema, ChatSessionCreate, ChatMessage as ChatMessageSchema, ChatMessageCreate, UserAnswer as UserAnswerSchema, UserSessionAnswerCreate, EvaluationResult as EvaluationResultSchema, Question as QuestionSchema
from ..deps import get_current_user
from sqlalchemy.sql import func
from ..services.model_service import ensure_evaluation_for_session, generate_and_save_results
from ..services.gemini_helper import generate_open_followup

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)

# Verificar que el usuario es estudiante
def get_current_student(current_user: UserModel = Depends(get_current_user)):
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso solo para estudiantes"
        )
    return current_user

# Crear una nueva sesión de chat
@router.post("/sessions", response_model=ChatSessionSchema)
def create_chat_session(
    chat_session: ChatSessionCreate,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    db_chat_session = ChatSessionModel(
        user_id=current_student.user_id,
        chat_mode=chat_session.chat_mode,
        conversation_stage=chat_session.conversation_stage or "welcome"
    )
    db.add(db_chat_session)
    db.commit()
    db.refresh(db_chat_session)
    return db_chat_session

# Obtener sesiones de chat del estudiante
@router.get("/sessions", response_model=List[ChatSessionSchema])
def get_chat_sessions(
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSessionModel).filter(
        ChatSessionModel.user_id == current_student.user_id
    ).all()
    return sessions

# Obtener una sesión de chat específica
@router.get("/sessions/{session_id}", response_model=ChatSessionSchema)
def get_chat_session(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSessionModel).filter(
        ChatSessionModel.session_id == session_id,
        ChatSessionModel.user_id == current_student.user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de chat no encontrada")
    
    return session

# Enviar un mensaje en una sesión de chat
@router.post("/messages", response_model=ChatMessageSchema)
def create_chat_message(
    chat_message: ChatMessageCreate,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    # Verificar que la sesión existe y pertenece al estudiante
    session = db.query(ChatSessionModel).filter(
        ChatSessionModel.session_id == chat_message.session_id,
        ChatSessionModel.user_id == current_student.user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de chat no encontrada")
    
    # Crear el mensaje
    db_chat_message = ChatMessageModel(
        session_id=chat_message.session_id,
        message_type=chat_message.message_type,
        content=chat_message.content,
        message_order=chat_message.message_order
    )
    db.add(db_chat_message)
    
    # Actualizar la última actividad de la sesión
    session.last_activity = func.now()
    
    db.commit()
    db.refresh(db_chat_message)
    return db_chat_message

# Obtener mensajes de una sesión de chat
@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageSchema])
def get_chat_messages(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    # Verificar que la sesión existe y pertenece al estudiante
    session = db.query(ChatSessionModel).filter(
        ChatSessionModel.session_id == session_id,
        ChatSessionModel.user_id == current_student.user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de chat no encontrada")
    
    # Obtener mensajes ordenados por orden de mensaje
    messages = db.query(ChatMessageModel).filter(
        ChatMessageModel.session_id == session_id
    ).order_by(ChatMessageModel.message_order).all()
    
    return messages

# Obtener la siguiente pregunta en modo guiado
@router.get("/sessions/{session_id}/next-question", response_model=QuestionSchema)
def get_next_question(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    # Verificar que la sesión existe y pertenece al estudiante
    session = db.query(ChatSessionModel).filter(
        ChatSessionModel.session_id == session_id,
        ChatSessionModel.user_id == current_student.user_id,
        ChatSessionModel.chat_mode == "guided"
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de chat guiado no encontrada")
    
    # Obtener la siguiente pregunta por display_order y modo compatible
    if session.current_question_id:
        current_q = db.query(QuestionModel).filter(QuestionModel.question_id == session.current_question_id).first()
        next_question = db.query(QuestionModel).filter(
            QuestionModel.display_order > (current_q.display_order or 0),
            QuestionModel.compatible_modes.in_(["guided", "both"])
        ).order_by(QuestionModel.display_order.asc()).first()
    else:
        next_question = db.query(QuestionModel).filter(
            QuestionModel.compatible_modes.in_(["guided", "both"])
        ).order_by(QuestionModel.display_order.asc()).first()
    
    if not next_question:
        raise HTTPException(status_code=404, detail="No hay preguntas disponibles")
    
    # Actualizar la pregunta actual en la sesión
    session.current_question_id = next_question.question_id
    db.commit()
    
    return next_question

# NUEVO: Siguiente mensaje en modo abierto (3 interacciones con Gemini)
@router.post("/sessions/{session_id}/open/next")
def get_open_next(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    # Validar la sesión y modo
    session = db.query(ChatSessionModel).filter(
        ChatSessionModel.session_id == session_id,
        ChatSessionModel.user_id == current_student.user_id,
        ChatSessionModel.chat_mode == "open"
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de chat abierto no encontrada")

    # Contar mensajes del usuario
    user_msgs = db.query(ChatMessageModel).filter(
        ChatMessageModel.session_id == session_id,
        ChatMessageModel.message_type == "user"
    ).order_by(ChatMessageModel.message_order.asc()).all()
    user_count = len(user_msgs)

    # Si ya hay 3 mensajes del usuario -> generar perfil y resultados
    if user_count >= 3:
        evaluation = ensure_evaluation_for_session(db, current_student.user_id, session_id)
        result = generate_and_save_results(db, evaluation.evaluation_id)
        evaluation.status = "completed"
        evaluation.completed_at = func.now()
        # Marcar sesión de chat como completada y mover a resultados
        session.status = "completed"
        session.conversation_stage = "results"
        session.last_activity = func.now()
        db.commit()
        return {"detail": "Conversación abierta completada", "evaluation_id": evaluation.evaluation_id, "result_id": result.result_id}

    # Generar pregunta de seguimiento con Gemini (o fallback)
    previous_texts = [m.content for m in user_msgs]
    bot_text = generate_open_followup(previous_texts)

    # Calcular el próximo orden
    max_order = db.query(func.max(ChatMessageModel.message_order)).filter(ChatMessageModel.session_id == session_id).scalar()
    next_order = (max_order or 0) + 1

    # Guardar mensaje del bot
    bot_msg = ChatMessageModel(
        session_id=session_id,
        message_type="bot",
        content=bot_text,
        message_order=next_order
    )
    db.add(bot_msg)
    session.last_activity = func.now()
    db.commit()
    db.refresh(bot_msg)

    return {"bot_message": bot_msg, "remaining_user_interactions": 3 - user_count}

# Mensaje de bienvenida (opcional desde backend)
@router.get("/welcome")
def get_welcome_message():
    return {"message": "¡Bienvenido! Selecciona un modo para comenzar: guiado u abierto."}

# Registrar respuesta del usuario (texto libre u opción múltiple)
@router.post("/sessions/{session_id}/answers", response_model=UserAnswerSchema)
def submit_answer(
    session_id: int,
    payload: UserSessionAnswerCreate,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    # Validar sesión del estudiante
    session = db.query(ChatSessionModel).filter(
        ChatSessionModel.session_id == session_id,
        ChatSessionModel.user_id == current_student.user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de chat no encontrada")

    # Asegurar evaluación
    evaluation = ensure_evaluation_for_session(db, current_student.user_id, session_id)

    # Crear respuesta
    db_answer = UserAnswerModel(
        evaluation_id=evaluation.evaluation_id,
        question_id=payload.question_id,
        answer_text=getattr(payload, "answer_text", None),
        selected_options=getattr(payload, "selected_options", None),
    )
    db.add(db_answer)

    # Actualizar actividad
    session.last_activity = func.now()
    db.commit()
    db.refresh(db_answer)
    return db_answer

# Completar evaluación y generar resultados (RIASEC + carreras)
@router.post("/sessions/{session_id}/complete")
def complete_evaluation(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSessionModel).filter(
        ChatSessionModel.session_id == session_id,
        ChatSessionModel.user_id == current_student.user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de chat no encontrada")

    evaluation = ensure_evaluation_for_session(db, current_student.user_id, session_id)
    # Generar y guardar resultados
    result = generate_and_save_results(db, evaluation.evaluation_id)
    # Marcar evaluación como completada
    evaluation.status = "completed"
    evaluation.completed_at = func.now()
    # Marcar sesión como completada para que el frontend muestre resultados
    session.status = "completed"
    session.conversation_stage = "results"
    session.last_activity = func.now()
    db.commit()
    return {"detail": "Evaluación completada", "evaluation_id": evaluation.evaluation_id, "result_id": result.result_id}

# Obtener resultados de una sesión
@router.get("/sessions/{session_id}/results", response_model=EvaluationResultSchema)
def get_session_results(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.session_id == session_id).first()
    if not evaluation or evaluation.user_id != current_student.user_id:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    result = db.query(EvaluationResultModel).filter(EvaluationResultModel.evaluation_id == evaluation.evaluation_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Resultados no generados aún")
    return result


# Eliminar sesión de chat y todo lo relacionado (cascada manual)
@router.delete("/sessions/{session_id}")
def delete_chat_session(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSessionModel).filter(
        ChatSessionModel.session_id == session_id,
        ChatSessionModel.user_id == current_student.user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de chat no encontrada")

    # Borrar mensajes
    db.query(ChatMessageModel).filter(ChatMessageModel.session_id == session_id).delete(synchronize_session=False)

    # Borrar evaluación y dependencias si existe
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.session_id == session_id).first()
    if evaluation:
        db.query(UserAnswerModel).filter(UserAnswerModel.evaluation_id == evaluation.evaluation_id).delete(synchronize_session=False)
        db.query(EvaluationResultModel).filter(EvaluationResultModel.evaluation_id == evaluation.evaluation_id).delete(synchronize_session=False)
        db.query(StudentFeedbackModel).filter(StudentFeedbackModel.evaluation_id == evaluation.evaluation_id).delete(synchronize_session=False)
        db.query(EvaluatorCommentModel).filter(EvaluatorCommentModel.evaluation_id == evaluation.evaluation_id).delete(synchronize_session=False)
        db.delete(evaluation)

    # Borrar sesión
    db.delete(session)
    db.commit()
    return {"detail": "Sesión eliminada correctamente"}