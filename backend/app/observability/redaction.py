"""PII redaction for anything leaving the request path: logs and eval datasets.

Resumes and transcripts carry emails, phone numbers, and the candidate's name;
none of that belongs in the o11y layer or in an exported dataset.

ponytail: regexes for the identifier shapes this app's data actually contains,
plus caller-supplied known names (e.g. from the resume's first line); an NER
pass if free-text name detection ever becomes necessary.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Digit runs with phone punctuation. Requiring 9+ digits keeps resume date
# ranges ("2019 - 2023", 8 digits) intact while catching real numbers.
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)")


def _phone_sub(m: re.Match[str]) -> str:
    return "[phone]" if sum(c.isdigit() for c in m.group()) >= 9 else m.group()


def redact(text: str, *, names: Iterable[str] = ()) -> str:
    """Strip emails, phone numbers, and any of ``names`` from ``text``."""
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub(_phone_sub, text)
    for name in names:
        if name and len(name) > 1:
            text = re.sub(rf"\b{re.escape(name)}\b", "[name]", text, flags=re.IGNORECASE)
    return text
