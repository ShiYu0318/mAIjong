"""Fail when a package drops below its coverage target (SPEC 11).

    uv run pytest --cov=engine --cov=backend --cov=ai --cov-report=json
    uv run python scripts/check_coverage.py coverage.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TARGETS = {"engine": 95.0, "backend": 80.0, "ai": 70.0}


def main() -> int:
    data = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else "coverage.json").read_text())
    totals = {pkg: [0, 0] for pkg in TARGETS}
    for name, info in data["files"].items():
        pkg = Path(name).parts[0]
        if pkg in totals:
            totals[pkg][0] += info["summary"]["num_statements"]
            totals[pkg][1] += info["summary"]["covered_lines"]
    failed = False
    for pkg, (stmts, covered) in totals.items():
        pct = 100.0 * covered / stmts if stmts else 0.0
        ok = pct >= TARGETS[pkg]
        failed |= not ok
        verdict = "ok" if ok else "BELOW TARGET"
        print(f"{pkg:<8} {pct:5.1f}%  (target {TARGETS[pkg]:.0f}%)  {verdict}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
