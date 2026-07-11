import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.auth import require_user
from ..core.config import MissingConfigError
from ..core.ratelimit import rate_limit
from ..llm import InterviewFeedback, InvalidInputError, LLMError, generate_feedback

logger = logging.getLogger("interview.feedback")

# Every feedback endpoint requires an authenticated user.
router = APIRouter(prefix="/feedback", tags=["feedback"], dependencies=[Depends(require_user)])


class GenerateFeedbackRequest(BaseModel):
    job_context: dict[str, Any]
    candidate_resume: str
    interview_transcript: str


@router.post("/generate", response_model=InterviewFeedback)
def generate_interview_feedback(request: GenerateFeedbackRequest, _: str = Depends(rate_limit)):
    """Score a completed interview transcript against the feedback rubric."""
    try:
        return generate_feedback(
            job=request.job_context,
            resume=request.candidate_resume,
            transcript=request.interview_transcript,
        )
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MissingConfigError:
        logger.error("LLM not configured")
        raise HTTPException(status_code=500, detail="Feedback service is not configured")
    except LLMError:
        logger.exception("Feedback generation failed")
        raise HTTPException(status_code=502, detail="Feedback service failed")


class InterviewMetrics(BaseModel):
    total_questions: int
    response_time_avg: float
    technical_depth: int
    communication_clarity: int
    engagement_level: int


class MetricsRequest(BaseModel):
    transcript: str


@router.post("/metrics", response_model=InterviewMetrics)
def calculate_interview_metrics(request: MetricsRequest):
    """Cheap heuristic counts over a transcript. No LLM involved."""
    transcript = request.transcript
    words = transcript.split()
    sentences = [s for s in transcript.split(".") if s.strip()]

    return InterviewMetrics(
        total_questions=transcript.count("?"),
        response_time_avg=len(words) / max(len(sentences), 1) * 0.5,
        technical_depth=min(
            10,
            transcript.count("technical") + transcript.count("experience") + transcript.count("project"),
        ),
        communication_clarity=min(
            10,
            transcript.count("explain") + transcript.count("describe") + transcript.count("example"),
        ),
        engagement_level=min(
            10,
            transcript.count("yes") + transcript.count("absolutely") + transcript.count("definitely"),
        ),
    )
