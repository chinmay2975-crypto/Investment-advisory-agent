"""Account lifecycle: password e-mails and full account deletion."""

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    Goal,
    Holding,
    Investor,
    InvestorProfile,
    Recommendation,
    RecommendationEvaluation,
    RefinementMessage,
    RefinementSession,
    ScenarioRun,
)

logger = logging.getLogger(__name__)


def email_enabled() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def send_password_reset_email(to_address: str, token: str) -> None:
    link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={token}"
    message = EmailMessage()
    message["Subject"] = "Reset your InvestAd password"
    message["From"] = settings.smtp_from
    message["To"] = to_address
    message.set_content(
        "Someone asked to reset the password for this InvestAd account.\n\n"
        f"Open this link within {settings.password_reset_expire_minutes} minutes to choose a new one:\n{link}\n\n"
        "If it wasn't you, ignore this e-mail; your password stays the same."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def delete_investor_account(db: Session, investor: Investor) -> None:
    """Delete the investor and everything they own, children before parents (no DB cascades)."""
    investor_id = investor.id
    recommendation_ids = [r.id for r in db.query(Recommendation.id).filter(Recommendation.investor_id == investor_id)]
    evaluation_ids = []
    if recommendation_ids:
        evaluations = db.query(RecommendationEvaluation).filter(RecommendationEvaluation.recommendation_id.in_(recommendation_ids))
        evaluation_ids = [e.id for e in evaluations]
        evaluations.delete(synchronize_session=False)

    session_ids = [s.id for s in db.query(RefinementSession.id).filter(RefinementSession.investor_id == investor_id)]
    if session_ids:
        db.query(RefinementMessage).filter(RefinementMessage.session_id.in_(session_ids)).delete(synchronize_session=False)
    for model in (RefinementSession, ScenarioRun, Recommendation, Holding, Goal, InvestorProfile):
        db.query(model).filter(model.investor_id == investor_id).delete(synchronize_session=False)
    db.delete(investor)
    db.commit()

    if evaluation_ids:  # reflection memory is derived from this user's data; remove it too
        try:
            from app.services import chroma_client

            chroma_client.get_reflection_collection().delete(ids=[f"evaluation:{i}" for i in evaluation_ids])
        except Exception:  # noqa: BLE001 - the account is gone either way; don't fail the request
            logger.warning("Could not remove %d reflections from ChromaDB", len(evaluation_ids), exc_info=True)
