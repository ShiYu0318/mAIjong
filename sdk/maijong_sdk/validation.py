"""Run a submission in a child process and check it obeys the rules (SPEC 06.4 / P9-5).

Uses Docker with networking disabled when available (MAIJONG_SANDBOX=docker); otherwise
a plain subprocess with resource limits. Each decision must arrive within 5 seconds.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from engine.actions import Action
from engine.game import Phase, acting_players, apply_action, get_legal_actions, new_game
from maijong_sdk.agents import RandomAgent
from maijong_sdk.types import GameInfo, observe

DECISION_LIMIT = 5.0
MEMORY_LIMIT = 2 * 1024**3


class AgentFailure(RuntimeError):
    pass


def _limits() -> None:  # runs in the child before exec
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (ImportError, ValueError, OSError):
        pass


class RemoteAgent:
    """Talks to `python -m maijong_sdk.sandbox <dir>` over stdin/stdout."""

    def __init__(self, directory: Path, limit: float = DECISION_LIMIT) -> None:
        self.limit = limit
        self.decision_times: list[float] = []
        use_docker = os.environ.get("MAIJONG_SANDBOX") == "docker" and shutil.which("docker")
        if use_docker:
            cmd = ["docker", "run", "--rm", "-i", "--network", "none", "--memory", "2g",
                   "-v", f"{directory.resolve()}:/submission:ro",
                   os.environ.get("MAIJONG_SANDBOX_IMAGE", "maijong-sandbox"),
                   "python", "-m", "maijong_sdk.sandbox", "/submission"]
            preexec = None
        else:
            cmd = [sys.executable, "-m", "maijong_sdk.sandbox", str(directory)]
            preexec = _limits if os.name == "posix" and sys.platform != "darwin" else None
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, preexec_fn=preexec)

    def _call(self, msg: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        import selectors

        sel = selectors.DefaultSelector()
        sel.register(self.proc.stdout, selectors.EVENT_READ)
        if not sel.select(timeout):
            self.close()
            raise AgentFailure(f"no reply within {timeout:.0f}s")
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise AgentFailure(f"agent process exited: {err[-500:]}")
        reply: dict[str, Any] = json.loads(line)
        if not reply.get("ok"):
            raise AgentFailure(reply.get("error", "agent error"))
        return reply

    def start(self, seat: int, info: GameInfo) -> None:
        self._call({"op": "start", "seat": seat, "info": info.__dict__}, 30.0)

    def decide(self, obs_dict: dict[str, Any], legal: list[Action]) -> Action:
        t0 = time.perf_counter()
        reply = self._call({"op": "decide", "obs": obs_dict,
                            "legal": [a.to_dict() for a in legal]}, self.limit)
        self.decision_times.append(time.perf_counter() - t0)
        action = Action.from_dict(reply["action"])
        if action not in legal:
            raise AgentFailure(f"illegal action {action}")
        return action

    def end(self, scores: list[int]) -> None:
        self._call({"op": "end", "scores": scores}, 30.0)

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()


def validate_submission(directory: Path, games: int = 10, seed: int = 0) -> dict[str, Any]:
    """Play `games` hands against random opponents; report pass/fail and timings."""
    report: dict[str, Any] = {"passed": False, "games": 0, "errors": []}
    if not (directory / "agent.py").exists() or not (directory / "manifest.json").exists():
        report["errors"].append("submission needs agent.py and manifest.json")
        return report
    remote = RemoteAgent(directory)
    rng = random.Random(seed)
    try:
        for k in range(games):
            seat = k % 4
            s = new_game(rng.randrange(2**31))
            remote.start(seat, GameInfo(seat, s.seat_wind(seat), s.round_wind, s.dealer))
            others = {p: RandomAgent(seed * 10 + k * 4 + p) for p in range(4) if p != seat}
            while s.phase is not Phase.ENDED:
                p = acting_players(s)[0]
                legal = get_legal_actions(s, p)
                obs = observe(s, p)
                a = remote.decide(obs.to_dict(), legal) if p == seat else \
                    others[p].decide(obs, legal)
                s, _ = apply_action(s, p, a)
            assert s.result is not None
            remote.end(list(s.result["payments"]))
            report["games"] += 1
        report["passed"] = True
    except AgentFailure as e:
        report["errors"].append(str(e))
    finally:
        remote.close()
    times = remote.decision_times
    report["decisions"] = len(times)
    report["max_decision_s"] = round(max(times), 4) if times else None
    report["mean_decision_s"] = round(sum(times) / len(times), 5) if times else None
    return report
