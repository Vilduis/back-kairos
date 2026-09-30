"""Registro único de modelos ORM: importarlo garantiza que el metadata esté completo."""

from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.auth.models import PasswordReset
from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.evaluations.models import Evaluation, EvaluationResult, Question, UserAnswer
from backend.modules.feedback.models import EvaluatorComment, StudentFeedback
from backend.modules.users.models import User

__all__ = [
    "ChatMessage",
    "ChatSession",
    "Evaluation",
    "EvaluationResult",
    "EvaluatorAssignment",
    "EvaluatorComment",
    "PasswordReset",
    "Question",
    "StudentFeedback",
    "User",
    "UserAnswer",
]
