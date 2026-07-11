"""The AI core: prompts and LLM calls, pure and importable.

No FastAPI, no LiveKit, no transport of any kind — so that guardrails, evals,
and tracing can wrap this one place. `evals/` imports directly from here.
"""

from .errors import InvalidInputError, LLMError
from .extraction import extract_job
from .feedback import generate_feedback
from .guardrails import require_groundable_transcript
from .interviewer import build_instructions, parse_room_metadata
from .schemas import InterviewContext, InterviewFeedback, ParsedJob, ParsedResume

__all__ = [
    "InterviewContext",
    "InterviewFeedback",
    "InvalidInputError",
    "LLMError",
    "ParsedJob",
    "ParsedResume",
    "build_instructions",
    "extract_job",
    "generate_feedback",
    "parse_room_metadata",
    "require_groundable_transcript",
]
