from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from statistics import fmean
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Row, distinct, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from backend.core.enums import (
    AssignmentStatus,
    EvaluationMode,
    EvaluationStatus,
    RiasecType,
    UserRole,
)
from backend.modules.admin.schemas import (
    ActivityPoint,
    AdminDashboard,
    DashboardRange,
    EvaluatorLoad,
    Kpi,
    ModeBreakdown,
)
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.evaluations.models import Evaluation, EvaluationResult
from backend.modules.evaluations.service import dominant_dimension
from backend.modules.feedback.models import StudentFeedback
from backend.modules.schools.scope import SchoolScope
from backend.modules.users.models import User

LOCAL_TZ = ZoneInfo("America/Lima")
EVALUATOR_LOAD_LIMIT = 5

type Bucket = Literal["day", "week", "month"]

RANGES: dict[DashboardRange, tuple[timedelta, Bucket]] = {
    "7d": (timedelta(days=7), "day"),
    "30d": (timedelta(days=30), "day"),
    "90d": (timedelta(days=90), "week"),
    "12m": (timedelta(days=365), "month"),
}


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def __contains__(self, moment: datetime | None) -> bool:
        return moment is not None and self.start <= moment <= self.end


def _bucket_of(moment: datetime, bucket: Bucket) -> date:
    day = moment.astimezone(LOCAL_TZ).date()
    if bucket == "week":
        return day - timedelta(days=day.weekday())
    if bucket == "month":
        return day.replace(day=1)
    return day


def _next_bucket(day: date, bucket: Bucket) -> date:
    if bucket == "month":
        return (day + timedelta(days=32)).replace(day=1)
    return day + timedelta(days=7 if bucket == "week" else 1)


def _periods(window: Window, bucket: Bucket) -> list[date]:
    periods = [_bucket_of(window.start, bucket)]
    last = _bucket_of(window.end, bucket)
    while periods[-1] < last:
        periods.append(_next_bucket(periods[-1], bucket))
    return periods


def _count_in(moments: Iterable[datetime | None], window: Window) -> int:
    return sum(moment in window for moment in moments)


def _average(values: Iterable[float]) -> float | None:
    values = list(values)
    return round(fmean(values), 2) if values else None


def _started_in(evaluations: Sequence[Row], window: Window) -> list[Row]:
    return [evaluation for evaluation in evaluations if evaluation.started_at in window]


def _completion_rate(evaluations: Sequence[Row], window: Window) -> float | None:
    started = _started_in(evaluations, window)
    if not started:
        return None
    completed = sum(e.status == EvaluationStatus.COMPLETED for e in started)
    return round(100 * completed / len(started), 1)


def _activity(
    registrations: Sequence[datetime],
    evaluations: Sequence[Row],
    window: Window,
    bucket: Bucket,
) -> list[ActivityPoint]:
    students = Counter(_bucket_of(m, bucket) for m in registrations if m in window)
    completed = Counter(
        _bucket_of(e.completed_at, bucket) for e in evaluations if e.completed_at in window
    )
    return [
        ActivityPoint(period=period, students=students[period], evaluations=completed[period])
        for period in _periods(window, bucket)
    ]


def _modes(evaluations: Sequence[Row], window: Window) -> list[ModeBreakdown]:
    counts = Counter((e.evaluation_mode, e.status) for e in _started_in(evaluations, window))
    return [
        ModeBreakdown(
            mode=mode,
            completed=counts[mode, EvaluationStatus.COMPLETED],
            in_progress=counts[mode, EvaluationStatus.IN_PROGRESS],
        )
        for mode in EvaluationMode
    ]


def _riasec_profiles(session: Session, scope: SchoolScope, window: Window) -> dict[RiasecType, int]:
    statement = (
        select(EvaluationResult.riasec_scores)
        .join(EvaluationResult.evaluation)
        .join(User, User.user_id == Evaluation.user_id)
        .where(Evaluation.completed_at.between(window.start, window.end), *scope.conditions())
    )
    dominant = Counter(dominant_dimension(scores) for scores in session.scalars(statement))
    return {dimension: dominant[dimension] for dimension in RiasecType}


def _active_users(session: Session, scope: SchoolScope) -> dict[UserRole, int]:
    statement = (
        select(User.role, func.count())
        .where(User.is_active, *scope.conditions())
        .group_by(User.role)
    )
    counts: dict[UserRole, int] = {role: count for role, count in session.execute(statement)}
    return {role: counts.get(role, 0) for role in UserRole}


def _count_assigned(
    session: Session, scope: SchoolScope, column: InstrumentedAttribute[int]
) -> int:
    statement = (
        select(func.count(distinct(column)))
        .join(User, User.user_id == EvaluatorAssignment.student_id)
        .where(EvaluatorAssignment.status == AssignmentStatus.ACTIVE, *scope.conditions())
    )
    return session.scalar(statement) or 0


def _evaluator_load(session: Session, scope: SchoolScope) -> list[EvaluatorLoad]:
    students = func.count(EvaluatorAssignment.student_id)
    statement = (
        select(User.user_id, User.full_name, students)
        .join(EvaluatorAssignment, EvaluatorAssignment.evaluator_id == User.user_id)
        .where(EvaluatorAssignment.status == AssignmentStatus.ACTIVE, *scope.conditions())
        .group_by(User.user_id, User.full_name)
        .order_by(students.desc(), User.full_name)
        .limit(EVALUATOR_LOAD_LIMIT)
    )
    return [
        EvaluatorLoad(user_id=user_id, full_name=full_name, students=count)
        for user_id, full_name, count in session.execute(statement)
    ]


def _feedback_dimensions(feedback: Sequence[Row], window: Window) -> dict[str, float]:
    ratings: dict[str, list[float]] = {}
    for row in feedback:
        if row.created_at in window and row.dimension_ratings:
            for name, value in row.dimension_ratings.items():
                ratings.setdefault(name, []).append(value)
    return {name: round(fmean(values), 2) for name, values in ratings.items()}


def _satisfaction(
    session: Session, scope: SchoolScope, current: Window, previous: Window
) -> tuple[Kpi, dict[str, float]]:
    feedback = session.execute(
        select(
            StudentFeedback.created_at,
            StudentFeedback.rating,
            StudentFeedback.dimension_ratings,
        )
        .join(User, User.user_id == StudentFeedback.user_id)
        .where(StudentFeedback.created_at >= previous.start, *scope.conditions())
    ).all()

    def average_rating(window: Window) -> float | None:
        return _average(row.rating for row in feedback if row.created_at in window)

    rating = Kpi(current=average_rating(current), previous=average_rating(previous))
    return rating, _feedback_dimensions(feedback, current)


def get_dashboard(session: Session, scope: SchoolScope, range_: DashboardRange) -> AdminDashboard:
    span, bucket = RANGES[range_]
    now = datetime.now(UTC)
    current = Window(now - span, now)
    previous = Window(now - 2 * span, current.start)

    registrations = session.scalars(
        select(User.created_at).where(
            User.role == UserRole.STUDENT, User.created_at >= previous.start, *scope.conditions()
        )
    ).all()
    evaluations = session.execute(
        select(
            Evaluation.started_at,
            Evaluation.completed_at,
            Evaluation.status,
            Evaluation.evaluation_mode,
        )
        .join(User, User.user_id == Evaluation.user_id)
        .where(
            or_(Evaluation.started_at >= previous.start, Evaluation.completed_at >= previous.start),
            *scope.conditions(),
        )
    ).all()
    completions = [evaluation.completed_at for evaluation in evaluations]
    # La valoración de la plataforma es información del equipo Kairos, no de cada colegio.
    average_rating, feedback_dimensions = (
        _satisfaction(session, scope, current, previous) if scope.is_superadmin else (None, None)
    )

    return AdminDashboard(
        active_users=_active_users(session, scope),
        assigned_students=_count_assigned(session, scope, EvaluatorAssignment.student_id),
        evaluators_with_students=_count_assigned(session, scope, EvaluatorAssignment.evaluator_id),
        new_students=Kpi(
            current=_count_in(registrations, current),
            previous=_count_in(registrations, previous),
        ),
        completed_evaluations=Kpi(
            current=_count_in(completions, current),
            previous=_count_in(completions, previous),
        ),
        completion_rate=Kpi(
            current=_completion_rate(evaluations, current),
            previous=_completion_rate(evaluations, previous),
        ),
        average_rating=average_rating,
        activity=_activity(registrations, evaluations, current, bucket),
        riasec_profiles=_riasec_profiles(session, scope, current),
        modes=_modes(evaluations, current),
        evaluator_load=_evaluator_load(session, scope),
        feedback_dimensions=feedback_dimensions,
    )
