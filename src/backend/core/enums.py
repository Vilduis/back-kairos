from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "student"
    EVALUATOR = "evaluator"
    ADMIN = "admin"


class ChatMode(StrEnum):
    GUIDED = "guided"
    OPEN = "open"
    MODE_SELECTION = "mode_selection"


class ConversationStage(StrEnum):
    WELCOME = "welcome"
    MODE_CHOICE = "mode_choice"
    QUESTIONS = "questions"
    COLLECTING = "collecting"
    CONFIRM_RESULTS = "confirm_results"
    RESULTS = "results"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class MessageType(StrEnum):
    USER = "user"
    BOT = "bot"
    SYSTEM = "system"


class EvaluationMode(StrEnum):
    GUIDED = "guided"
    OPEN = "open"


class EvaluationStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class QuestionType(StrEnum):
    SCALE = "scale"
    MULTIPLE_CHOICE = "multiple_choice"
    OPEN_TEXT = "open_text"


class CompatibleMode(StrEnum):
    GUIDED = "guided"
    OPEN = "open"
    BOTH = "both"


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class RiasecType(StrEnum):
    R = "R"
    I = "I"  # noqa: E741
    A = "A"
    S = "S"
    E = "E"
    C = "C"
