from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Holding, Investor
from app.db.session import get_db
from app.dependencies import require_self
from app.schemas.tax import TaxAnalysisRequest, TaxAnalysisResult
from app.services.tax_calculator import analyze_tax

router = APIRouter(
    prefix="/investors/{investor_id}/holdings", tags=["tax"], dependencies=[Depends(require_self)]
)


@router.post("/tax-analysis", response_model=TaxAnalysisResult)
def get_tax_analysis(investor_id: int, payload: TaxAnalysisRequest, db: Session = Depends(get_db)):
    if db.get(Investor, investor_id) is None:
        raise HTTPException(status_code=404, detail="Investor not found")

    try:
        holdings = db.query(Holding).filter(Holding.investor_id == investor_id).all()
        result = analyze_tax(
            holdings,
            ordinary_income_tax_rate=payload.ordinary_income_tax_rate,
            taxable_income=payload.taxable_income,
            filing_status=payload.filing_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result
