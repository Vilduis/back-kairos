"""Registro único de modelos ORM: importarlo garantiza que el metadata esté completo."""

from backend.modules.access_codes.models import AccessCode
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.auth.models import PasswordReset
from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.evaluations.models import Evaluation, EvaluationResult, Question, UserAnswer
from backend.modules.feedback.models import EvaluatorComment, StudentFeedback
from backend.modules.schools.models import School
from backend.modules.users.models import User

__all__ = [
    "AccessCode",
    "ChatMessage",
    "ChatSession",
    "Evaluation",
    "EvaluationResult",
    "EvaluatorAssignment",
    "EvaluatorComment",
    "PasswordReset",
    "Question",
    "School",
    "StudentFeedback",
    "User",
    "UserAnswer",
]
