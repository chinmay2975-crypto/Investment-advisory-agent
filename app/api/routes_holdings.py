import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.models import Holding, Investor
from app.db.session import get_db
from app.dependencies import require_self
from app.schemas.holding import HoldingCreate, HoldingRead, PortfolioAnalysis
from app.services.portfolio_analysis import analyze_portfolio

router = APIRouter(
    prefix="/investors/{investor_id}/holdings", tags=["holdings"], dependencies=[Depends(require_self)]
)


def _get_investor_or_404(investor_id: int, db: Session) -> Investor:
    investor = db.get(Investor, investor_id)
    if investor is None:
        raise HTTPException(status_code=404, detail="Investor not found")
    return investor


@router.post("/", response_model=HoldingRead)
def create_holding(investor_id: int, payload: HoldingCreate, db: Session = Depends(get_db)):
    _get_investor_or_404(investor_id, db)

    holding = Holding(investor_id=investor_id, source="manual", **payload.model_dump())
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


@router.post("/csv-upload", response_model=list[HoldingRead])
def upload_holdings_csv(investor_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    _get_investor_or_404(investor_id, db)

    raw = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))

    required_columns = {"ticker", "quantity"}
    if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400, detail=f"CSV must include columns: {sorted(required_columns)}"
        )

    holdings = []
    for row_number, row in enumerate(reader, start=2):
        ticker = (row.get("ticker") or "").strip()
        if not ticker:
            continue
        try:
            quantity = float(row["quantity"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Row {row_number}: invalid quantity '{row.get('quantity')}'")

        cost_basis_raw = (row.get("cost_basis") or "").strip()
        cost_basis = float(cost_basis_raw) if cost_basis_raw else None

        holdings.append(
            Holding(
                investor_id=investor_id,
                ticker=ticker.upper(),
                quantity=quantity,
                cost_basis=cost_basis,
                source="csv_upload",
            )
        )

    if not holdings:
        raise HTTPException(status_code=400, detail="No valid holding rows found in CSV")

    db.add_all(holdings)
    db.commit()
    for holding in holdings:
        db.refresh(holding)
    return holdings


@router.get("/", response_model=list[HoldingRead])
def list_holdings(investor_id: int, db: Session = Depends(get_db)):
    return db.query(Holding).filter(Holding.investor_id == investor_id).all()


@router.delete("/{holding_id}", status_code=204)
def delete_holding(investor_id: int, holding_id: int, db: Session = Depends(get_db)):
    holding = (
        db.query(Holding).filter(Holding.investor_id == investor_id, Holding.id == holding_id).first()
    )
    if holding is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(holding)
    db.commit()


@router.get("/analysis", response_model=PortfolioAnalysis)
def get_portfolio_analysis(investor_id: int, db: Session = Depends(get_db)):
    _get_investor_or_404(investor_id, db)

    holdings = db.query(Holding).filter(Holding.investor_id == investor_id).all()
    return analyze_portfolio(holdings)
