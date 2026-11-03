from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.countries import CountryRequiredError, UnknownCountryError, normalize_country_code
from app.db.models import Investor
from app.dependencies import get_current_investor
from app.schemas.analysis import PortfolioAnalyzeRequest, PortfolioAnalyzeResponse
from app.schemas.portfolio_import import PortfolioImportResult
from app.services.country_analysis import UnsupportedCurrencyError, analyze_portfolio
from app.services.portfolio_import import MAX_BYTES, PortfolioImportError, import_portfolio, verify_tickers

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post(
    "/analyze",
    response_model=PortfolioAnalyzeResponse,
    summary="Country-aware portfolio analysis (allocation, returns, risk, benchmark)",
    description=(
        "Infers the country from the holdings unless `country` is given (UK/GB, IN, US). Mixed "
        "portfolios get a per-country breakdown plus a combined view in `base_currency`. "
        "Uses live yfinance data, so the first call for new tickers can take several seconds. "
        "General information only, not financial advice."
    ),
)
def analyze(payload: PortfolioAnalyzeRequest, _: Investor = Depends(get_current_investor)):
    try:
        return analyze_portfolio(payload)
    except (CountryRequiredError, UnknownCountryError, UnsupportedCurrencyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/import",
    response_model=PortfolioImportResult,
    summary="Parse holdings from any file or pasted text (nothing is saved)",
    description=(
        "Upload a broker export, statement or screenshot — CSV/TSV/semicolon, Excel (.xlsx/.xls/.ods), "
        "JSON, PDF (including scanned PDFs), Word (.docx), HTML (saved web pages), or an image "
        "(PNG/JPG/WEBP screenshot or photo) — or paste text such as `RELIANCE.NS 20 2400` / `NSE:TCS, 10`. "
        "The format is detected from the file contents. Column names are matched automatically "
        "(e.g. 'Instrument', 'Qty.', 'Avg. cost'). Tickers without an exchange suffix get the suffix of "
        "`default_country` (IN, US, UK). Images, scans, files with no usable table, and files listing "
        "company names instead of tickers are read by the AI (`method: ai`) and must be reviewed. "
        "Returns holdings to review; save them with the holdings endpoints."
    ),
)
def import_holdings(
    file: UploadFile | None = File(default=None, description=f"Up to {MAX_BYTES // (1024 * 1024)} MB"),
    text: str | None = Form(default=None, description="Pasted holdings, used when no file is sent"),
    default_country: str | None = Form(default=None, description="Market for tickers without a suffix: IN, US or UK"),
    _: Investor = Depends(get_current_investor),
):
    try:
        country = normalize_country_code(default_country) if default_country else None
        content = file.file.read(MAX_BYTES + 1) if file is not None else None
        result = import_portfolio(
            content=content or None,
            filename=(file.filename or "") if file is not None else "",
            text=text,
            default_country=country,
        )
        return verify_tickers(result, country)
    except UnknownCountryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PortfolioImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
