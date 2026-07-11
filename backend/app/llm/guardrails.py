"""Output-side safety for the wired feedback flow (Phase 3).

Feedback can only be *grounded* in what the candidate actually said. The biggest
groundedness failure is scoring a transcript where the candidate barely spoke:
the model has nothing to cite, so it invents strengths. We refuse to score that
case instead of shipping hallucinated praise.

Output safety (no defamatory / discriminatory content) and on-task moderation of
the live agent are handled in the prompts (``prompts.py``); a content-moderation
API is the upgrade path if prompt-level control proves insufficient.
"""

from __future__ import annotations

from .errors import InvalidInputError

# Below this many words of candidate speech there isn't enough to assess.
MIN_CANDIDATE_WORDS = 20


def require_groundable_transcript(candidate_text: str) -> None:
    """Raise if the candidate said too little to give grounded feedback."""
    if len(candidate_text.split()) < MIN_CANDIDATE_WORDS:
        raise InvalidInputError(
            "Not enough candidate responses to give grounded feedback yet — "
            "complete more of the interview and try again."
        )
