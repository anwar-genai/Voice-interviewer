"""Job-posting extraction. Pure and importable: no FastAPI, no transport."""

from __future__ import annotations

from .client import structured_completion
from .errors import InvalidInputError
from .prompts import JOB_SCHEMA, build_extraction_messages
from .schemas import ParsedJob


def extract_job(posting_text: str) -> ParsedJob:
    """Extract structured job fields from raw job-posting text."""
    if not posting_text.strip():
        raise InvalidInputError("Job posting text is empty")

    data = structured_completion(
        messages=build_extraction_messages(posting_text),
        schema=JOB_SCHEMA,
        schema_name="job_schema",
    )

    # The schema uses human-readable keys; the API model uses snake_case.
    return ParsedJob(
        job_title=data.get("job title"),
        job_type=data.get("job type"),
        location=data.get("location"),
        start_date=data.get("start date"),
        qualifications=data.get("qualifications"),
        responsibilities=data.get("responsibilities"),
        benefits=data.get("benefits"),
    )
