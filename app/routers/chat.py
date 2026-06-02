import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

logger = logging.getLogger(__name__)

from ..db import get_db
from ..models import (
    User as UserModel,
    ChatSession as ChatSessionModel,
    ChatMessage as ChatMessageModel,
    Question as QuestionModel,
    Evaluation as EvaluationModel,
    UserAnswer as UserAnswerModel,
    EvaluationResult as EvaluationResultModel,
    StudentFeedback as StudentFeedbackModel,
    EvaluatorComment as EvaluatorCommentModel,
)
from ..schemas import (
    ChatSession as ChatSessionSchema,
    ChatSessionCreate,
    ChatMessage as ChatMessageSchema,
    ChatMessageCreate,
    UserAnswer as UserAnswerSchema,
    UserSessionAnswerCreate,
    EvaluationResult as EvaluationResultSchema,
    Question as QuestionSchema,
)
from ..deps import get_current_user, get_current_student
from sqlalchemy.sql import func
from ..enums import ChatMode, ConversationStage
from ..services.model_service import ensure_evaluation_for_session, generate_and_save_results
from ..services.gemini_helper import generate_open_followup, generate_closing_message
from ..utils.heuristics import (
    is_acceptance as _is_acceptance,
    is_negative as _is_negative,
    count_signals as _count_signals,
)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _get_session_or_404(
    session_id: int,
    user_id: int,
    db: Session,
    chat_mode: str = None,
    detail: str = "Sesión de chat no encontrada",
) -> ChatSessionModel:
    """Obtiene una sesión validando pertenencia al usuario. Lanza 404 si no existe."""
    filters = [
        ChatSessionModel.session_id == session_id,
        ChatSessionModel.user_id == user_id,
    ]
    if chat_mode is not None:
        filters.append(ChatSessionModel.chat_mode == chat_mode)
    session = db.query(ChatSessionModel).filter(*filters).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return session


def _next_message_order(session_id: int, db: Session) -> int:
    """Devuelve el siguiente número de orden de mensaje para la sesión."""
    max_order = db.query(func.max(ChatMessageModel.message_order)).filter(
        ChatMessageModel.session_id == session_id
    ).scalar()
    return (max_order or 0) + 1


def _save_bot_message(session_id: int, content: str, db: Session) -> ChatMessageModel:
    """Crea y persiste un mensaje de bot en la sesión."""
    msg = ChatMessageModel(
        session_id=session_id,
        message_type="bot",
        content=content,
        message_order=_next_message_order(session_id, db),
    )
    db.add(msg)
    return msg


def _normalize_question_anchors(question: QuestionModel) -> None:
    """Normaliza los anchors de escala Likert en la pregunta si están incompletos.

    Modifica el objeto ORM directamente para que los cambios sean persistidos
    junto con el commit de `current_question_id` en el mismo request.
    """
    if (getattr(question, "question_type", None) or "").lower() != "scale":
        return
    try:
        opts = dict(getattr(question, "options", {}) or {})
        anchors = dict((opts.get("anchors") or {}))
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
            question.options = opts
    except Exception as e:
        logger.warning("Error normalizando anchors de pregunta %s: %s", question.question_id, e)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=ChatSessionSchema)
def create_chat_session(
    chat_session: ChatSessionCreate,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    db_chat_session = ChatSessionModel(
        user_id=current_student.user_id,
        chat_mode=chat_session.chat_mode,
        conversation_stage=chat_session.conversation_stage or ConversationStage.WELCOME,
    )
    db.add(db_chat_session)
    db.commit()
    db.refresh(db_chat_session)
    return db_chat_session


@router.get("/sessions", response_model=List[ChatSessionSchema])
def get_chat_sessions(
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    return db.query(ChatSessionModel).filter(
        ChatSessionModel.user_id == current_student.user_id
    ).all()


@router.get("/sessions/{session_id}", response_model=ChatSessionSchema)
def get_chat_session(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    return _get_session_or_404(session_id, current_student.user_id, db)


@router.post("/messages", response_model=ChatMessageSchema)
def create_chat_message(
    chat_message: ChatMessageCreate,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(chat_message.session_id, current_student.user_id, db)

    db_chat_message = ChatMessageModel(
        session_id=chat_message.session_id,
        message_type=chat_message.message_type,
        content=chat_message.content,
        message_order=chat_message.message_order,
    )
    db.add(db_chat_message)
    session.last_activity = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_chat_message)
    return db_chat_message


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageSchema])
def get_chat_messages(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    _get_session_or_404(session_id, current_student.user_id, db)
    return db.query(ChatMessageModel).filter(
        ChatMessageModel.session_id == session_id
    ).order_by(ChatMessageModel.message_order).all()


@router.get("/sessions/{session_id}/next-question")
def get_next_question(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Devuelve la primera pregunta guiada NO respondida de la sesión.

    Es idempotente: llamarlo varias veces (al retomar, en StrictMode, etc.)
    devuelve siempre la misma pregunta pendiente hasta que se responda, en vez
    de avanzar un puntero a ciegas. Así no se saltan preguntas y se restaura el
    punto exacto donde quedó el estudiante.

    Respuesta:
      - {"completed": False, "question": {...}, "total": N, "answered": K}
      - {"completed": True,  "question": None,  "total": N, "answered": N}

    `total` y `answered` permiten mostrar el progreso "Pregunta X de N".
    """
    session = _get_session_or_404(
        session_id,
        current_student.user_id,
        db,
        chat_mode=ChatMode.GUIDED,
        detail="Sesión de chat guiado no encontrada",
    )

    # Total de preguntas guiadas configuradas
    guided_filter = QuestionModel.compatible_modes.in_([ChatMode.GUIDED, "both"])
    total_guided = db.query(QuestionModel).filter(guided_filter).count()

    # IDs ya respondidos en esta sesión (si ya existe evaluación)
    answered_ids: set[int] = set()
    evaluation = db.query(EvaluationModel).filter(
        EvaluationModel.session_id == session_id
    ).first()
    if evaluation:
        rows = db.query(UserAnswerModel.question_id).filter(
            UserAnswerModel.evaluation_id == evaluation.evaluation_id
        ).all()
        answered_ids = {qid for (qid,) in rows if qid is not None}

    answered_count = len(answered_ids)

    # Primera pregunta guiada (por display_order) que aún no esté respondida
    filters = [guided_filter]
    if answered_ids:
        filters.append(QuestionModel.question_id.notin_(answered_ids))
    next_question = db.query(QuestionModel).filter(*filters).order_by(
        QuestionModel.display_order.asc()
    ).first()

    if next_question is None:
        # 404 sólo si NO hay preguntas guiadas configuradas (error real).
        if total_guided == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay preguntas configuradas",
            )
        # Todas respondidas → el test está listo para completarse
        return {
            "completed": True,
            "question": None,
            "total": total_guided,
            "answered": total_guided,
        }

    # Normaliza anchors Likert si es necesario (persistido con el commit siguiente)
    _normalize_question_anchors(next_question)

    # current_question_id ya es sólo informativo (la lógica usa answered_ids)
    session.current_question_id = next_question.question_id
    db.commit()
    return {
        "completed": False,
        "question": QuestionSchema.model_validate(next_question),
        "total": total_guided,
        "answered": answered_count,
    }


@router.get("/guided/first-question")
def get_guided_first_question(
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Primera pregunta guiada SIN crear sesión ni persistir nada.

    Permite mostrar la primera pregunta del Test RIASEC sin ensuciar el
    historial: la sesión se crea recién cuando el estudiante responde. Misma
    forma de respuesta que `/next-question` para reutilizar el manejo en el
    frontend.
    """
    guided_filter = QuestionModel.compatible_modes.in_([ChatMode.GUIDED, "both"])
    total_guided = db.query(QuestionModel).filter(guided_filter).count()
    first_question = db.query(QuestionModel).filter(guided_filter).order_by(
        QuestionModel.display_order.asc()
    ).first()

    if first_question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay preguntas configuradas",
        )

    # Normaliza anchors Likert (persiste la corrección si la hubo)
    _normalize_question_anchors(first_question)
    db.commit()
    return {
        "completed": False,
        "question": QuestionSchema.model_validate(first_question),
        "total": total_guided,
        "answered": 0,
    }


@router.post("/sessions/{session_id}/open/next")
def get_open_next(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(
        session_id,
        current_student.user_id,
        db,
        chat_mode=ChatMode.OPEN,
        detail="Sesión de chat abierto no encontrada",
    )

    all_msgs = db.query(ChatMessageModel).filter(
        ChatMessageModel.session_id == session_id
    ).order_by(ChatMessageModel.message_order.asc()).all()

    user_msgs = [m for m in all_msgs if m.message_type == "user"]
    last_user_text = (user_msgs[-1].content if user_msgs else "").strip()
    conversation_history = [{"role": m.message_type, "content": m.content} for m in all_msgs]

    signal_count = sum(_count_signals(m.content) for m in user_msgs)
    user_count = len(user_msgs)
    name_for_followup = current_student.full_name if user_count == 0 else None

    current_stage = (session.conversation_stage or "").lower()

    # --- Rama: aceptación explícita del usuario (fuera de etapa confirm_results) ---
    if _is_acceptance(last_user_text) and current_stage != ConversationStage.CONFIRM_RESULTS:
        if signal_count >= 5 and user_count >= 7:
            session.conversation_stage = ConversationStage.RESULTS
            session.last_activity = datetime.now(timezone.utc)
            db.commit()
            return {"detail": "El estudiante confirmó ver resultados. Generando..."}
        # Aún no hay suficientes señales: continuar recolectando
        previous_texts = [m.content for m in user_msgs]
        bot_text = generate_open_followup(previous_texts, conversation_history, name_for_followup)
        bot_msg = _save_bot_message(session_id, bot_text, db)
        session.conversation_stage = ConversationStage.COLLECTING
        session.last_activity = datetime.now(timezone.utc)
        db.commit()
        db.refresh(bot_msg)
        return {"bot_message": bot_msg}

    # --- Rama: esperando confirmación del estudiante ---
    if current_stage == ConversationStage.CONFIRM_RESULTS:
        if _is_acceptance(last_user_text):
            session.conversation_stage = ConversationStage.RESULTS
            session.last_activity = datetime.now(timezone.utc)
            db.commit()
            return {"detail": "El estudiante confirmó ver resultados. Generando..."}
        # No confirmó: volver a recolectar
        previous_texts = [m.content for m in user_msgs]
        bot_text = generate_open_followup(previous_texts, conversation_history, name_for_followup)
        bot_msg = _save_bot_message(session_id, bot_text, db)
        session.conversation_stage = ConversationStage.COLLECTING
        session.last_activity = datetime.now(timezone.utc)
        db.commit()
        db.refresh(bot_msg)
        return {"bot_message": bot_msg}

    # --- Rama: límite duro de 8 mensajes → forzar confirmación ---
    if user_count >= 8 and current_stage != ConversationStage.RESULTS:
        user_texts = [m.content for m in user_msgs]
        confirm_text = generate_closing_message(user_texts, current_student.full_name)
        bot_msg = _save_bot_message(session_id, confirm_text, db)
        session.conversation_stage = ConversationStage.CONFIRM_RESULTS
        session.last_activity = datetime.now(timezone.utc)
        db.commit()
        db.refresh(bot_msg)
        return {"bot_message": bot_msg, "awaiting_confirmation": True}

    # --- Rama: aviso proactivo en el 7.º mensaje ---
    if user_count == 7 and current_stage != ConversationStage.CONFIRM_RESULTS:
        user_texts = [m.content for m in user_msgs]
        confirm_text = generate_closing_message(user_texts, current_student.full_name)
        bot_msg = _save_bot_message(session_id, confirm_text, db)
        session.conversation_stage = ConversationStage.CONFIRM_RESULTS
        session.last_activity = datetime.now(timezone.utc)
        db.commit()
        db.refresh(bot_msg)
        return {"bot_message": bot_msg, "awaiting_confirmation": True}

    # --- Rama: suficientes señales → pedir confirmación ---
    if signal_count >= 5 and user_count >= 7:
        user_texts = [m.content for m in user_msgs]
        confirm_text = generate_closing_message(user_texts, current_student.full_name)
        bot_msg = _save_bot_message(session_id, confirm_text, db)
        session.conversation_stage = ConversationStage.CONFIRM_RESULTS
        session.last_activity = datetime.now(timezone.utc)
        db.commit()
        db.refresh(bot_msg)
        return {"bot_message": bot_msg, "awaiting_confirmation": True}

    # --- Caso general: seguimiento conversacional ---
    previous_texts = [m.content for m in user_msgs]
    bot_text = generate_open_followup(previous_texts, conversation_history, name_for_followup)
    bot_msg = _save_bot_message(session_id, bot_text, db)
    session.last_activity = datetime.now(timezone.utc)
    db.commit()
    db.refresh(bot_msg)
    return {"bot_message": bot_msg}


@router.get("/welcome")
def get_welcome_message():
    return {"message": "¡Bienvenido! Selecciona un modo para comenzar: guiado u abierto."}


@router.post("/sessions/{session_id}/answers", response_model=UserAnswerSchema)
def submit_answer(
    session_id: int,
    payload: UserSessionAnswerCreate,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(session_id, current_student.user_id, db)
    evaluation = ensure_evaluation_for_session(db, current_student.user_id, session_id)

    # Si ya existe respuesta para esta pregunta, se actualiza (no se duplica).
    # Evita inflar el puntaje Likert si el estudiante responde dos veces o
    # reenvía al retomar la sesión.
    db_answer = db.query(UserAnswerModel).filter(
        UserAnswerModel.evaluation_id == evaluation.evaluation_id,
        UserAnswerModel.question_id == payload.question_id,
    ).first()
    if db_answer:
        db_answer.answer_text = payload.answer_text
        db_answer.selected_options = payload.selected_options
    else:
        db_answer = UserAnswerModel(
            evaluation_id=evaluation.evaluation_id,
            question_id=payload.question_id,
            answer_text=payload.answer_text,
            selected_options=payload.selected_options,
        )
        db.add(db_answer)
    session.last_activity = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_answer)
    return db_answer


@router.post("/sessions/{session_id}/complete")
def complete_evaluation(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(session_id, current_student.user_id, db)
    evaluation = ensure_evaluation_for_session(db, current_student.user_id, session_id)
    result = generate_and_save_results(db, evaluation.evaluation_id)
    evaluation.status = "completed"
    evaluation.completed_at = datetime.now(timezone.utc)
    session.status = "completed"
    session.conversation_stage = ConversationStage.RESULTS
    session.last_activity = datetime.now(timezone.utc)
    db.commit()
    return {
        "detail": "Evaluación completada",
        "evaluation_id": evaluation.evaluation_id,
        "result_id": result.result_id,
    }


@router.get("/sessions/{session_id}/results", response_model=EvaluationResultSchema)
def get_session_results(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.session_id == session_id).first()
    if not evaluation or evaluation.user_id != current_student.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluación no encontrada")

    result = (
        db.query(EvaluationResultModel)
        .filter(EvaluationResultModel.evaluation_id == evaluation.evaluation_id)
        .order_by(EvaluationResultModel.generated_at.desc())
        .first()
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resultados no generados aún")

    # Sanitizar métricas para cumplir el esquema sin mutar el objeto ORM
    def _to_float(x):
        try:
            return float(x)
        except Exception:
            return None

    metrics = dict(result.metrics or {})
    mv = metrics.get("model_version")
    mv_num = _to_float(mv)
    if mv_num is None:
        mv_num = 6.0  # normaliza valores históricos ('v6', '6', etc.)
    metrics["model_version"] = mv_num

    sm = metrics.get("source_mode")
    sm_num = _to_float(sm)
    if sm_num is None:
        try:
            sm_str = str(sm or ChatMode.GUIDED).lower()
        except Exception:
            sm_str = ChatMode.GUIDED
        sm_num = 1.0 if sm_str == ChatMode.OPEN else 0.0
    metrics["source_mode"] = sm_num

    # Retornar schema construido desde el dict sanitizado (no muta el ORM)
    return EvaluationResultSchema(
        result_id=result.result_id,
        evaluation_id=result.evaluation_id,
        riasec_scores=result.riasec_scores,
        top_careers=result.top_careers,
        metrics=metrics,
        generated_at=result.generated_at,
    )


@router.delete("/sessions/{session_id}")
def delete_chat_session(
    session_id: int,
    current_student: UserModel = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(session_id, current_student.user_id, db)

    db.query(ChatMessageModel).filter(
        ChatMessageModel.session_id == session_id
    ).delete(synchronize_session=False)

    evaluation = db.query(EvaluationModel).filter(EvaluationModel.session_id == session_id).first()
    if evaluation:
        db.query(UserAnswerModel).filter(
            UserAnswerModel.evaluation_id == evaluation.evaluation_id
        ).delete(synchronize_session=False)
        db.query(EvaluationResultModel).filter(
            EvaluationResultModel.evaluation_id == evaluation.evaluation_id
        ).delete(synchronize_session=False)
        db.query(StudentFeedbackModel).filter(
            StudentFeedbackModel.evaluation_id == evaluation.evaluation_id
        ).delete(synchronize_session=False)
        db.query(EvaluatorCommentModel).filter(
            EvaluatorCommentModel.evaluation_id == evaluation.evaluation_id
        ).delete(synchronize_session=False)
        db.delete(evaluation)

    db.delete(session)
    db.commit()
    return {"detail": "Sesión eliminada correctamente"}
