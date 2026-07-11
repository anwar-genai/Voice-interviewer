import io

import pdfplumber
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl

from ..core.config import MissingConfigError, get_settings
from ..llm import InvalidInputError, LLMError, ParsedJob, ParsedResume, extract_job

router = APIRouter(prefix="/utils", tags=["utils"])


class ParseLinkRequest(BaseModel):
    url: HttpUrl


class ParseJobTextRequest(BaseModel):
    text: str


def _fetch_page_text(url: str) -> str:
    """Fetch a URL and reduce it to visible text."""
    settings = get_settings()
    try:
        response = requests.get(
            url,
            timeout=settings.fetch_timeout_seconds,
            headers={"User-Agent": settings.fetch_user_agent},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {exc}")

    soup = BeautifulSoup(response.text, "html.parser")
    lines = (line.strip() for line in soup.get_text("\n").splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)


def _extract_pdf_text(content: bytes) -> str:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages_text).strip()


def _extract_job_or_http_error(posting_text: str) -> ParsedJob:
    """Run extraction, translating LLM-core errors into HTTP status codes."""
    try:
        return extract_job(posting_text)
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MissingConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/parse-job-text-llm", response_model=ParsedJob)
def parse_job_text_llm(body: ParseJobTextRequest):
    """Extract structured job fields from a pasted job description."""
    return _extract_job_or_http_error(body.text)


@router.post("/parse-link-llm", response_model=ParsedJob)
def parse_link_llm(body: ParseLinkRequest):
    """Fetch a job posting URL and extract structured job fields from it."""
    cleaned = _fetch_page_text(str(body.url))

    if len(cleaned) < 100:
        # Many sites (e.g. LinkedIn) require auth/JS; advise pasting raw text instead.
        raise HTTPException(
            status_code=422,
            detail="Content not accessible. Try /utils/parse-job-text-llm with pasted description.",
        )

    return _extract_job_or_http_error(cleaned)


@router.post("/parse-pdf", response_model=ParsedResume)
def parse_pdf(body: ParseLinkRequest):
    """Extract text from a PDF resume hosted at a URL."""
    try:
        response = requests.get(str(body.url), timeout=get_settings().fetch_timeout_seconds)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch PDF: {exc}")

    if "pdf" not in response.headers.get("content-type", ""):
        raise HTTPException(status_code=400, detail="URL does not point to a PDF")

    try:
        text = _extract_pdf_text(response.content)
    except Exception as exc:  # noqa: BLE001 - pdfplumber raises many types
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {exc}")

    return ParsedResume(text=text)


@router.post("/parse-pdf-upload", response_model=ParsedResume)
def parse_pdf_upload(file: UploadFile = File(...)):
    """Extract text from an uploaded PDF resume."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        text = _extract_pdf_text(file.file.read())
    except Exception as exc:  # noqa: BLE001 - pdfplumber raises many types
        raise HTTPException(status_code=400, detail=f"Failed to parse uploaded PDF: {exc}")
    finally:
        file.file.close()

    return ParsedResume(text=text)
