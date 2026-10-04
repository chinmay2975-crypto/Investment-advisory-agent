from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class Investor(Base):
    __tablename__ = "investors"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("InvestorProfile", back_populates="investor", uselist=False)
    goals = relationship("Goal", back_populates="investor")
    holdings = relationship("Holding", back_populates="investor")
    recommendations = relationship("Recommendation", back_populates="investor")


class InvestorProfile(Base):
    __tablename__ = "investor_profile"

    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey("investors.id"), unique=True, nullable=False)
    risk_cadence = Column(String, nullable=False)  # e.g. Conservative / Balanced / Aggressive
    horizon_years = Column(Integer, nullable=True)
    preferences = Column(JSON, default=dict)  # e.g. sector preferences, ESG flags
    restrictions = Column(JSON, default=dict)  # e.g. excluded tickers/sectors
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    investor = relationship("Investor", back_populates="profile")


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey("investors.id"), nullable=False)
    category = Column(String, nullable=False)  # e.g. Retirement, Home, Education
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    target_date = Column(DateTime, nullable=False)
    contribution_cadence = Column(String, nullable=True)  # e.g. monthly, quarterly
    contribution_amount = Column(Float, nullable=True)
    goal_risk_override = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    investor = relationship("Investor", back_populates="goals")


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey("investors.id"), nullable=False)
    ticker = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=True)
    acquired_at = Column(DateTime, nullable=True)
    source = Column(String, default="manual")  # manual entry or csv_upload

    investor = relationship("Investor", back_populates="holdings")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey("investors.id"), nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    status = Column(String, default="pending")  # pending / approved / confirmed
    payload = Column(JSON, nullable=False)  # what/why/expected_behavior/goal_probability/risks
    llm_provider = Column(String, nullable=True)  # gemini / groq, for self-assessment tracking
    generated_at = Column(DateTime, default=datetime.utcnow)

    investor = relationship("Investor", back_populates="recommendations")
    evaluations = relationship("RecommendationEvaluation", back_populates="recommendation")


class RefinementSession(Base):
    __tablename__ = "refinement_sessions"

    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey("investors.id"), nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    origin_recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    current_recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    active_constraints = Column(JSON, default=dict)  # {"exclusions": [...], "tilts": [...], "other": [...]}
    status = Column(String, default="open")  # open / closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    investor = relationship("Investor")
    goal = relationship("Goal")
    messages = relationship(
        "RefinementMessage", back_populates="session", order_by="RefinementMessage.created_at"
    )


class RefinementMessage(Base):
    __tablename__ = "refinement_messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("refinement_sessions.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    user_message = Column(Text, nullable=False)
    resulting_recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    llm_provider = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("RefinementSession", back_populates="messages")
    resulting_recommendation = relationship("Recommendation")


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"

    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey("investors.id"), nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    conservative_recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    balanced_recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    aggressive_recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    investor = relationship("Investor")
    goal = relationship("Goal")
    conservative_recommendation = relationship("Recommendation", foreign_keys=[conservative_recommendation_id])
    balanced_recommendation = relationship("Recommendation", foreign_keys=[balanced_recommendation_id])
    aggressive_recommendation = relationship("Recommendation", foreign_keys=[aggressive_recommendation_id])


class RecommendationEvaluation(Base):
    __tablename__ = "recommendation_evaluations"

    id = Column(Integer, primary_key=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    deviation = Column(JSON, nullable=True)  # structured diff vs actual outcome
    contributing_factors = Column(Text, nullable=True)
    assumptions_held = Column(Boolean, nullable=True)

    recommendation = relationship("Recommendation", back_populates="evaluations")
