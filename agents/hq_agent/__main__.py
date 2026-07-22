"""Run: PYTHONPATH=sdk:agents uv run python -m hq_agent "fleet health summary" """

from __future__ import annotations

import sys

from hq_agent.agent import run_once


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    prompt = " ".join(args).strip() or (
        "Give a short fleet health summary: call fleet_overview, griffin_anomalies, "
        "and signoz_status. Label Griffin as MAD. List any model proposals."
    )
    result = run_once(prompt)
    content = getattr(result, "content", None) or str(result)
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
