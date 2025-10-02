from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, HttpUrl
import requests
from bs4 import BeautifulSoup
import io
import pdfplumber
import os
import json


router = APIRouter(prefix="/utils", tags=["utils"])


class ParseLinkRequest(BaseModel):
    url: HttpUrl


class ParsedJob(BaseModel):
    job_title: str | None = None
    job_type: str | None = None
    location: str | None = None
    start_date: str | None = None
    qualifications: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None


@router.post("/parse-link", response_model=ParsedJob)
def parse_link(body: ParseLinkRequest):
    try:
        response = requests.get(
            str(body.url),
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            },
        )
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {exc}")

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n")
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    cleaned = "\n".join(chunk for chunk in chunks if chunk)

    # Heuristic extraction (placeholder until LLM structured parsing is wired)
    def find_section(keyword: str) -> str | None:
        lowered = cleaned.lower()
        idx = lowered.find(keyword)
        if idx == -1:
            return None
        window = cleaned[idx: idx + 1000]
        return window

    return ParsedJob(
        job_title=None,
        job_type=None,
        location=None,
        start_date=None,
        qualifications=find_section("qualification"),
        responsibilities=find_section("responsibilit"),
        benefits=find_section("benefit"),
    )


class ParsePdfRequest(BaseModel):
    # base64 PDF content could be used later; for now, accept URL
    url: HttpUrl


class ParsedResume(BaseModel):
    text: str


@router.post("/parse-pdf", response_model=ParsedResume)
def parse_pdf(body: ParsePdfRequest):
    try:
        response = requests.get(str(body.url), timeout=30)
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch PDF: {exc}")

    content_type = response.headers.get("content-type", "")
    if "pdf" not in content_type:
        raise HTTPException(status_code=400, detail="URL does not point to a PDF")

    try:
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]
        text = "\n\n".join(pages_text).strip()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {exc}")

    return ParsedResume(text=text)


@router.post("/parse-pdf-upload", response_model=ParsedResume)
def parse_pdf_upload(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        content = file.file.read()
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]
        text = "\n\n".join(pages_text).strip()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse uploaded PDF: {exc}")
    finally:
        file.file.close()

    return ParsedResume(text=text)


class ParseJobTextRequest(BaseModel):
    text: str


def _llm_extract_job_from_text(text: str) -> ParsedJob:
    try:
        from cerebras.cloud.sdk import Cerebras  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Cerebras SDK not available: {exc}")

    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="CEREBRAS_API_KEY not configured")

    client = Cerebras(api_key=api_key)

    job_schema = {
        "type": "object",
        "properties": {
            "job title": {"type": "string"},
            "job type": {"type": "string", "enum": ["full-time", "part-time", "contract", "internship"]},
            "location": {"type": "string"},
            "start date": {"type": "string"},
            "qualifications": {"type": "string"},
            "responsibilities": {"type": "string"},
            "benefits": {"type": "string"},
        },
        "required": ["job title"],
        "additionalProperties": False,
    }

    completion = client.chat.completions.create(
        model=os.environ.get("CEREBRAS_MODEL", "llama3.3-70b"),
        messages=[
            {"role": "system", "content": f"You are a link summarizing agent. Extract job information from: {text}"},
            {"role": "user", "content": "Summarize the relevant job information in the required JSON schema."},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "job_schema", "strict": True, "schema": job_schema},
        },
    )

    try:
        content = completion.choices[0].message.content  # type: ignore[index]
        data = json.loads(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM output: {exc}")

    return ParsedJob(
        job_title=data.get("job title"),
        job_type=data.get("job type"),
        location=data.get("location"),
        start_date=data.get("start date"),
        qualifications=data.get("qualifications"),
        responsibilities=data.get("responsibilities"),
        benefits=data.get("benefits"),
    )


@router.post("/parse-job-text-llm", response_model=ParsedJob)
def parse_job_text_llm(body: ParseJobTextRequest):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text is empty")
    return _llm_extract_job_from_text(body.text)


@router.post("/parse-link-llm", response_model=ParsedJob)
def parse_link_llm(body: ParseLinkRequest):
    try:
        resp = requests.get(
            str(body.url),
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            },
        )
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {exc}")

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text("\n")
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    cleaned = "\n".join(chunk for chunk in chunks if chunk)

    if not cleaned or len(cleaned) < 100:
        # Many sites (e.g., LinkedIn) require auth/JS; advise pasting raw text instead
        raise HTTPException(status_code=422, detail="Content not accessible. Try /utils/parse-job-text-llm with pasted description.")

    return _llm_extract_job_from_text(cleaned)

