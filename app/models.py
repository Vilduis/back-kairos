from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .db import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    educational_institution = Column(String(150))
    role = Column(String(20), default='student')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user")
    evaluations = relationship("Evaluation", back_populates="user")
    password_resets = relationship("PasswordReset", back_populates="user")
    student_feedbacks = relationship("StudentFeedback", back_populates="user")
    evaluator_assignments_as_evaluator = relationship("EvaluatorAssignment", 
                                                    foreign_keys="[EvaluatorAssignment.evaluator_id]", 
                                                    back_populates="evaluator")
    evaluator_assignments_as_student = relationship("EvaluatorAssignment", 
                                                  foreign_keys="[EvaluatorAssignment.student_id]", 
                                                  back_populates="student")
    evaluator_comments = relationship("EvaluatorComment", back_populates="evaluator")

class PasswordReset(Base):
    __tablename__ = "password_resets"

    reset_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="password_resets")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    chat_mode = Column(String(20), nullable=False)  # 'guided', 'open', 'mode_selection'
    current_question_id = Column(Integer, ForeignKey("questions.question_id"), nullable=True)
    conversation_stage = Column(String(50))  # 'welcome', 'mode_choice', 'questions', 'results'
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default='active')  # 'active', 'completed', 'abandoned'

    user = relationship("User", back_populates="chat_sessions")
    current_question = relationship("Question")
    chat_messages = relationship("ChatMessage", back_populates="chat_session")
    evaluation = relationship("Evaluation", back_populates="chat_session", uselist=False)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.session_id"))
    message_type = Column(String(10), nullable=False)  # 'user', 'bot', 'system'
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    message_order = Column(Integer, nullable=False)

    chat_session = relationship("ChatSession", back_populates="chat_messages")

class Evaluation(Base):
    __tablename__ = "evaluations"

    evaluation_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    session_id = Column(Integer, ForeignKey("chat_sessions.session_id"))
    evaluation_mode = Column(String(20), nullable=False)  # 'guided', 'open'
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(20), default='in_progress')  # 'in_progress', 'completed'
    progress = Column(Float, default=0.0)  # 0.0 to 1.0

    user = relationship("User", back_populates="evaluations")
    chat_session = relationship("ChatSession", back_populates="evaluation")
    user_answers = relationship("UserAnswer", back_populates="evaluation")
    evaluation_results = relationship("EvaluationResult", back_populates="evaluation", uselist=False)
    student_feedbacks = relationship("StudentFeedback", back_populates="evaluation")
    evaluator_comments = relationship("EvaluatorComment", back_populates="evaluation")

class Question(Base):
    __tablename__ = "questions"

    question_id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), nullable=False)  # 'multiple_choice', 'scale', 'open_text'
    category = Column(String(50))  # 'interests', 'skills', 'values', 'personality'
    display_order = Column(Integer)
    options = Column(JSON)  # {"choices": ["A) Opción 1", "B) Opción 2"], "max_selections": 2}
    validation_rules = Column(JSON)  # {"allowed_values": ["A","B","C"], "min_length": 10}
    compatible_modes = Column(String(50), default='guided')  # 'guided', 'open', 'both'

    user_answers = relationship("UserAnswer", back_populates="question")

class UserAnswer(Base):
    __tablename__ = "user_answers"

    answer_id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.evaluation_id"))
    question_id = Column(Integer, ForeignKey("questions.question_id"))
    answer_text = Column(Text)
    selected_options = Column(JSON)  # Para opción múltiple: {"selected": [0, 2]}
    answered_at = Column(DateTime(timezone=True), server_default=func.now())

    evaluation = relationship("Evaluation", back_populates="user_answers")
    question = relationship("Question", back_populates="user_answers")

class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    result_id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.evaluation_id"))
    riasec_scores = Column(JSON, nullable=False)  # {"R": 4.1, "I": 3.9, ...}
    top_careers = Column(JSON, nullable=False)  # [{"career": "Diseñador", "score": 0.82}, ...]
    metrics = Column(JSON, nullable=False)  # {"precision": 0.87, "recall": 0.85, ...}
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    evaluation = relationship("Evaluation", back_populates="evaluation_results")

class StudentFeedback(Base):
    __tablename__ = "student_feedback"

    feedback_id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.evaluation_id"))
    user_id = Column(Integer, ForeignKey("users.user_id"))
    rating = Column(Integer)  # 1-5
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    evaluation = relationship("Evaluation", back_populates="student_feedbacks")
    user = relationship("User", back_populates="student_feedbacks")

class EvaluatorAssignment(Base):
    __tablename__ = "evaluator_assignments"

    assignment_id = Column(Integer, primary_key=True, index=True)
    evaluator_id = Column(Integer, ForeignKey("users.user_id"))
    student_id = Column(Integer, ForeignKey("users.user_id"))
    assigned_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default='active')  # 'active', 'inactive'

    evaluator = relationship("User", foreign_keys=[evaluator_id], back_populates="evaluator_assignments_as_evaluator")
    student = relationship("User", foreign_keys=[student_id], back_populates="evaluator_assignments_as_student")

class EvaluatorComment(Base):
    __tablename__ = "evaluator_comments"

    comment_id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.evaluation_id"))
    evaluator_id = Column(Integer, ForeignKey("users.user_id"))
    comment_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    evaluation = relationship("Evaluation", back_populates="evaluator_comments")
    evaluator = relationship("User", back_populates="evaluator_comments")