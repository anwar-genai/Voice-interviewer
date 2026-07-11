# Evals

Offline quality checks for the LLM surfaces. A sibling of `tests/`, not shipped
with the app: these import `app.llm.*` directly and call real providers.

Today this is a seed — a tiny golden-set for job extraction, which is all that is
possible until feedback is wired (Phase 3) and the full harness lands (Phase 4).

## Run

```bash
cd backend
python -m evals.runner              # all suites
python -m evals.runner extraction   # one suite
```

Needs `CEREBRAS_API_KEY`. Exits non-zero when a suite scores below its threshold,
so CI can gate prompt changes on it.

## Layout

```
evals/
  datasets/extraction_golden.json   # cases: posting text -> expected fields
  extraction/                       # the extraction suite
  runner.py                         # CLI entry point
```

## Adding a case

Append to `datasets/extraction_golden.json`. Only the fields you list in
`expected` are scored, so a case can assert on `job_title` alone.
