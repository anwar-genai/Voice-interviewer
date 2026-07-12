"""Voice SLO check: turn-latency percentiles from an agent-worker log.

The metrics hook already logs a ``turn_latency`` line per STT/LLM/TTS/EOU step;
this reads those lines back and holds p95 against the SLOs below — the
prod→eval loop at its simplest: telemetry in, pass/fail out.

    python run_agent.py dev > agent.log 2>&1   # capture a session
    python -m evals.voice_slo agent.log

Exits non-zero on any breach, so it can gate like the other suites.

ponytail: WER is not measured — it needs retained audio plus reference scripts,
which data minimization says we don't keep. STT accuracy is protected indirectly
(per-interview vocabulary + transcription-aware rubric, tests/test_stt_fairness.py);
add an audio golden-set here if accuracy complaints appear.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# p95 ceilings, seconds. eou_delay is the silence the user hears before the
# agent starts thinking (bounded by MAX_ENDPOINTING_DELAY_SECONDS = 4.0).
SLOS = {
    "eou_delay_s": 3.0,
    "llm_ttft_s": 1.5,
    "tts_ttfb_s": 1.5,
}

_METRIC = re.compile(r"(eou_delay_s|llm_ttft_s|tts_ttfb_s)=([0-9.]+)")


def _p(values: list[float], q: float) -> float:
    return sorted(values)[min(len(values) - 1, int(q * len(values)))]


def check(lines: list[str]) -> int:
    samples: dict[str, list[float]] = {name: [] for name in SLOS}
    for line in lines:
        if "turn_latency" not in line:
            continue
        for name, value in _METRIC.findall(line):
            samples[name].append(float(value))

    if not any(samples.values()):
        print("No turn_latency lines found — is this an agent-worker log?")
        return 2

    failed = False
    for name, ceiling in SLOS.items():
        values = samples[name]
        if not values:
            print(f"  [n/a]   {name}: no samples")
            continue
        p95 = _p(values, 0.95)
        ok = p95 <= ceiling
        failed |= not ok
        print(
            f"  [{'ok' if ok else 'FAIL'}]{' ' * (5 - len('ok' if ok else 'FAIL'))}"
            f"{name}: p50={_p(values, 0.5):.2f}s p95={p95:.2f}s "
            f"(SLO p95<={ceiling}s, n={len(values)})"
        )
    print("\nSLO check:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    return check(Path(argv[0]).read_text(encoding="utf-8", errors="replace").splitlines())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
