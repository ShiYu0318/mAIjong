"""Line-delimited JSON protocol for running untrusted agents in a separate process.

Child:   python -m maijong_sdk.sandbox <submission_dir>
Parent:  writes {"op": "start"|"decide"|"end", ...} lines, reads one JSON reply per line.

The platform enforces the 5 s decision limit and kills the process on violations.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from maijong_sdk.base_agent import BaseAgent
from maijong_sdk.types import Action, GameInfo, Observation


def load_submission(directory: Path) -> BaseAgent:
    manifest = json.loads((directory / "manifest.json").read_text())
    module_file = directory / "agent.py"
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location("submitted_agent", module_file)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cls = getattr(mod, manifest["agent_class"])
    agent = cls()
    if not isinstance(agent, BaseAgent):
        raise TypeError("agent_class must subclass maijong_sdk.BaseAgent")
    return agent


def serve(agent: BaseAgent, stdin: Any = None, stdout: Any = None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        op = msg.get("op")
        reply: dict[str, Any] = {"ok": True}
        try:
            if op == "start":
                agent.on_game_start(msg["seat"], GameInfo(**msg["info"]))
            elif op == "decide":
                obs = Observation.from_dict(msg["obs"])
                legal = [Action.from_dict(a) for a in msg["legal"]]
                reply["action"] = agent.decide(obs, legal).to_dict()
            elif op == "end":
                agent.on_game_end(msg["scores"])
            elif op == "quit":
                break
        except Exception as e:  # report the failure, the parent decides what to do
            reply = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        stdout.write(json.dumps(reply) + "\n")
        stdout.flush()


def main() -> None:
    serve(load_submission(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
