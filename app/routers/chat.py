import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

logger = logging.getLogger(__name__)

from ..db import get_db
from ..models import User as UserModel, ChatSession as ChatSessionModel, ChatMessage as ChatMessageModel, Question as QuestionModel, Evaluation as EvaluationModel, UserAnswer as UserAnswerModel, EvaluationResult as EvaluationResultModel, StudentFeedback as StudentFeedbackModel, EvaluatorComment as EvaluatorCommentModel
from ..schemas import ChatSession as ChatSessionSchema, ChatSessionCreate, ChatMessage as ChatMessageSchema, ChatMessageCreate, UserAnswer as UserAnswerSchema, UserSessionAnswerCreate, EvaluationResult as EvaluationResultSchema, Question as QuestionSchema
from ..deps import get_current_user, get_current_student
from sqlalchemy.sql import func
from ..services.model_service import ensure_evaluation_for_session, generate_and_save_results
from ..services.gemini_helper import generate_open_followup, generate_closing_message
from ..utils.text import normalize_text as _normalize
from ..utils.heuristics import (
    is_greeting as _is_greeting,
    is_acceptance as _is_acceptance,
    is_negative as _is_negative,
    is_substantive_signal as _is_substantive_signal,
    count_signals as _count_signals,
)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)

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
    # Normalizar anchors para preguntas de escala (fallback seguro)
    try:
        if (getattr(next_question, "question_type", None) or "").lower() == "scale":
            opts = dict(getattr(next_question, "options", {}) or {})
            anchors = dict((opts.get("anchors") or {}) or {})
            default_anchors = {
                "1": "Totalmente en desacuerdo",
                "2": "En desacuerdo",
                "3": "Neutral",
                "4": "De acuerdo",
                "5": "Totalmente de acuerdo",
            }
            changed = False
            for k, v in default_anchors.items():
                cur = str(anchors.get(str(k), "")).strip()
                if not cur or cur == str(k):
                    anchors[str(k)] = v
                    changed = True
            if opts.get("scale_min") is None:
                opts["scale_min"] = 1
                changed = True
            if opts.get("scale_max") is None:
                opts["scale_max"] = 5
                changed = True
            if changed:
                opts["anchors"] = anchors
                next_question.options = opts
    except Exception as e:
        logger.warning("Error normalizando anchors de pregunta %s: %s", next_question.question_id, e)

    # Actualizar la pregunta actual en la sesión
    session.current_question_id = next_question.question_id
    db.commit()
    
    return next_question

# NUEVO: Siguiente mensaje en modo abierto con confirmación basada en señales (gustos/habilidades/fortalezas)
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

    # Todos los mensajes (para historial de conversación)
    all_msgs = db.query(ChatMessageModel).filter(
        ChatMessageModel.session_id == session_id
    ).order_by(ChatMessageModel.message_order.asc()).all()

    # Solo mensajes del usuario
    user_msgs = [m for m in all_msgs if m.message_type == "user"]
    last_user_text = (user_msgs[-1].content if user_msgs else "").strip()

    # Historial completo para Gemini (role + content)
    conversation_history = [
        {"role": m.message_type, "content": m.content}
        for m in all_msgs
    ]

    # Los mensajes de insistencia se delegan al generador de follow-up

    # Calcular número de señales sustantivas únicas por mensaje
    # Contabilizar 5–6 señales en general (no por tipo) y permitir múltiples por mensaje
    signal_count = sum(_count_signals(m.content) for m in user_msgs)
    user_count = len(user_msgs)

    # Nombre solo en el primer turno; el cierre siempre lo usa (2 menciones totales)
    name_for_followup = current_student.full_name if user_count == 0 else None

    # Si el último mensaje es una aceptación explícita y ya hay señales mínimas, permitir cerrar
    # Evitar interceptar cuando estamos en etapa de confirmación explícita (se maneja más abajo)
    # Requiere >= 5 señales Y >= 5 mensajes para evitar cerrar cuando el usuario responde "sí"
    # a una pregunta conversacional de Gemini en interacciones tempranas
    if _is_acceptance(last_user_text) and (session.conversation_stage or "").lower() != "confirm_results":
        if signal_count >= 5 and user_count >= 5:
            session.conversation_stage = "results"
            session.last_activity = func.now()
            db.commit()
            return {"detail": "El estudiante confirmó ver resultados. Generando..."}
        else:
            # Delegar el seguimiento al generador (Gemini/fallback)
            previous_texts = [m.content for m in user_msgs]
            bot_text = generate_open_followup(previous_texts, conversation_history, name_for_followup)
            max_order = db.query(func.max(ChatMessageModel.message_order)).filter(ChatMessageModel.session_id == session_id).scalar()
            next_order = (max_order or 0) + 1
            bot_msg = ChatMessageModel(
                session_id=session_id,
                message_type="bot",
                content=bot_text,
                message_order=next_order,
            )
            db.add(bot_msg)
            session.conversation_stage = "collecting"
            session.last_activity = func.now()
            db.commit()
            db.refresh(bot_msg)
            return {"bot_message": bot_msg}

    # Si estamos esperando confirmación del estudiante
    if (session.conversation_stage or "").lower() == "confirm_results":
        if _is_acceptance(last_user_text):
            session.conversation_stage = "results"
            session.last_activity = func.now()
            db.commit()
            return {"detail": "El estudiante confirmó ver resultados. Generando..."}
        else:
            # Volver a etapa de recolección y continuar con seguimiento
            previous_texts = [m.content for m in user_msgs]
            bot_text = generate_open_followup(previous_texts, conversation_history, name_for_followup)

            max_order = db.query(func.max(ChatMessageModel.message_order)).filter(ChatMessageModel.session_id == session_id).scalar()
            next_order = (max_order or 0) + 1

            bot_msg = ChatMessageModel(
                session_id=session_id,
                message_type="bot",
                content=bot_text,
                message_order=next_order
            )
            db.add(bot_msg)
            session.conversation_stage = "collecting"
            session.last_activity = func.now()
            db.commit()
            db.refresh(bot_msg)
            return {"bot_message": bot_msg}

    # Límite duro de 6 mensajes del usuario: forzar confirmación
    if user_count >= 6 and (session.conversation_stage or "").lower() != "results":
        user_texts = [m.content for m in user_msgs]
        confirm_text_limit = generate_closing_message(user_texts, current_student.full_name)

        max_order = db.query(func.max(ChatMessageModel.message_order)).filter(ChatMessageModel.session_id == session_id).scalar()
        next_order = (max_order or 0) + 1

        bot_msg = ChatMessageModel(
            session_id=session_id,
            message_type="bot",
            content=confirm_text_limit,
            message_order=next_order
        )
        db.add(bot_msg)
        session.conversation_stage = "confirm_results"
        session.last_activity = func.now()
        db.commit()
        db.refresh(bot_msg)
        return {"bot_message": bot_msg, "awaiting_confirmation": True}

    # Aviso proactivo al 5.º mensaje: pedir última señal antes de mostrar resultados
    if user_count == 5 and (session.conversation_stage or "").lower() != "confirm_results":
        user_texts = [m.content for m in user_msgs]
        confirm_text_5 = generate_closing_message(user_texts, current_student.full_name)

        max_order = db.query(func.max(ChatMessageModel.message_order)).filter(ChatMessageModel.session_id == session_id).scalar()
        next_order = (max_order or 0) + 1

        bot_msg = ChatMessageModel(
            session_id=session_id,
            message_type="bot",
            content=confirm_text_5,
            message_order=next_order
        )
        db.add(bot_msg)
        session.conversation_stage = "confirm_results"
        session.last_activity = func.now()
        db.commit()
        db.refresh(bot_msg)
        return {"bot_message": bot_msg, "awaiting_confirmation": True}

    # Si ya hay suficientes señales sustantivas (>=5) -> pedir confirmación para mostrar resultados
    # También requiere al menos 5 mensajes para no cerrar prematuramente en interacciones tempranas
    if signal_count >= 5 and user_count >= 5:
        user_texts = [m.content for m in user_msgs]
        confirm_text = generate_closing_message(user_texts, current_student.full_name)

        max_order = db.query(func.max(ChatMessageModel.message_order)).filter(ChatMessageModel.session_id == session_id).scalar()
        next_order = (max_order or 0) + 1

        bot_msg = ChatMessageModel(
            session_id=session_id,
            message_type="bot",
            content=confirm_text,
            message_order=next_order
        )
        db.add(bot_msg)
        session.conversation_stage = "confirm_results"
        session.last_activity = func.now()
        db.commit()
        db.refresh(bot_msg)
        return {"bot_message": bot_msg, "awaiting_confirmation": True}

    # Caso general: generar pregunta de seguimiento con Gemini (o fallback)
    previous_texts = [m.content for m in user_msgs]
    bot_text = generate_open_followup(previous_texts, conversation_history, name_for_followup)

    max_order = db.query(func.max(ChatMessageModel.message_order)).filter(ChatMessageModel.session_id == session_id).scalar()
    next_order = (max_order or 0) + 1

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

    return {"bot_message": bot_msg}

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
    # Usar el resultado más reciente por fecha de generación
    result = (
        db.query(EvaluationResultModel)
        .filter(EvaluationResultModel.evaluation_id == evaluation.evaluation_id)
        .order_by(EvaluationResultModel.generated_at.desc())
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Resultados no generados aún")
    # Sanitizar métricas para cumplir el esquema (valores numéricos)
    metrics = result.metrics or {}
    mv = metrics.get("model_version")
    sm = metrics.get("source_mode")
    def _to_float(x):
        try:
            return float(x)
        except Exception:
            return None
    mv_num = _to_float(mv)
    if mv_num is None:
        # Normalizar valores históricos ('v6', '6', etc.) a 6.0
        mv_num = 6.0
    metrics["model_version"] = mv_num
    sm_num = _to_float(sm)
    if sm_num is None:
        # guided -> 0.0; open -> 1.0 (por defecto guided)
        try:
            sm_str = str(sm or "guided").lower()
        except Exception:
            sm_str = "guided"
        sm_num = 1.0 if sm_str == "open" else 0.0
    metrics["source_mode"] = sm_num
    result.metrics = metrics
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