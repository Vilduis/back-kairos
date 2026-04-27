from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    educational_institution: Optional[str] = None
    role: Optional[str] = 'student'

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    educational_institution: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class User(UserBase):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenUser(BaseModel):
    user_id: int
    full_name: str
    email: EmailStr
    role: str

class TokenWithUser(BaseModel):
    access_token: str
    token_type: str
    user: TokenUser

class TokenData(BaseModel):
    email: Optional[str] = None

# Password Reset Schemas
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# Chat Schemas
class ChatSessionBase(BaseModel):
    chat_mode: str
    conversation_stage: Optional[str] = None

class ChatSessionCreate(ChatSessionBase):
    user_id: int

class ChatSession(ChatSessionBase):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    user_id: int
    started_at: datetime
    last_activity: datetime
    status: str

class ChatMessageBase(BaseModel):
    message_type: str
    content: str
    message_order: int

class ChatMessageCreate(ChatMessageBase):
    session_id: int

class ChatMessage(ChatMessageBase):
    model_config = ConfigDict(from_attributes=True)

    message_id: int
    session_id: int
    sent_at: datetime

# Evaluation Schemas
class EvaluationBase(BaseModel):
    evaluation_mode: str

class EvaluationCreate(EvaluationBase):
    user_id: int
    session_id: int

class Evaluation(EvaluationBase):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: int
    user_id: int
    session_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    progress: float

# Question Schemas
class QuestionBase(BaseModel):
    question_text: str
    question_type: str
    category: Optional[str] = None
    display_order: Optional[int] = None
    options: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    compatible_modes: Optional[str] = 'guided'

class QuestionCreate(QuestionBase):
    pass

class Question(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    question_id: int

# Answer Schemas
class UserAnswerBase(BaseModel):
    answer_text: Optional[str] = None
    selected_options: Optional[Dict[str, Any]] = None

class UserAnswerCreate(UserAnswerBase):
    evaluation_id: int
    question_id: int

class UserAnswer(UserAnswerBase):
    model_config = ConfigDict(from_attributes=True)

    answer_id: int
    evaluation_id: int
    question_id: int
    answered_at: datetime

# Para responder en sesión sin exponer evaluation_id
class UserSessionAnswerCreate(UserAnswerBase):
    question_id: int

# Result Schemas
class EvaluationResultBase(BaseModel):
    riasec_scores: Dict[str, float]
    top_careers: List[Dict[str, Any]]
    metrics: Dict[str, float]

class EvaluationResultCreate(EvaluationResultBase):
    evaluation_id: int

class EvaluationResult(EvaluationResultBase):
    model_config = ConfigDict(from_attributes=True)

    result_id: int
    evaluation_id: int
    generated_at: datetime

# Feedback Schemas
class StudentFeedbackBase(BaseModel):
    rating: int
    comment: Optional[str] = None

class StudentFeedbackCreate(StudentFeedbackBase):
    evaluation_id: int
    user_id: int

class StudentFeedback(StudentFeedbackBase):
    model_config = ConfigDict(from_attributes=True)

    feedback_id: int
    evaluation_id: int
    user_id: int
    created_at: datetime

# Enviar feedback del estudiante sin requerir user_id explícito
class StudentFeedbackSubmit(StudentFeedbackBase):
    pass

# Assignment Schemas
class EvaluatorAssignmentBase(BaseModel):
    status: Optional[str] = 'active'

class EvaluatorAssignmentCreate(EvaluatorAssignmentBase):
    evaluator_id: int
    student_id: int

class EvaluatorAssignment(EvaluatorAssignmentBase):
    model_config = ConfigDict(from_attributes=True)

    assignment_id: int
    evaluator_id: int
    student_id: int
    assigned_date: datetime

# Evaluator Comment Schemas
class EvaluatorCommentBase(BaseModel):
    comment_text: str

class EvaluatorCommentCreate(EvaluatorCommentBase):
    evaluation_id: int
    evaluator_id: int

class EvaluatorComment(EvaluatorCommentBase):
    model_config = ConfigDict(from_attributes=True)

    comment_id: int
    evaluation_id: int
    evaluator_id: int
    created_at: datetime
