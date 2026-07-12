import hashlib
import io
import logging

import pdfplumber
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl

from ..core.config import MissingConfigError, get_settings
from ..core.ratelimit import rate_limit
from ..llm import InvalidInputError, LLMError, ParsedJob, ParsedResume, extract_job

logger = logging.getLogger("interview.utils")

# rate_limit also authenticates, so every /utils endpoint is protected + throttled.
router = APIRouter(prefix="/utils", tags=["utils"], dependencies=[Depends(rate_limit)])


class ParseLinkRequest(BaseModel):
    url: HttpUrl


class ParseJobTextRequest(BaseModel):
    text: str


def _fetch_bytes_capped(url: str, limit: int, *, expect_pdf: bool = False) -> tuple[bytes, str]:
    """Fetch a URL, refusing bodies larger than ``limit``. Returns (bytes, content_type)."""
    settings = get_settings()
    try:
        with requests.get(
            url,
            timeout=settings.fetch_timeout_seconds,
            headers={"User-Agent": settings.fetch_user_agent},
            stream=True,
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            declared = response.headers.get("content-length")
            if declared and int(declared) > limit:
                raise HTTPException(status_code=413, detail="Remote file is too large")
            if expect_pdf and "pdf" not in content_type:
                raise HTTPException(status_code=400, detail="URL does not point to a PDF")

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                total += len(chunk)
                if total > limit:
                    raise HTTPException(status_code=413, detail="Remote file is too large")
                chunks.append(chunk)
            return b"".join(chunks), content_type
    except requests.RequestException:
        logger.warning("Failed to fetch %s", url, exc_info=True)
        raise HTTPException(status_code=400, detail="Could not fetch the URL")


def _fetch_page_text(url: str) -> str:
    """Fetch a URL and reduce it to visible text, bounded by the JD length limit."""
    limit = get_settings().max_job_text_chars
    content, _ = _fetch_bytes_capped(url, limit * 4)  # markup is larger than its text
    soup = BeautifulSoup(content, "html.parser")
    lines = (line.strip() for line in soup.get_text("\n").splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = "\n".join(chunk for chunk in chunks if chunk)
    return text[:limit]


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
    except MissingConfigError:
        logger.error("LLM not configured")
        raise HTTPException(status_code=500, detail="Extraction service is not configured")
    except LLMError:
        logger.exception("Job extraction failed")
        raise HTTPException(status_code=502, detail="Extraction service failed")


# Cost control: re-practicing the same job is the product's core loop, and every
# repeat parse of an identical JD was a paid LLM call. Successful extractions are
# cached by input hash; failures are never cached.
# ponytail: in-process dict, cleared when full — fine for the one API machine
# fly.toml pins; move to Redis alongside the rate limiter if the API scales out.
_extract_cache: dict[str, ParsedJob] = {}
_EXTRACT_CACHE_MAX = 256


def _extract_job_cached(posting_text: str) -> ParsedJob:
    key = hashlib.sha256(posting_text.encode()).hexdigest()
    hit = _extract_cache.get(key)
    if hit is not None:
        return hit
    result = _extract_job_or_http_error(posting_text)
    if len(_extract_cache) >= _EXTRACT_CACHE_MAX:
        _extract_cache.clear()
    _extract_cache[key] = result
    return result


@router.post("/parse-job-text-llm", response_model=ParsedJob)
def parse_job_text_llm(body: ParseJobTextRequest):
    """Extract structured job fields from a pasted job description."""
    if len(body.text) > get_settings().max_job_text_chars:
        raise HTTPException(status_code=413, detail="Job description is too long")
    return _extract_job_cached(body.text)


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

    return _extract_job_cached(cleaned)


@router.post("/parse-pdf", response_model=ParsedResume)
def parse_pdf(body: ParseLinkRequest):
    """Extract text from a PDF resume hosted at a URL."""
    settings = get_settings()
    content, _ = _fetch_bytes_capped(str(body.url), settings.max_pdf_bytes, expect_pdf=True)

    try:
        text = _extract_pdf_text(content)
    except Exception:  # noqa: BLE001 - pdfplumber raises many types
        logger.warning("Failed to parse PDF from URL", exc_info=True)
        raise HTTPException(status_code=400, detail="Could not parse the PDF")

    return ParsedResume(text=text[: settings.max_resume_chars])


@router.post("/parse-pdf-upload", response_model=ParsedResume)
async def parse_pdf_upload(file: UploadFile = File(...)):
    """Extract text from an uploaded PDF resume."""
    settings = get_settings()
    if not (file.filename or "").lower().endswith(".pdf") or "pdf" not in (file.content_type or ""):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Read at most one byte past the limit so we can detect (and reject) oversize files.
    content = await file.read(settings.max_pdf_bytes + 1)
    await file.close()
    if len(content) > settings.max_pdf_bytes:
        raise HTTPException(status_code=413, detail="PDF is too large")

    try:
        text = _extract_pdf_text(content)
    except Exception:  # noqa: BLE001 - pdfplumber raises many types
        logger.warning("Failed to parse uploaded PDF", exc_info=True)
        raise HTTPException(status_code=400, detail="Could not parse the uploaded PDF")

    return ParsedResume(text=text[: settings.max_resume_chars])
