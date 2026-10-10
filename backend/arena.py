"""Arena: rated matches between submitted agents (SPEC 07.1, 07.2, 07.4).

Submitted agents always run in the sandbox (separate process, 5 s per decision).
House agents (owner None, manifest {"house": "<spec>"}) are built-in rule bots that keep
the ladder populated. A match is one East round; placement comes from final scores.
"""

from __future__ import annotations

import hashlib
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maijong_sdk.types import GameInfo, observe
from maijong_sdk.validation import AgentFailure, RemoteAgent
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.elo import update_elo
from ai.simulate import make_agent
from backend.models import Agent, EloHistory, Game, new_id, now
from engine.actions import Action, ActionType
from engine.game import GameState, Phase, acting_players, apply_action, get_legal_actions
from engine.match import finish_hand, new_match, ranks, start_hand

log = logging.getLogger("maijong.arena")

HOUSE_AGENTS = {"官方 Bot 普通": "lv3", "官方 Bot 入門": "lv2", "官方 Bot 高手": "rule"}
MAX_VIOLATIONS = 3
FAST_DECISION = 0.001  # seconds; flagged when the hand is complex


def ensure_house_agents(db: Session) -> list[Agent]:
    out = []
    for name, spec in HOUSE_AGENTS.items():
        a = db.scalar(select(Agent).where(Agent.owner_id.is_(None), Agent.name == name))
        if a is None:
            a = Agent(name=name, owner_id=None, manifest={"house": spec,
                                                          "description": "平台內建規則型 AI"},
                      status="ACTIVE")
            db.add(a)
        out.append(a)
    db.commit()
    return out


def verify_model_hash(agent: Agent) -> bool:
    """P10-8: the stored model must still match the hash recorded at submission."""
    if not agent.submission_path or agent.model_sha256 is None:
        return True
    model = Path(agent.submission_path) / "model.pt"
    return model.exists() and hashlib.sha256(model.read_bytes()).hexdigest() == agent.model_sha256


def pick_table(db: Session, rng: random.Random) -> list[Agent]:
    """Four agents with close ratings, preferring those with fewer games."""
    active = db.scalars(select(Agent).where(Agent.status == "ACTIVE")).all()
    if len(active) < 4:
        return []
    anchor = min(active, key=lambda a: (a.games_played, rng.random()))
    rest = sorted((a for a in active if a.id != anchor.id),
                  key=lambda a: (abs(a.elo - anchor.elo), a.games_played, rng.random()))
    return [anchor, *rest[:3]]


@dataclass
class SeatRunner:
    """Adapts a submitted (sandboxed) or house agent to the engine loop."""

    agent: Agent
    remote: RemoteAgent | None = None
    house: Any = None
    violations: list[str] = field(default_factory=list)
    times: list[float] = field(default_factory=list)
    fast_flags: int = 0

    @classmethod
    def create(cls, agent: Agent, seed: int) -> SeatRunner:
        house = agent.manifest.get("house")
        if house:
            return cls(agent, house=make_agent(house, seed))
        assert agent.submission_path is not None
        return cls(agent, remote=RemoteAgent(Path(agent.submission_path)))

    def start(self, seat: int, s: GameState) -> None:
        if self.remote is not None:
            try:
                self.remote.start(seat, GameInfo(seat, s.seat_wind(seat), s.round_wind,
                                                 s.dealer))
            except AgentFailure as e:
                self.violations.append(f"start: {e}")
                self._restart()

    def _restart(self) -> None:
        if self.remote is not None:
            self.remote.close()
            assert self.agent.submission_path is not None
            self.remote = RemoteAgent(Path(self.agent.submission_path))

    def act(self, s: GameState, seat: int) -> Action:
        legal = get_legal_actions(s, seat)
        if self.house is not None:
            chosen: Action = self.house.act(s, seat, legal)
            return chosen
        assert self.remote is not None
        t0 = time.perf_counter()
        try:
            a = self.remote.decide(observe(s, seat).to_dict(), legal)
        except AgentFailure as e:
            self.violations.append(str(e))
            self._restart()
            return next((x for x in legal if x.type is ActionType.PASS), legal[0])
        dt = time.perf_counter() - t0
        self.times.append(dt)
        if dt < FAST_DECISION and len(legal) > 8:
            self.fast_flags += 1
        return a

    def end(self, scores: list[int]) -> None:
        if self.remote is not None:
            try:
                self.remote.end(scores)
            except AgentFailure as e:
                self.violations.append(f"end: {e}")

    def close(self) -> None:
        if self.remote is not None:
            self.remote.close()


def play_match(agents: list[Agent], seed: int, rounds: int = 1
               ) -> tuple[list[int], list[GameState], list[SeatRunner]]:
    """Play one match; returns final scores, hands and the seat runners (for stats)."""
    rng = random.Random(seed)
    runners = [SeatRunner.create(a, seed * 4 + i) for i, a in enumerate(agents)]
    m = new_match(first_dealer=rng.randrange(4), rounds=rounds)
    hands: list[GameState] = []
    try:
        while not m.finished:
            s = start_hand(m, seed=rng.randrange(2**62))
            for p, r in enumerate(runners):
                r.start(p, s)
            while s.phase is not Phase.ENDED:
                p = acting_players(s)[0]
                s, _ = apply_action(s, p, runners[p].act(s, p))
            assert s.result is not None
            for r in runners:
                r.end(list(s.result["payments"]))
            hands.append(s)
            m = finish_hand(m, s)
            if len(hands) > 40:  # runaway dealer streaks are capped by the rules anyway
                break
    finally:
        for r in runners:
            r.close()
    return m.scores, hands, runners


def record_match(db: Session, agents: list[Agent], scores: list[int], hands: list[GameState],
                 runners: list[SeatRunner], kind: str = "ARENA") -> dict[str, Any]:
    order = ranks(scores)
    before = [a.elo for a in agents]
    after = update_elo(before, order, [a.games_played for a in agents])
    seats = [{"seat": i, "name": a.name, "agent_id": a.id, "is_bot": True, "user_id": None}
             for i, a in enumerate(agents)]
    match_id = new_id()
    last_game: Game | None = None
    for i, s in enumerate(hands):
        last_game = Game(id=s.game_id, room_id=None, round_wind=s.round_wind, dealer_seq=i,
                         dealer_streak=s.dealer_streak, seed=str(s.seed), seats=seats,
                         result={**(s.result or {}), "match_id": match_id, "kind_tag": kind},
                         is_public=True)
        db.add(last_game)
    db.flush()
    for a, b, e, place, r in zip(agents, before, after, order, runners, strict=True):
        a.elo = e
        a.games_played += 1
        db.add(EloHistory(agent_id=a.id, game_id=last_game.id if last_game else None,
                          elo_before=b, elo_after=e, placement=place, recorded_at=now()))
        if r.violations or r.fast_flags:
            log_ = a.manifest.get("fair_play", {"violations": 0, "fast_flags": 0})
            log_ = {"violations": log_["violations"] + len(r.violations),
                    "fast_flags": log_["fast_flags"] + r.fast_flags,
                    "last": r.violations[-3:]}
            a.manifest = {**a.manifest, "fair_play": log_}
            if log_["violations"] >= MAX_VIOLATIONS:
                a.status = "BANNED"
    db.commit()
    return {"match_id": match_id, "agents": [a.id for a in agents], "scores": scores,
            "ranks": order, "elo_before": before, "elo_after": after, "hands": len(hands)}


def run_arena_match(db: Session, seed: int | None = None) -> dict[str, Any] | None:
    """Schedule and play one rated match (P10-1). Returns None if no table can be formed."""
    ensure_house_agents(db)
    rng = random.Random(seed)
    agents = pick_table(db, rng)
    if not agents:
        return None
    for a in agents:
        if not verify_model_hash(a):
            a.status = "BANNED"
            a.manifest = {**a.manifest, "fair_play": {"reason": "model hash mismatch"}}
            db.commit()
            return None
    scores, hands, runners = play_match(agents, rng.randrange(2**31))
    return record_match(db, agents, scores, hands, runners)


class SandboxAgent:
    """Engine-side Agent (act(state, seat, legal)) backed by a sandboxed submission."""

    def __init__(self, agent: Agent) -> None:
        self.name = agent.name
        self.runner = SeatRunner.create(agent, seed=0)

    def act(self, state: GameState, seat: int, legal: list[Action]) -> Action:
        return self.runner.act(state, seat)

    def close(self) -> None:
        self.runner.close()


def agent_for_room(agent: Agent) -> Any:
    house = agent.manifest.get("house")
    return make_agent(house, 0) if house else SandboxAgent(agent)
