from enum import Enum


class UserRole(str, Enum):
    STUDENT = "student"
    ADMIN = "admin"
    EVALUATOR = "evaluator"


class ChatMode(str, Enum):
    GUIDED = "guided"
    OPEN = "open"
    MODE_SELECTION = "mode_selection"


class ConversationStage(str, Enum):
    WELCOME = "welcome"
    MODE_CHOICE = "mode_choice"
    QUESTIONS = "questions"
    COLLECTING = "collecting"
    CONFIRM_RESULTS = "confirm_results"
    RESULTS = "results"
