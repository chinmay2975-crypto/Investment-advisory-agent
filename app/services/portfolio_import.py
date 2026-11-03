"""Turn a holdings file in (almost) any format into reviewable holdings.

Order of attempts, cheapest and most predictable first:
1. Tables (CSV/TSV/semicolon, Excel/ODS, JSON, PDF, Word and HTML tables): find the header row
   anywhere in the first rows and match column names against synonyms used by common brokers.
2. Plain lines such as "RELIANCE.NS 20 2400" (pasted text, simple PDFs/Word docs).
3. LLM extraction through the Gemini/Groq router when there is no usable table, the table only
   names companies (e.g. Groww exports), or the input is a screenshot/photo -- flagged as
   `method="ai"` so the user reviews every row.
Nothing is saved here; the caller shows the result in an editable table first.
"""

import csv
import io
import json
import re
from dataclasses import dataclass, field

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from app.countries import get_country, list_countries
from app.llm.base import ProviderError
from app.llm.factory import get_router
from app.services import price_data
from app.schemas.portfolio_import import (
    ExtractedPortfolio,
    ImportedHolding,
    PortfolioImportResult,
    SkippedRow,
)

MAX_BYTES = 10 * 1024 * 1024
MAX_IMAGE_SIDE = 2000  # px; keeps screenshots legible but small enough for every vision provider
PREFERRED_VISION_PROVIDER = "gemini"
MAX_AI_CHARS = 15_000
HEADER_SCAN_ROWS = 25
MAX_SKIPPED_REPORTED = 50
TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.^=&:_-]{0,23}$")
TOTAL_ROW = re.compile(r"^(grand |net |sub ?)?totals?\b|^sum$", re.IGNORECASE)

# Normalised header synonyms. Exact matches beat partial ones; longer partial matches win.
FIELD_SYNONYMS: dict[str, tuple[str, ...]] = {
    "ticker": (
        "ticker", "symbol", "tradingsymbol", "trading symbol", "instrument", "scrip", "scrip name",
        "stock symbol", "security symbol", "nse symbol", "bse symbol", "symbol name", "code",
        "stock code", "ticker symbol", "asset",
    ),
    "name": (
        "name", "company", "company name", "security name", "stock name", "stock", "description",
        "instrument name", "holding name", "security", "investment", "fund name", "scheme name",
    ),
    "quantity": (
        "quantity", "qty", "shares", "units", "units held", "no of shares", "number of shares",
        "holding", "holdings", "quantity available", "net qty", "net quantity", "balance",
        "free qty", "free quantity", "total quantity", "current qty", "qty available", "position",
        "share count", "shares held",
    ),
    "unit_cost": (
        "avg cost", "average cost", "avg price", "average price", "avg buy price",
        "average buy price", "buy price", "purchase price", "cost price", "buy avg",
        "avg cost basis", "average cost basis", "unit cost", "price paid", "avg buy",
        "average purchase price", "buy average", "avg trading price", "cost per share",
    ),
    "total_cost": (
        "invested", "invested value", "investment value", "cost value", "total cost", "book cost",
        "buy value", "amount invested", "cost basis", "cost basis total", "total cost basis", "cost",
        "purchase value",
    ),
    "exchange": ("exchange", "market", "exch", "exchange name", "listing"),
}


class PortfolioImportError(ValueError):
    pass


@dataclass
class _Parsed:
    holdings: list[ImportedHolding] = field(default_factory=list)
    skipped: list[SkippedRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)


def _norm(value) -> str:
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", str(value or "").lower())  # drop units like "(₹)"
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _num(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if pd.isna(value) else float(value)
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^\d.\-]", "", text.replace(",", ""))
    if text in ("", "-", ".", "-."):
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def _map_columns(cells: list) -> dict[str, int]:
    candidates = []
    for index, cell in enumerate(cells):
        header = _norm(cell)
        if not header:
            continue
        best = None
        for field_name, synonyms in FIELD_SYNONYMS.items():
            for synonym in synonyms:
                if header == synonym:
                    score = 100 + len(synonym)
                elif re.search(rf"\b{re.escape(synonym)}\b", header):
                    score = len(synonym)
                else:
                    continue
                if best is None or score > best[0]:
                    best = (score, field_name)
        if best:
            candidates.append((best[0], index, best[1]))
    mapping: dict[str, int] = {}
    for _, index, field_name in sorted(candidates, reverse=True):
        if field_name not in mapping and index not in mapping.values():
            mapping[field_name] = index
    return mapping


def _find_header(rows: list[list]) -> tuple[int, dict[str, int]] | None:
    best = None
    for i, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        mapping = _map_columns(row)
        if "quantity" in mapping and ("ticker" in mapping or "name" in mapping):
            if best is None or len(mapping) > len(best[1]):
                best = (i, mapping)
    return best


def _suffix_ticker(raw: str, exchange: str | None, default_country: str | None) -> tuple[str, str | None]:
    """Returns (yfinance ticker, how a suffix was added or None)."""
    ticker = re.sub(r"\s+", "", raw).upper()
    if ":" in ticker:  # TradingView style "NSE:RELIANCE"
        prefix, ticker = ticker.split(":", 1)
        exchange = exchange or prefix
    if ticker.endswith(".US"):  # broker style "AAPL.US"; Yahoo uses the bare symbol for US listings
        return ticker[:-3], None
    countries = list_countries()
    if any(c.matches_suffix(ticker) for c in countries):
        return ticker, None
    if exchange:
        for country in countries:
            if country.matches_exchange(exchange):
                suffix = country.suffix_for_exchange(exchange)
                return ticker + suffix, ("exchange" if suffix else None)
    if default_country and "." not in ticker:
        suffix = get_country(default_country).default_suffix
        if suffix:
            return ticker + suffix, "default"
    return ticker, None


def _source_if_changed(raw: str, ticker: str) -> str | None:
    original = re.sub(r"\s+", "", raw).upper()
    return original if original != ticker else None


def _looks_like_names(values: list[str]) -> bool:
    values = [v for v in values if v]
    return bool(values) and sum(1 for v in values if " " in v.strip()) > len(values) / 2


def _parse_table(rows: list[list], default_country: str | None) -> tuple[_Parsed, bool]:
    """Returns (result, needs_ai). needs_ai means a table was found but only had company names."""
    found = _find_header(rows)
    if not found:
        return _Parsed(), False
    header_index, cols = found
    header = rows[header_index]
    body = rows[header_index + 1 :]

    def cell(row, field_name):
        index = cols.get(field_name)
        return row[index] if index is not None and index < len(row) else None

    if "ticker" in cols and _looks_like_names([str(cell(r, "ticker") or "") for r in body]):
        cols["name"] = cols.pop("ticker")  # the "ticker" column actually holds company names
    if "ticker" not in cols:
        return _Parsed(mapping={k: str(header[v]) for k, v in cols.items()}), True

    parsed = _Parsed(mapping={k: str(header[v]).strip() for k, v in cols.items()})
    suffixed = {"exchange": 0, "default": 0}
    derived_cost = False
    for offset, row in enumerate(body):
        row_number = header_index + offset + 2  # 1-based, after the header
        if not any(str(c or "").strip() for c in row) or [str(c).strip() for c in row] == [str(c).strip() for c in header]:
            continue
        raw_ticker = str(cell(row, "ticker") or "").strip()
        if not raw_ticker or TOTAL_ROW.match(raw_ticker):
            continue
        quantity = _num(cell(row, "quantity"))
        if quantity is None or quantity <= 0:
            parsed.skipped.append(SkippedRow(row=row_number, reason=f"{raw_ticker}: no positive quantity"))
            continue
        ticker, how = _suffix_ticker(raw_ticker, str(cell(row, "exchange") or "") or None, default_country)
        if not TICKER_PATTERN.match(ticker):
            parsed.skipped.append(SkippedRow(row=row_number, reason=f"'{raw_ticker}' is not a valid ticker"))
            continue
        if how:
            suffixed[how] += 1
        cost = _num(cell(row, "unit_cost"))
        if cost is None and "total_cost" in cols:
            total = _num(cell(row, "total_cost"))
            if total is not None:
                cost, derived_cost = total / quantity, True
        name = cell(row, "name")
        parsed.holdings.append(
            ImportedHolding(
                ticker=ticker,
                quantity=quantity,
                cost_basis=round(cost, 6) if cost is not None and cost >= 0 else None,
                name=str(name).strip() if name else None,
                source_ticker=_source_if_changed(raw_ticker, ticker),
            )
        )

    if suffixed["exchange"]:
        parsed.warnings.append(f"Added exchange suffixes to {suffixed['exchange']} ticker(s) using the exchange column.")
    if suffixed["default"]:
        parsed.warnings.append(
            f"{suffixed['default']} ticker(s) had no exchange suffix; assumed {get_country(default_country).name} "
            f"listings (e.g. {get_country(default_country).default_suffix}). Change them if that's wrong."
        )
    if derived_cost:
        parsed.warnings.append(f"Per-unit cost was calculated from the total cost column '{parsed.mapping['total_cost']}'.")
    return parsed, False


LINE_PATTERN = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9.&:^_-]{0,23})\s*[,;|\t ]\s*([\d,]*\.?\d+)"
    r"(?:\s*[,;|\t ]\s*[₹$£€]?\s*([\d,]*\.?\d+))?\s*$"
)


def _parse_lines(text: str, default_country: str | None) -> _Parsed | None:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    parsed = _Parsed()
    defaulted = 0
    for number, line in enumerate(lines, start=1):
        match = LINE_PATTERN.match(line)
        if match and TOTAL_ROW.match(match.group(1)):
            continue
        if not match:
            parsed.skipped.append(SkippedRow(row=number, reason=f"not understood: {line.strip()[:60]}"))
            continue
        ticker, how = _suffix_ticker(match.group(1), None, default_country)
        defaulted += how == "default"
        quantity = _num(match.group(2))
        if not quantity or quantity <= 0:
            parsed.skipped.append(SkippedRow(row=number, reason=f"{ticker}: no positive quantity"))
            continue
        parsed.holdings.append(
            ImportedHolding(
                ticker=ticker,
                quantity=quantity,
                cost_basis=_num(match.group(3)),
                source_ticker=_source_if_changed(match.group(1), ticker),
            )
        )
    if not parsed.holdings or len(parsed.holdings) < 0.6 * len(lines):
        return None
    if defaulted:
        parsed.warnings.append(
            f"{defaulted} ticker(s) had no exchange suffix; assumed {get_country(default_country).name} listings."
        )
    return parsed


def _ai_extract(document: str, default_country: str | None, reason: str, images: list | None = None) -> _Parsed:
    truncated = len(document) > MAX_AI_CHARS
    source = "the attached screenshot or photo of a brokerage app or statement" if images else "this brokerage document"
    market = get_country(default_country).name if default_country else "the market the document refers to"
    suffix_help = "; ".join(
        f"{c.name}: {', '.join(c.ticker_suffixes) if c.ticker_suffixes else 'no suffix'}" for c in list_countries()
    )
    prompt = f"""Extract the investment holdings from {source}. Return ONLY holdings that
actually appear in it; never invent holdings or guess quantities.
For each holding:
- ticker: the Yahoo Finance ticker ({suffix_help}). If only a company or fund name is given, use that
  company's well-known ticker on {market}. Leave out holdings you cannot identify with confidence.
- exchange: the exchange it trades on (NSE, BSE, LSE, NYSE, NASDAQ, ...) if shown or clear from
  context such as the currency or broker, else null.
- quantity: number of shares or units currently held (a positive number).
- cost_basis: average cost PER UNIT if stated or derivable (total cost / quantity), else null.
Skip totals, cash balances and rows without a quantity. Copy ticker symbols exactly; do not guess spellings.

""" + (f'\nDOCUMENT:\n"""\n{document[:MAX_AI_CHARS]}\n"""' if document.strip() else "")
    try:
        # Gemini reads screenshots/scans far more accurately than Groq's vision model, which was
        # seen substituting look-alike tickers, so prefer it for images.
        extracted, provider = get_router().generate(
            prompt, ExtractedPortfolio, images=images, prefer=PREFERRED_VISION_PROVIDER if images else None
        )
    except ProviderError as exc:
        raise PortfolioImportError(
            f"{reason} AI extraction is unavailable right now ({exc}); try a CSV/Excel export or paste "
            "lines like 'RELIANCE.NS 20 2400'."
        ) from exc

    parsed = _Parsed(
        warnings=[f"{reason} Holdings were extracted by AI ({provider}) — check every row before saving."]
    )
    if images and provider != PREFERRED_VISION_PROVIDER:
        parsed.warnings.append(
            f"The more accurate image reader was busy, so a fallback model ({provider}) read this image; it can "
            "misread similar-looking tickers. Compare every ticker with your broker, or try again in a minute."
        )
    if truncated:
        parsed.warnings.append(f"The document was long; only the first {MAX_AI_CHARS:,} characters were read.")
    for item in extracted.holdings:
        # Bare tickers get the home market's suffix, same as tables; verify_tickers() then reverts any
        # that only exist without it (e.g. AAPL.NS -> AAPL) while keeping real ones (INFY.NS).
        ticker, _ = _suffix_ticker(item.ticker, item.exchange, default_country)
        if item.quantity > 0 and TICKER_PATTERN.match(ticker):
            cost = item.cost_basis if item.cost_basis is not None and item.cost_basis >= 0 else None
            parsed.holdings.append(
                ImportedHolding(
                    ticker=ticker,
                    quantity=item.quantity,
                    cost_basis=cost,
                    source_ticker=_source_if_changed(item.ticker, ticker),
                )
            )
    return parsed


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _delimited_rows(text: str) -> list[list[str]] | None:
    sample = "\n".join(text.splitlines()[:50])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in (",", "\t", ";", "|")}
        delimiter = max(counts, key=counts.get)
        if counts[delimiter] == 0:
            return None
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return rows if any(len(r) > 1 for r in rows) else None


def _excel_rows(content: bytes, engine: str) -> list[list[list]]:
    sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, dtype=object, engine=engine)
    return [df.where(pd.notna(df), "").values.tolist() for df in sheets.values()]


def _docx_content(content: bytes) -> tuple[list[list[list]], str]:
    import docx

    document = docx.Document(io.BytesIO(content))
    tables = [[[cell.text.strip() for cell in row.cells] for row in table.rows] for table in document.tables]
    text = "\n".join(p.text for p in document.paragraphs)
    for table in tables:  # include table text too, so the line parser and AI see everything
        text += "\n" + "\n".join(" ".join(row) for row in table)
    return tables, text


def _html_content(content: bytes) -> tuple[list[list[list]], str]:
    import lxml.html

    root = lxml.html.fromstring(_decode(content))
    for junk in root.xpath("//script|//style"):
        junk.drop_tree()
    tables = []
    for table in root.xpath("//table"):
        rows = [[cell.text_content().strip() for cell in tr.xpath("./th|./td")] for tr in table.xpath(".//tr")]
        tables.append([r for r in rows if r])
    text = "\n".join(line.strip() for line in root.text_content().splitlines() if line.strip())
    return tables, text


def _prepare_image(content: bytes) -> tuple[bytes, str]:
    """Normalise any screenshot/photo to a modest JPEG every vision provider accepts."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(content)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")  # honour phone rotation
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=88)
    return out.getvalue(), "image/jpeg"


def _json_rows(content: bytes) -> list[list] | None:
    data = json.loads(_decode(content))

    def find_records(node, depth=0):
        if isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
            return node
        if isinstance(node, list) and node and all(isinstance(x, list) for x in node):
            return node
        if isinstance(node, dict) and depth < 3:
            for value in node.values():
                found = find_records(value, depth + 1)
                if found:
                    return found
        return None

    records = find_records(data)
    if not records:
        return None
    if isinstance(records[0], list):
        return records
    keys: list[str] = []
    for record in records:
        keys.extend(k for k in record if k not in keys)
    return [keys] + [[record.get(k, "") for k in keys] for record in records]


def _pdf_content(content: bytes) -> tuple[list[list], str]:
    import pdfplumber

    rows: list[list] = []
    texts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend([[c or "" for c in row] for row in table])
            texts.append(page.extract_text() or "")
    return rows, "\n".join(texts)


IMAGE_SIGNATURES = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"BM")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")


MAX_SCANNED_PAGES = 3


def _pdf_page_images(content: bytes) -> list[tuple[bytes, str]]:
    import pdfplumber

    images = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages[:MAX_SCANNED_PAGES]:
            buffer = io.BytesIO()
            page.to_image(resolution=150).original.save(buffer, "PNG")
            images.append(_prepare_image(buffer.getvalue()))
    return images


def _detect_format(content: bytes, filename: str) -> str:
    """Sniff the real format from the bytes; the extension is only a tie-breaker."""
    import zipfile

    name = filename.lower()
    if content.startswith(b"%PDF"):
        return "pdf"
    if content.startswith(IMAGE_SIGNATURES) or (content[:4] == b"RIFF" and content[8:12] == b"WEBP") or (
        content[:4] in (b"II*\x00", b"MM\x00*")
    ):
        return "image"
    if content.startswith(b"PK\x03\x04"):  # xlsx, docx and ods are all zip containers
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                if "word/document.xml" in names:
                    return "word"
                if "mimetype" in names and b"opendocument.spreadsheet" in archive.read("mimetype"):
                    return "ods"
        except zipfile.BadZipFile:
            pass
        return "excel"
    if content.startswith(b"\xd0\xcf\x11\xe0"):
        return "excel-legacy"
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(IMAGE_EXTENSIONS):
        return "image"
    head = content[:2048].lstrip().lower()
    if name.endswith((".html", ".htm")) or head.startswith((b"<!doctype html", b"<html")) or b"<table" in head:
        return "html"
    if name.endswith(".json") or head[:1] in (b"{", b"["):
        return "json"
    return "text"


def _merge_duplicates(holdings: list[ImportedHolding]) -> tuple[list[ImportedHolding], int]:
    merged: dict[str, ImportedHolding] = {}
    duplicates = 0
    for holding in holdings:
        existing = merged.get(holding.ticker)
        if existing is None:
            merged[holding.ticker] = holding
            continue
        duplicates += 1
        quantity = existing.quantity + holding.quantity
        cost = None
        if existing.cost_basis is not None and holding.cost_basis is not None:
            cost = round((existing.cost_basis * existing.quantity + holding.cost_basis * holding.quantity) / quantity, 6)
        merged[holding.ticker] = existing.model_copy(update={"quantity": quantity, "cost_basis": cost})
    return list(merged.values()), duplicates


def _finish(parsed: _Parsed, source_format: str, method: str) -> PortfolioImportResult:
    holdings, duplicates = _merge_duplicates(parsed.holdings)
    if duplicates:
        parsed.warnings.append(f"Merged {duplicates} duplicate row(s) for the same ticker (quantities added).")
    if not holdings:
        raise PortfolioImportError("No holdings found. Make sure the file lists tickers and quantities.")
    return PortfolioImportResult(
        holdings=holdings,
        source_format=source_format,
        method=method,
        column_mapping=parsed.mapping,
        skipped=parsed.skipped[:MAX_SKIPPED_REPORTED],
        warnings=parsed.warnings,
    )


def import_portfolio(
    content: bytes | None = None,
    filename: str = "",
    text: str | None = None,
    default_country: str | None = None,
) -> PortfolioImportResult:
    if content is not None and len(content) > MAX_BYTES:
        raise PortfolioImportError(f"File is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    if content and filename.lower().endswith((".heic", ".heif")):
        raise PortfolioImportError("HEIC photos aren't supported yet; export the photo as JPEG or take a screenshot.")
    if not content and not (text and text.strip()):
        raise PortfolioImportError("Upload a file or paste your holdings.")

    if content:
        kind = _detect_format(content, filename)
    else:
        kind = "text"
        content = text.encode("utf-8")

    tables: list[list[list]] = []
    raw_text = ""
    try:
        if kind == "image":
            image = _prepare_image(content)
            reason = "Read from an image."
            return _finish(_ai_extract("", default_country, reason, images=[image]), "image", "ai")
        if kind == "pdf":
            pdf_rows, raw_text = _pdf_content(content)
            tables = [pdf_rows] if pdf_rows else []
            if not raw_text.strip() and not pdf_rows:  # scanned PDF: read the page images instead
                reason = "This PDF is a scan with no selectable text, so its pages were read as images."
                return _finish(_ai_extract("", default_country, reason, images=_pdf_page_images(content)), "pdf", "ai")
        elif kind in ("excel", "excel-legacy", "ods"):
            engine = {"excel": "openpyxl", "excel-legacy": "xlrd", "ods": "odf"}[kind]
            tables = _excel_rows(content, engine)
            raw_text = "\n".join(" | ".join(str(c) for c in row) for table in tables for row in table)
        elif kind == "word":
            tables, raw_text = _docx_content(content)
        elif kind == "html":
            tables, raw_text = _html_content(content)
        elif kind == "json":
            rows = _json_rows(content)
            tables = [rows] if rows else []
            raw_text = _decode(content)
        else:
            raw_text = _decode(content)
            rows = _delimited_rows(raw_text)
            tables = [rows] if rows else []
    except PortfolioImportError:
        raise
    except Exception as exc:  # corrupt/unsupported file
        raise PortfolioImportError(f"Couldn't read this file ({type(exc).__name__}: {exc}).") from exc

    # Plain text only counts as "csv" if a delimited table was actually used.
    source_format = {"excel-legacy": "excel", "ods": "excel"}.get(kind, kind)

    names_only = False
    for table in sorted(tables, key=len, reverse=True):
        parsed, needs_ai = _parse_table(table, default_country)
        if parsed.holdings:
            return _finish(parsed, "csv" if kind == "text" else source_format, "columns")
        names_only = names_only or needs_ai
    if names_only and kind == "text":
        source_format = "csv"

    if not names_only:
        lines = _parse_lines(raw_text, default_country)
        if lines:
            return _finish(lines, source_format, "lines")

    reason = (
        "The file lists company names rather than ticker symbols."
        if names_only
        else "No table with ticker and quantity columns was found."
    )
    return _finish(_ai_extract(raw_text, default_country, reason), source_format, "ai")


VERIFY_WORKERS = 8


def _has_prices(ticker: str) -> bool:
    try:
        return not price_data.fetch_price_history(ticker, "5d").closes.empty
    except Exception:  # noqa: BLE001 - treat any data-source failure as "not found"
        return False


def _alternatives(holding: ImportedHolding, default_country: str | None) -> list[str]:
    options = []
    if holding.source_ticker:  # the file's own spelling, e.g. VOO before we assumed VOO.NS
        options.append(_suffix_ticker(holding.source_ticker, None, None)[0])
    if default_country and "." not in holding.ticker:  # e.g. bare ITC that is really ITC.NS
        options.append(holding.ticker + get_country(default_country).default_suffix)
    return [o for o in dict.fromkeys(options) if o and o != holding.ticker]


def verify_tickers(result: PortfolioImportResult, default_country: str | None) -> PortfolioImportResult:
    """Check every ticker has market data; fix guessed exchange suffixes when the data shows the right
    listing, and flag tickers that can't be found so the user can correct them before saving."""
    holdings = result.holdings
    with ThreadPoolExecutor(VERIFY_WORKERS) as pool:
        primary = dict(zip([h.ticker for h in holdings], pool.map(_has_prices, [h.ticker for h in holdings])))
        options = {h.ticker: _alternatives(h, default_country) for h in holdings if not primary[h.ticker]}
        to_check = list(dict.fromkeys(o for opts in options.values() for o in opts))
        found = dict(zip(to_check, pool.map(_has_prices, to_check)))

    checked, corrected, missing = [], [], []
    for holding in holdings:
        if primary[holding.ticker]:
            checked.append(holding.model_copy(update={"price_found": True}))
            continue
        fix = next((o for o in options[holding.ticker] if found.get(o)), None)
        if fix:
            corrected.append(f"{holding.ticker} → {fix}")
            checked.append(
                holding.model_copy(
                    update={"ticker": fix, "price_found": True, "source_ticker": holding.source_ticker or holding.ticker}
                )
            )
        else:
            missing.append(holding.ticker)
            checked.append(holding.model_copy(update={"price_found": False}))

    warnings = list(result.warnings)
    if corrected:
        warnings.append("Corrected the market where only the other listing has price data: " + ", ".join(corrected) + ".")
    if missing:
        warnings.append(
            "No market data found for " + ", ".join(missing) + " — check the spelling or exchange suffix "
            "before saving (otherwise they're left out of the analysis)."
        )
    merged, _ = _merge_duplicates(checked)
    return result.model_copy(update={"holdings": merged, "warnings": warnings})
