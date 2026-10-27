"""SQLAlchemy models for SycoMetrix."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sycometrix.extensions import db


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def enum_values(enum_class: type[enum.Enum]) -> list[str]:
    """Persist enum values (lowercase strings), rather than member names."""
    return [member.value for member in enum_class]


class Condition(str, enum.Enum):
    NEUTRAL = "neutral"
    CORRECT_BELIEF = "correct_belief"
    INCORRECT_BELIEF = "incorrect_belief"


class Stance(str, enum.Enum):
    AGREES = "agrees"
    DISAGREES = "disagrees"
    UNCLEAR = "unclear"


class RiskLevel(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


condition_enum = Enum(
    Condition, name="condition", values_callable=enum_values, native_enum=True
)
stance_enum = Enum(Stance, name="stance", values_callable=enum_values, native_enum=True)
risk_level_enum = Enum(
    RiskLevel, name="risk_level", values_callable=enum_values, native_enum=True
)


class Experiment(db.Model):
    __tablename__ = "experiment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    test_cases: Mapped[list["TestCase"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TestCase.id",
    )


class TestCase(db.Model):
    __test__ = False
    __tablename__ = "test_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiment.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    incorrect_belief: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    experiment: Mapped["Experiment"] = relationship(back_populates="test_cases")
    prompts: Mapped[list["Prompt"]] = relationship(
        back_populates="test_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Prompt.id",
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="test_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Evaluation.id",
    )

    def prompt_for(self, condition: Condition) -> "Prompt | None":
        """Return the prompt for a condition, if one exists."""
        return next((prompt for prompt in self.prompts if prompt.condition == condition), None)

    def responses_for(self, model_id: int) -> dict[Condition, "Response | None"]:
        """Map every condition to that model's response, or None if not run."""
        return {
            condition: next(
                (
                    response
                    for prompt in self.prompts
                    if prompt.condition == condition
                    for response in prompt.responses
                    if response.model_id == model_id
                ),
                None,
            )
            for condition in Condition
        }

    def evaluation_for(self, model_id: int) -> "Evaluation | None":
        """Return this test case's evaluation for a model, if one exists."""
        return next(
            (evaluation for evaluation in self.evaluations if evaluation.model_id == model_id),
            None,
        )


class Prompt(db.Model):
    __tablename__ = "prompt"
    __table_args__ = (
        UniqueConstraint("test_case_id", "condition", name="uq_prompt_test_case_condition"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_case.id", ondelete="CASCADE"), nullable=False
    )
    condition: Mapped[Condition] = mapped_column(condition_enum, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)

    test_case: Mapped["TestCase"] = relationship(back_populates="prompts")
    responses: Mapped[list["Response"]] = relationship(
        back_populates="prompt",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Response.id",
    )


class LLMModel(db.Model):
    __tablename__ = "model"
    __table_args__ = (
        UniqueConstraint("provider", "model_name", name="uq_model_provider_model_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    responses: Mapped[list["Response"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Response.id",
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Evaluation.id",
    )


class Response(db.Model):
    __tablename__ = "response"
    __table_args__ = (
        UniqueConstraint("prompt_id", "model_id", name="uq_response_prompt_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(
        ForeignKey("prompt.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[int] = mapped_column(
        ForeignKey("model.id", ondelete="CASCADE"), nullable=False
    )
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    stance: Mapped[Stance | None] = mapped_column(stance_enum, nullable=True, default=None)
    stance_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    prompt: Mapped["Prompt"] = relationship(back_populates="responses")
    model: Mapped["LLMModel"] = relationship(back_populates="responses")


class Evaluation(db.Model):
    __tablename__ = "evaluation"
    __table_args__ = (
        UniqueConstraint("test_case_id", "model_id", name="uq_evaluation_test_case_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_case.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[int] = mapped_column(
        ForeignKey("model.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(risk_level_enum, nullable=False)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    test_case: Mapped["TestCase"] = relationship(back_populates="evaluations")
    model: Mapped["LLMModel"] = relationship(back_populates="evaluations")
