"""Data shapes shared by the LLM core, the routers, and the eval harness.

These live with the AI core rather than in the routers so that `evals/` can
import them without pulling in FastAPI.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ParsedJob(BaseModel):
    job_title: str | None = None
    job_type: str | None = None
    location: str | None = None
    start_date: str | None = None
    qualifications: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None


class ParsedResume(BaseModel):
    text: str


class InterviewFeedback(BaseModel):
    strengths: list[str]
    improvements: list[str]
    overall_score: int = Field(ge=1, le=10)
    technical_score: int = Field(ge=1, le=10)
    communication_score: int = Field(ge=1, le=10)
    recommendations: list[str]


class InterviewContext(BaseModel):
    """Everything the interviewer agent needs to personalize a session."""

    job: dict[str, Any] = Field(default_factory=dict)
    resume: str = ""
