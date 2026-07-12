"""CLI entry point for the eval suites.

    python -m evals.runner              # all suites
    python -m evals.runner extraction   # one suite

Exits non-zero if any suite scores below its threshold, so CI can gate on it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from app.observability import configure_logging

from .extraction import eval_extraction
from .fairness import eval_fairness
from .feedback import eval_feedback
from .harness import SuiteResult, print_report
from .interviewer import eval_interviewer

SUITES: dict[str, Callable[[], SuiteResult]] = {
    "extraction": eval_extraction.run,
    "interviewer": eval_interviewer.run,
    "feedback": eval_feedback.run,
    "fairness": eval_fairness.run,
}


def main(argv: list[str]) -> int:
    configure_logging()

    requested = argv or list(SUITES)
    unknown = [name for name in requested if name not in SUITES]
    if unknown:
        print(f"Unknown suite(s): {', '.join(unknown)}. Available: {', '.join(SUITES)}")
        return 2

    results = []
    for name in requested:
        result = SUITES[name]()
        print_report(result)
        results.append(result)

    failed = [r.name for r in results if not r.passed]
    if failed:
        errored = sum(len(r.errors) for r in results)
        detail = f" ({errored} case(s) errored)" if errored else ""
        print(f"\n{len(failed)} suite(s) failed: {', '.join(failed)}{detail}")
        return 1

    print(f"\nAll {len(results)} suite(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
