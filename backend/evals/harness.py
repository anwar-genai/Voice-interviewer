"""Shared result types and reporting for the eval suites."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FieldResult:
    field_name: str
    expected: str
    actual: str | None
    passed: bool


@dataclass
class CaseResult:
    case_id: str
    fields: list[FieldResult] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(f.passed for f in self.fields)


@dataclass
class SuiteResult:
    name: str
    threshold: float
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def errors(self) -> list[CaseResult]:
        return [c for c in self.cases if c.error]

    @property
    def score(self) -> float:
        """Field-level accuracy over the cases that actually ran."""
        scored = [c for c in self.cases if not c.error]
        total = sum(len(c.fields) for c in scored)
        if total == 0:
            return 0.0
        passed = sum(sum(1 for f in c.fields if f.passed) for c in scored)
        return passed / total

    @property
    def passed(self) -> bool:
        """An errored case is an infrastructure failure, not a quality signal.

        It must not be averaged away into a passing score, so any error fails
        the suite regardless of how the remaining cases scored.
        """
        return not self.errors and self.score >= self.threshold


def print_report(result: SuiteResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    scored = len(result.cases) - len(result.errors)
    print(f"\n=== {result.name}: {status} "
          f"(score {result.score:.0%} over {scored}/{len(result.cases)} cases, "
          f"threshold {result.threshold:.0%}) ===")

    for case in result.cases:
        if case.error:
            print(f"  [error] {case.case_id}: {case.error}")
            continue
        if case.passed:
            print(f"  [ok]    {case.case_id}")
            continue

        print(f"  [fail]  {case.case_id}")
        for f in case.fields:
            if not f.passed:
                print(f"            {f.field_name}: expected ~{f.expected!r}, got {f.actual!r}")
