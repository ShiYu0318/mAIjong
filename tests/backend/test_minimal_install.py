"""The backend image installs only the `backend` extra: no numpy, no torch. Everything the
server imports at start-up must work without them (models load lazily when present)."""

from __future__ import annotations

import subprocess
import sys


def test_backend_starts_without_numpy_or_torch():
    code = (
        "import sys\n"
        "sys.modules['numpy'] = None\n"
        "sys.modules['torch'] = None\n"
        "import backend.main\n"
        "from ai.agents import create_agent\n"
        "for lvl in range(1, 6):\n"
        "    create_agent(lvl, seed=0)\n"
        "print('ok')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={"SECRET_KEY": "x-secret-key-that-is-long-enough-123456",
                              "PATH": "/usr/bin:/bin"}, timeout=120)
    assert out.returncode == 0 and "ok" in out.stdout, out.stderr[-2000:]
