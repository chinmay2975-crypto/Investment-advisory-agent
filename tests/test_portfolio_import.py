import io
import json

import pytest
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from app.db.models import Investor
from app.llm.base import LLMClient, ProviderError
from app.llm.router import LLMRouter
from app.schemas.portfolio_import import ExtractedHolding, ExtractedPortfolio
from app.services.portfolio_import import PortfolioImportError, import_portfolio, verify_tickers
from tests import market_fakes


def tickers(result) -> dict[str, tuple[float, float | None]]:
    return {h.ticker: (h.quantity, h.cost_basis) for h in result.holdings}


class FakeExtractor(LLMClient):
    name = "fake"

    def __init__(self, holdings=None, fail=False):
        self.holdings = holdings or []
        self.fail = fail
        self.prompts = []

    def generate(self, prompt, schema):
        self.prompts.append(prompt)
        if self.fail:
            raise ProviderError("both providers down", status_code=503)
        assert schema is ExtractedPortfolio
        return ExtractedPortfolio(holdings=[ExtractedHolding(**h) for h in self.holdings])


@pytest.fixture
def ai(monkeypatch):
    client = FakeExtractor(
        holdings=[
            {"ticker": "RELIANCE", "quantity": 10, "cost_basis": 2400},
            {"ticker": "INFY.NS", "quantity": 5, "cost_basis": None},
            {"ticker": "AAPL", "quantity": 3, "cost_basis": None},
        ]
    )
    monkeypatch.setattr("app.services.portfolio_import.get_router", lambda: LLMRouter([client]))
    return client


# --- tables -----------------------------------------------------------------------------


def test_zerodha_style_csv_with_preamble_commas_and_total_row():
    csv_text = (
        "Holdings statement for client AB1234\n"
        "As on 12-10-2026\n"
        "\n"
        "Instrument,Qty.,Avg. cost,LTP,Cur. val,P&L\n"
        'RELIANCE,20,"2,400.50",1167.7,"23,354",-1000\n'
        'INFY,30,"1,450",1035,"31,050",-500\n'
        "Total,,,,\"54,404\",\n"
    )
    result = import_portfolio(content=csv_text.encode(), filename="holdings.csv", default_country="IN")

    assert result.method == "columns" and result.source_format == "csv"
    assert tickers(result) == {"RELIANCE.NS": (20, 2400.5), "INFY.NS": (30, 1450)}
    assert result.column_mapping == {"ticker": "Instrument", "quantity": "Qty.", "unit_cost": "Avg. cost"}
    assert any("no exchange suffix" in w for w in result.warnings)


def test_semicolon_file_with_exchange_column_and_prefixed_tickers():
    text = "Symbol;Exchange;Shares;Buy Price\nRELIANCE;NSE;10;2400\nHDFCBANK;BSE;5;1500\nVOD;LSE;100;0.9\nNSE:TCS;;2;3600\nAAPL;NASDAQ;3;180\n"
    result = import_portfolio(content=text.encode(), filename="export.txt")
    assert tickers(result) == {
        "RELIANCE.NS": (10, 2400),
        "HDFCBANK.BO": (5, 1500),
        "VOD.L": (100, 0.9),
        "TCS.NS": (2, 3600),
        "AAPL": (3, 180),
    }


def test_us_broker_total_cost_basis_is_converted_to_per_unit():
    text = "Symbol,Description,Quantity,Last Price,Cost Basis Total\nVOO,Vanguard S&P 500 ETF,4,520.10,$1600.00\nMSFT,Microsoft,10,410,\"3,000.00\"\n"
    result = import_portfolio(content=text.encode(), filename="positions.csv", default_country="US")
    assert tickers(result) == {"VOO": (4, 400), "MSFT": (10, 300)}
    assert any("calculated from the total cost" in w for w in result.warnings)


def test_excel_with_header_on_third_row_and_extra_sheet():
    wb = Workbook()
    notes = wb.active
    notes.title = "Notes"
    notes.append(["This sheet has no holdings"])
    sheet = wb.create_sheet("Portfolio")
    sheet.append(["My portfolio"])
    sheet.append([])
    sheet.append(["Ticker Symbol", "Units held", "Average price (£)"])
    sheet.append(["VOD.L", 1000, 0.85])
    sheet.append(["HSBA.L", 200, 6.4])
    buffer = io.BytesIO()
    wb.save(buffer)

    result = import_portfolio(content=buffer.getvalue(), filename="isa.xlsx")
    assert result.source_format == "excel"
    assert tickers(result) == {"VOD.L": (1000, 0.85), "HSBA.L": (200, 6.4)}


def test_nested_json_records():
    payload = {"account": "x", "data": {"holdings": [{"symbol": "AAPL", "shares": 5, "avg_price": 180}, {"symbol": "MSFT", "shares": 2}]}}
    result = import_portfolio(content=json.dumps(payload).encode(), filename="h.json")
    assert result.source_format == "json"
    assert tickers(result) == {"AAPL": (5, 180), "MSFT": (2, None)}


def test_pdf_table():
    buffer = io.BytesIO()
    table = Table([["Symbol", "Quantity", "Avg Cost"], ["AAPL", "5", "180"], ["MSFT", "2", "300"]])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black")]))
    SimpleDocTemplate(buffer, pagesize=A4).build([table])

    result = import_portfolio(content=buffer.getvalue(), filename="statement.pdf")
    assert result.source_format == "pdf"
    assert tickers(result) == {"AAPL": (5, 180), "MSFT": (2, 300)}


def test_duplicates_merged_and_bad_rows_skipped():
    text = "ticker,quantity,cost\nAAPL,5,100\naapl,5,200\nMSFT,0,300\n$$$,4,1\n"
    result = import_portfolio(text=text)
    # "cost" is a total-cost column: per unit 100/5 = 20 and 200/5 = 40, weighted average 30
    assert tickers(result)["AAPL"] == (10, 30)
    reasons = " ".join(s.reason for s in result.skipped)
    assert "MSFT" in reasons and "$$$" in reasons
    assert any("Merged 1 duplicate" in w for w in result.warnings)


# --- plain lines -------------------------------------------------------------------------


def test_pasted_lines_with_header_and_total():
    text = "My stocks\nRELIANCE.NS 20 2400\nAAPL, 5\nNSE:TCS | 2 | ₹3,600\nMSFT.US 3\nTotal 1000\n"
    result = import_portfolio(text=text, default_country="IN")
    assert result.method == "lines" and result.source_format == "text"
    # default market (IN) applies to bare tickers; an explicit ".US" marks a US listing
    assert tickers(result) == {"RELIANCE.NS": (20, 2400), "AAPL.NS": (5, None), "TCS.NS": (2, 3600), "MSFT": (3, None)}


# --- AI fallback ----------------------------------------------------------------------------


def test_names_only_export_goes_to_ai(ai, monkeypatch):
    text = "Stock Name,ISIN,Quantity,Average buy price\nReliance Industries Ltd,INE002A01018,10,2400\nInfosys Limited,INE009A01021,5,1400\n"
    result = import_portfolio(content=text.encode(), filename="groww.csv", default_country="IN")
    assert result.method == "ai" and result.source_format == "csv"
    # bare AI tickers get the home market's suffix, exactly like tables...
    assert tickers(result) == {"RELIANCE.NS": (10, 2400), "INFY.NS": (5, None), "AAPL.NS": (3, None)}
    assert any("company names" in w for w in result.warnings)
    assert "Reliance Industries Ltd" in ai.prompts[0] and "India" in ai.prompts[0]

    # ...and the market-data check reverts the ones that only exist without it (AAPL.NS has no data)
    market_fakes.install(monkeypatch, prices={"INFY.NS": (market_fakes.series(1500), "INR")})
    verified = {h.ticker for h in verify_tickers(result, "IN").holdings}
    assert verified == {"RELIANCE.NS", "INFY.NS", "AAPL"}


def test_unstructured_text_goes_to_ai(ai):
    result = import_portfolio(text="I bought ten Reliance shares, at 2400 each, and some Infosys.", default_country="IN")
    assert result.method == "ai"
    assert result.source_format == "text"  # commas in prose must not make it "csv"
    assert any("check every row" in w for w in result.warnings)


def test_ai_unavailable_gives_helpful_error(monkeypatch):
    monkeypatch.setattr("app.llm.router.time.sleep", lambda seconds: None)  # skip the router's cooldown wait
    monkeypatch.setattr("app.services.portfolio_import.get_router", lambda: LLMRouter([FakeExtractor(fail=True)]))
    with pytest.raises(PortfolioImportError, match="AI extraction is unavailable"):
        import_portfolio(text="some prose about my investments")


def test_empty_input_rejected():
    with pytest.raises(PortfolioImportError):
        import_portfolio(text="   ")


# --- endpoint -----------------------------------------------------------------------------


def _investor(db_session):
    investor = Investor(email="import@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.commit()
    return investor


def test_import_endpoint_file_upload(client, db_session, auth_headers, monkeypatch):
    market_fakes.install(monkeypatch)
    investor = _investor(db_session)
    response = client.post(
        "/portfolio/import",
        files={"file": ("h.csv", b"Symbol,Qty\nRELIANCE,10\n", "text/csv")},
        data={"default_country": "IN"},
        headers=auth_headers(investor.id),
    )
    assert response.status_code == 200
    assert response.json()["holdings"] == [
        {"ticker": "RELIANCE.NS", "quantity": 10.0, "cost_basis": None, "name": None,
         "source_ticker": "RELIANCE", "price_found": True}
    ]


def test_import_endpoint_text_and_errors(client, db_session, auth_headers, monkeypatch):
    market_fakes.install(monkeypatch)
    investor = _investor(db_session)
    headers = auth_headers(investor.id)
    ok = client.post("/portfolio/import", data={"text": "AAPL 5 180"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["method"] == "lines"
    assert client.post("/portfolio/import", data={"text": ""}, headers=headers).status_code == 422
    assert client.post("/portfolio/import", data={"text": "AAPL 5", "default_country": "FR"}, headers=headers).status_code == 400
    assert client.post("/portfolio/import", data={"text": "AAPL 5"}).status_code == 401


# --- more formats -------------------------------------------------------------------------


class ImageExtractor(LLMClient):
    """Records the images it is sent; returns one holding."""

    name = "vision"

    def __init__(self):
        self.images = None
        self.prompt = None

    def generate(self, prompt, schema, images=None):
        self.prompt, self.images = prompt, images
        return ExtractedPortfolio(holdings=[ExtractedHolding(ticker="RELIANCE", quantity=20, cost_basis=2400)])


@pytest.fixture
def vision(monkeypatch):
    client = ImageExtractor()
    monkeypatch.setattr("app.services.portfolio_import.get_router", lambda: LLMRouter([client]))
    return client


def _png(width=3000, height=1800) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, "PNG")
    return buffer.getvalue()


def test_screenshot_is_downscaled_and_sent_to_vision_model(vision):
    result = import_portfolio(content=_png(), filename="IMG_0042.png", default_country="IN")
    assert result.source_format == "image" and result.method == "ai"
    assert tickers(result) == {"RELIANCE.NS": (20, 2400)}
    [(data, mime)] = vision.images
    from PIL import Image

    assert mime == "image/jpeg"
    assert max(Image.open(io.BytesIO(data)).size) <= 2000
    assert "screenshot" in vision.prompt and "DOCUMENT" not in vision.prompt


def test_image_detected_from_bytes_even_with_wrong_extension(vision):
    result = import_portfolio(content=_png(400, 300), filename="holdings.txt")
    assert result.source_format == "image"


def test_scanned_pdf_pages_are_read_as_images(vision):
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from PIL import Image

    image = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(image, "PNG")
    image.seek(0)
    pdf = io.BytesIO()
    page = canvas.Canvas(pdf)
    page.drawImage(ImageReader(image), 50, 400, width=300, height=200)  # an image, no text at all
    page.save()

    result = import_portfolio(content=pdf.getvalue(), filename="scan.pdf")
    assert result.source_format == "pdf" and result.method == "ai"
    assert len(vision.images) == 1
    assert any("scan" in w for w in result.warnings)


def test_word_document_table():
    import docx

    document = docx.Document()
    document.add_paragraph("Portfolio summary for October")
    table = document.add_table(rows=3, cols=3)
    for row, values in zip(table.rows, [["Scrip", "Quantity", "Buy Price"], ["TCS", "10", "3600"], ["ITC", "100", "410"]]):
        for cell, value in zip(row.cells, values):
            cell.text = value
    buffer = io.BytesIO()
    document.save(buffer)

    result = import_portfolio(content=buffer.getvalue(), filename="portfolio.docx", default_country="IN")
    assert result.source_format == "word" and result.method == "columns"
    assert tickers(result) == {"TCS.NS": (10, 3600), "ITC.NS": (100, 410)}


def test_word_document_plain_lines():
    import docx

    document = docx.Document()
    for line in ["My holdings", "AAPL 5 180", "MSFT 2 300"]:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    result = import_portfolio(content=buffer.getvalue(), filename="notes.docx")
    assert result.source_format == "word" and result.method == "lines"
    assert tickers(result) == {"AAPL": (5, 180), "MSFT": (2, 300)}


def test_opendocument_spreadsheet():
    import pandas as pd

    buffer = io.BytesIO()
    pd.DataFrame({"Symbol": ["VOO", "MSFT"], "Shares": [4, 10], "Average Cost": [400, 300]}).to_excel(
        buffer, index=False, engine="odf"
    )
    result = import_portfolio(content=buffer.getvalue(), filename="positions.ods")
    assert result.source_format == "excel"
    assert tickers(result) == {"VOO": (4, 400), "MSFT": (10, 300)}


def test_saved_html_page_with_holdings_table():
    html = b"""<!DOCTYPE html><html><head><style>td{}</style><script>var x=1;</script></head><body>
    <h1>My holdings</h1><table><tr><th>Instrument</th><th>Qty.</th><th>Avg. cost</th></tr>
    <tr><td>INFY</td><td>30</td><td>1,450.00</td></tr><tr><td>HDFCBANK</td><td>40</td><td>775</td></tr></table></body></html>"""
    result = import_portfolio(content=html, filename="Holdings - Console.html", default_country="IN")
    assert result.source_format == "html"
    assert tickers(result) == {"INFY.NS": (30, 1450), "HDFCBANK.NS": (40, 775)}


def test_heic_photos_get_a_clear_message():
    with pytest.raises(PortfolioImportError, match="HEIC"):
        import_portfolio(content=b"\x00\x00\x00\x18ftypheic", filename="IMG_1234.HEIC")


# --- market-data verification --------------------------------------------------------------


def test_verification_fixes_wrong_assumed_suffix_and_flags_unknown(monkeypatch):
    # fakes have prices for AAPL, MSFT, RELIANCE.NS, TCS.NS ... but not VOO.NS, ITC or NIFTYBEEES.NS
    market_fakes.install(monkeypatch, prices={"ITC.NS": (market_fakes.series(260), "INR")})
    text = "Symbol,Qty\nAAPL,5\nRELIANCE,10\nITC,100\nNIFTYBEEES,200\n"
    result = verify_tickers(import_portfolio(text=text, default_country="IN"), "IN")
    by_ticker = {h.ticker: h for h in result.holdings}

    assert by_ticker["AAPL"].price_found and by_ticker["AAPL"].source_ticker == "AAPL"  # AAPL.NS guessed, reverted
    assert by_ticker["RELIANCE.NS"].price_found
    assert by_ticker["ITC.NS"].price_found
    assert by_ticker["NIFTYBEEES.NS"].price_found is False
    assert any("AAPL.NS → AAPL" in w for w in result.warnings)
    assert any("No market data found for NIFTYBEEES.NS" in w for w in result.warnings)


def test_verification_adds_home_suffix_to_bare_ai_ticker(monkeypatch):
    market_fakes.install(monkeypatch, prices={"ITC.NS": (market_fakes.series(260), "INR")})
    from app.schemas.portfolio_import import ImportedHolding, PortfolioImportResult

    result = PortfolioImportResult(
        holdings=[ImportedHolding(ticker="ITC", quantity=100)], source_format="image", method="ai"
    )
    checked = verify_tickers(result, "IN")
    assert checked.holdings[0].ticker == "ITC.NS" and checked.holdings[0].price_found


def test_ai_exchange_field_sets_the_suffix(monkeypatch):
    client = FakeExtractor(holdings=[{"ticker": "HDFCBANK", "quantity": 40, "exchange": "BSE"},
                                     {"ticker": "VOD", "quantity": 100, "exchange": "LSE"},
                                     {"ticker": "AAPL", "quantity": 3, "exchange": "NASDAQ"}])
    monkeypatch.setattr("app.services.portfolio_import.get_router", lambda: LLMRouter([client]))
    result = import_portfolio(text="some statement prose", default_country="IN")
    assert set(tickers(result)) == {"HDFCBANK.BO", "VOD.L", "AAPL"}
    assert "exchange" in client.prompts[0]


def test_image_read_by_fallback_model_gets_a_stronger_warning(vision):
    result = import_portfolio(content=_png(400, 300), filename="shot.png")
    assert vision.name != "gemini"
    assert any("fallback model" in w for w in result.warnings)
