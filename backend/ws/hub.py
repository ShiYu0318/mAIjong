"""In-process room runtime: seats, match flow, bots, timers and broadcasting.

Each room owns an asyncio lock; every state change happens under it. Scheduled bot
moves and turn timers carry the state version they were created for and do nothing
if the game moved on in the meantime.

A Redis-backed implementation can replace RoomManager for multi-instance deployments;
the WebSocket layer only depends on the methods used here.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import random
import secrets
import string
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from ai.agents import LEVEL_NAMES, Agent, RuleAgent, create_agent
from ai.explainability.candidate_scorer import score_all_discards
from backend.config import get_settings
from backend.hints.llm_provider import describe_discard, get_provider
from backend.metrics import METRICS
from backend.security_middleware import clean_text
from backend.ws.store import NullStore, RoomStore
from backend.ws.view import (
    discard_waits,
    draw_summary,
    legal_actions_payload,
    masked_state,
    visible_event,
)
from engine.actions import Action, ActionType, decode_action, encode_action
from engine.game import (
    GameState,
    IllegalAction,
    Phase,
    acting_players,
    apply_action,
    get_legal_actions,
)
from engine.match import MatchState, finish_hand, new_match, ranks, start_hand
from engine.score import ScoringRules

log = logging.getLogger("maijong.hub")

HINT_COOLDOWN = 5.0
HINT_LIMIT_RANKED = 3
QUICK_RATING_RANGE = 200.0  # SPEC 13 OQ-09: quick match pairs within ±200 before bots fill


class Socket(Protocol):
    async def send_json(self, data: Any) -> None: ...


@dataclass
class RoomConfig:
    time_limit: float | None = 30.0
    rounds: int = 1
    base_points: int = 100
    tai_points: int = 50
    tai_cap: int | None = None
    bot_levels: list[int | None] = field(default_factory=lambda: [None, None, None, None])
    bot_delay: float = 0.6
    next_hand_delay: float = 4.0
    quick_wait: float = 30.0
    public: bool = False
    tutor: bool = False  # guided game: coach notes after every discard


@dataclass
class Seat:
    index: int
    user_id: str | None = None
    name: str = ""
    bot_level: int | None = None  # set for bot seats
    agent: Agent | None = None
    agent_id: str | None = None  # a stored (community or house) agent seated here
    sockets: list[Socket] = field(default_factory=list)
    disconnected_at: float | None = None
    taken_over: bool = False  # bot temporarily plays for a disconnected human
    extension_used: bool = False
    hints_used: int = 0
    last_hint_at: float = 0.0

    @property
    def is_bot(self) -> bool:
        return self.bot_level is not None

    @property
    def bot_controlled(self) -> bool:
        return self.is_bot or self.taken_over

    def public(self) -> dict[str, Any]:
        return {
            "seat": self.index, "name": self.name, "is_bot": self.is_bot,
            "bot_level": self.bot_level, "connected": bool(self.sockets) or self.is_bot,
            "taken_over": self.taken_over, "user_id": self.user_id, "agent_id": self.agent_id,
        }


SaveHook = Any  # callable(room, game_state) -> None, run in a worker thread


class Room:
    def __init__(self, room_id: str, code: str, kind: str, config: RoomConfig,
                 host_id: str | None, save_hook: SaveHook | None = None,
                 progress_hook: Any = None) -> None:
        self.id = room_id
        self.code = code
        self.kind = kind
        self.config = config
        self.host_id = host_id
        self.status = "WAITING"
        self.seats: list[Seat | None] = [None] * 4
        self.match: MatchState | None = None
        self.game: GameState | None = None
        self.version = 0
        self.lock = asyncio.Lock()
        self.spectators: list[Socket] = []
        self.save_hook = save_hook
        self.progress_hook = progress_hook  # (room, game, final_scores) -> {seat: events}
        self.rng = random.Random()
        self.tasks: set[asyncio.Task[Any]] = set()
        self.deadline: float | None = None
        self.decisions: dict[int, dict[str, Any]] = {}
        self.actions: list[list[int]] = []  # [seat, action_id] for exact replay
        self.arena_agents: dict[int, str] = {}  # seat → agents.id (ARENA rooms)
        self.scenario: dict[str, int] | None = None  # practice: start from (seed, step)
        self.match_end_hook: Any = None
        self.store: RoomStore = NullStore()
        self.hand_seed: int | None = None  # seed of the current hand (for recovery)
        self.hand_started_at: float | None = None  # wall clock, for games.result duration_s
        self.quick_ratings: list[float] = []  # ratings of people who joined a quick match
        self._dirty = False
        self._writer_task: asyncio.Task[None] | None = None
        for i, lvl in enumerate(config.bot_levels):
            if lvl is not None:
                self.seats[i] = Seat(i, name=bot_name(i, lvl), bot_level=lvl,
                                     agent=create_agent(lvl))

    # ------------------------------------------------------------ seating
    def attach_agent(self, seat: int, agent_row: Any) -> None:
        """Seat a stored agent (house bot or sandboxed submission)."""
        from backend.arena import agent_for_room

        self.seats[seat] = Seat(seat, name=agent_row.name, bot_level=3,
                                agent=agent_for_room(agent_row), agent_id=agent_row.id)
        self.config.bot_levels[seat] = 3

    def seat_of(self, user_id: str | None) -> int | None:
        for s in self.seats:
            if s and user_id and s.user_id == user_id:
                return s.index
        return None

    def join(self, user_id: str | None, name: str, seat: int | None = None) -> int:
        existing = self.seat_of(user_id)
        if existing is not None:
            return existing
        if self.status != "WAITING":
            raise ValueError("game already started")
        free = [i for i in range(4) if self.seats[i] is None]
        if seat is not None:
            if seat not in free:
                raise ValueError("seat taken")
            idx = seat
        elif free:
            idx = free[0]
        else:
            raise ValueError("room full")
        self.seats[idx] = Seat(idx, user_id=user_id, name=name)
        self._persist()
        return idx

    def public(self) -> dict[str, Any]:
        cfg = self.config
        return {
            "room_id": self.id, "code": self.code, "type": self.kind, "status": self.status,
            "host_id": self.host_id,
            "seats": [s.public() if s else None for s in self.seats],
            "config": {
                "time_limit": cfg.time_limit, "rounds": cfg.rounds,
                "base_points": cfg.base_points, "tai_points": cfg.tai_points,
                "tai_cap": cfg.tai_cap, "bot_levels": cfg.bot_levels,
            },
            "match": None if self.match is None else {
                "dealer": self.match.dealer, "dealer_streak": self.match.dealer_streak,
                "round_wind": self.match.round_wind, "hands_played": self.match.hands_played,
                "scores": self.match.scores, "finished": self.match.finished,
            },
        }

    # ------------------------------------------------------------ connections
    async def connect(self, seat: int | None, ws: Socket) -> None:
        async with self.lock:
            if seat is None:
                self.spectators.append(ws)
            else:
                st = self.seats[seat]
                assert st is not None
                if not st.sockets:  # the seat just came online: show it to everyone already here
                    await self._broadcast("ROOM_STATE", self.public())
                st.sockets.append(ws)
                since = st.disconnected_at
                reconnect = since is not None
                window = get_settings().reconnect_window_sec
                if since is not None and st.taken_over and time.time() - since <= window:
                    st.taken_over = False
                st.disconnected_at = None
                await self._send(ws, "JOINED", {"seat": seat, "room_code": self.code,
                                                "room": self.public()})
                if reconnect:
                    await self._broadcast("PLAYER_RECONNECTED", {"seat": seat})
            await self._sync_one(seat, ws)

    async def disconnect(self, seat: int | None, ws: Socket) -> None:
        async with self.lock:
            if seat is None:
                with contextlib.suppress(ValueError):
                    self.spectators.remove(ws)
                return
            st = self.seats[seat]
            if st is None:
                return
            with contextlib.suppress(ValueError):
                st.sockets.remove(ws)
            if st.sockets or st.is_bot:
                return
            st.disconnected_at = time.time()
            await self._broadcast("PLAYER_DISCONNECTED", {"seat": seat})
            if self.status == "IN_GAME":
                self._spawn(self._takeover_after_grace(seat, st.disconnected_at))

    async def _takeover_after_grace(self, seat: int, since: float) -> None:
        await asyncio.sleep(get_settings().grace_period_sec)
        async with self.lock:
            st = self.seats[seat]
            if st is None or st.disconnected_at != since or self.status != "IN_GAME":
                return
            st.taken_over = True
            if st.agent is None:
                st.agent = create_agent(get_settings().default_bot_level)
            await self._broadcast("SEAT_BOT_FILL", {"seat": seat,
                                                    "level": get_settings().default_bot_level})
            self._schedule_actors()

    # ------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        async with self.lock:
            await self._start_locked()

    async def _start_locked(self) -> None:
        if self.status != "WAITING":
            raise ValueError("already started")
        for i in range(4):
            if self.seats[i] is None:
                lvl = get_settings().default_bot_level
                self.seats[i] = Seat(i, name=bot_name(i, lvl), bot_level=lvl,
                                     agent=create_agent(lvl))
                self.config.bot_levels[i] = lvl
                await self._broadcast("SEAT_BOT_FILL", {"seat": i, "level": lvl})
        cfg = self.config
        self.match = new_match(
            first_dealer=self.rng.randrange(4), rounds=cfg.rounds,
            rules=ScoringRules(cfg.base_points, cfg.tai_points, cfg.tai_cap),
        )
        self.status = "IN_GAME"
        await self._broadcast("ROOM_STATE", self.public())
        await self._broadcast("GAME_START", {
            "seats": [s.public() for s in self.seats if s],
            "dealer": self.match.dealer, "round_wind": self.match.round_wind,
        })
        await self._new_hand()

    async def _new_hand(self) -> None:
        assert self.match is not None
        if self.scenario is not None and self.match.hands_played == 0:
            from ai.explainability.analysis import _replay_to

            # practice scenario: play on from a recorded self-play position (one hand only)
            self.game = _replay_to(self.scenario["seed"], self.scenario["step"])
            self.match.dealer = self.game.dealer
        else:
            self.hand_seed = self.rng.randrange(2**62)
            self.game = start_hand(self.match, seed=self.hand_seed)
        self.decisions = {}
        self.actions = []
        self.hand_started_at = time.time()
        self.version += 1
        for seat in range(4):
            await self._send_seat(seat, "DEAL", {
                "hand": list(self.game.hands[seat]), "flowers": list(self.game.flowers[seat]),
            })
        await self._after_change([])

    async def handle(self, seat: int, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        payload = msg.get("payload")
        if not isinstance(payload, dict):  # e.g. a bare string: treat as no payload
            payload = {}
        if kind == "PING":
            await self._send_seat(seat, "PONG", {})
            return
        if kind == "JOIN":  # the seat comes from the ws token; answer the handshake again
            await self._send_seat(seat, "JOINED", {"seat": seat, "room_code": self.code,
                                                   "room": self.public()})
            return
        async with self.lock:
            if kind == "CHAT":
                text = clean_text(str(payload.get("message", "")))
                if text:
                    await self._broadcast("CHAT", {"seat": seat, "message": text})
            elif kind == "ACTION":
                await self._human_action(seat, payload)
            elif kind == "EXTEND_TIME":
                st = self.seats[seat]
                if st and not st.extension_used and self.deadline is not None:
                    st.extension_used = True
                    self.deadline += 15
                    self._schedule_actors()
                    await self._send_seat(seat, "ACTION_REQUEST", self._request(seat))
            elif kind == "READY":
                await self._sync_one(seat, None)
            elif kind == "HINT_REQUEST":
                await self._hint(seat)
            else:
                await self._error(seat, "UNKNOWN_MESSAGE", f"unknown type {kind!r}")

    @property
    def ranked(self) -> bool:
        return self.kind in ("QUICK", "ARENA")

    async def _hint(self, seat: int) -> None:
        st = self.seats[seat]
        g = self.game
        if st is None or g is None or g.phase is not Phase.DISCARD or g.turn != seat:
            await self._error(seat, "HINT_UNAVAILABLE", "只有輪到你打牌時可以使用提示")
            return
        now = time.time()
        if now - st.last_hint_at < HINT_COOLDOWN:
            await self._error(seat, "HINT_COOLDOWN", "提示冷卻中，請稍候再試")
            return
        if self.ranked and st.hints_used >= HINT_LIMIT_RANKED:
            await self._error(seat, "HINT_LIMIT", "排名對局每場最多使用 3 次提示")
            return
        st.last_hint_at = now
        st.hints_used += 1
        cands = [c.to_dict() for c in score_all_discards(g, seat)]
        text = await get_provider().explain(cands)
        remaining = HINT_LIMIT_RANKED - st.hints_used if self.ranked else None
        await self._send_seat(seat, "HINT_RESULT", {
            "candidates": cands, "explanation": text, "remaining": remaining,
        })

    async def _human_action(self, seat: int, payload: dict[str, Any]) -> None:
        if self.game is None or self.status != "IN_GAME":
            await self._error(seat, "INVALID_ACTION", "no game in progress")
            return
        try:
            action = Action.from_dict(payload)
        except (KeyError, ValueError) as e:
            await self._error(seat, "INVALID_ACTION", str(e))
            return
        if seat not in acting_players(self.game):
            # duplicate or late action: ignore and resend the current request
            await self._sync_one(seat, None)
            return
        try:
            await self._apply(seat, action)
        except IllegalAction as e:
            await self._error(seat, "INVALID_ACTION", str(e))
            await self._sync_one(seat, None)

    async def _apply(self, seat: int, action: Action, decision: dict[str, Any] | None = None
                     ) -> None:
        assert self.game is not None
        seq = len(self.game.events)
        coach: list[dict[str, Any]] | None = None
        if self.config.tutor and action.type in (ActionType.DISCARD, ActionType.TING):
            coach = [c.to_dict() for c in score_all_discards(self.game, seat)]
        before = set(acting_players(self.game))
        self.game, events = apply_action(self.game, seat, action)
        self.actions.append([seat, encode_action(action)])
        if not set(acting_players(self.game)) <= before:
            self.deadline = None  # someone new must act: restart the clock
        if coach is not None and action.tile is not None:
            st = self.seats[seat]
            human = st is not None and not st.bot_controlled
            who = st.name if st is not None else ""
            # the structured fields let the client word the note in its own language
            note = {"seat": seat, "tile": action.tile,
                    "text": describe_discard(coach, action.tile, who, human),
                    "candidates": coach[:3], "who": who, "human": human,
                    "chosen": next((c for c in coach if c["tile"] == action.tile), None)}
            for s in self.seats:
                if s is not None and not s.is_bot:
                    await self._send_seat(s.index, "TUTOR_NOTE", note)
        if decision is not None:
            self.decisions[seq] = decision
        self.version += 1
        await self._after_change(events)

    async def _after_change(self, events: list[dict[str, Any]]) -> None:
        g = self.game
        assert g is not None
        for target, seat in self._audience():
            for ev in events:
                vis = visible_event(ev, seat)
                if vis is not None and ev["type"] != "HU":
                    await self._send(target, "PLAYER_ACTION", {
                        "player": ev.get("player"), "event": vis,
                    })
        if self._shared:
            for ev in events:
                vis = visible_event(ev, None)
                if vis is not None and ev["type"] != "HU":
                    await self._publish("PLAYER_ACTION", {"player": ev.get("player"),
                                                          "event": vis})
        if g.phase is Phase.ENDED:
            await self._hand_finished()
            return
        for target, seat in self._audience():
            await self._send(target, "STATE_UPDATE", masked_state(g, seat))
        await self._publish_view()
        self._persist()
        self._arm_deadline()  # before the requests go out, so they carry the deadline
        for seat in acting_players(g):
            st = self.seats[seat]
            if st is not None and not st.bot_controlled:
                await self._send_seat(seat, "ACTION_REQUEST", self._request(seat))
        self._schedule_actors()

    def _request(self, seat: int) -> dict[str, Any]:
        assert self.game is not None
        return {
            "player": seat,
            "legal_actions": legal_actions_payload(self.game, seat),
            "deadline": self.deadline,
            "waits": discard_waits(self.game, seat),
        }

    # ------------------------------------------------------------ bots & timers
    def _human_waiting(self) -> bool:
        """Whether a person (not a bot, not a forced ready-hand discard) must act now."""
        g = self.game
        if g is None or g.phase is Phase.ENDED:
            return False
        for seat in acting_players(g):
            st = self.seats[seat]
            if st is None or st.bot_controlled:
                continue
            if not (g.declared_ting[seat] and len(get_legal_actions(g, seat)) == 1):
                return True
        return False

    def _arm_deadline(self) -> None:
        if self.config.time_limit and self.deadline is None and self._human_waiting():
            self.deadline = time.time() + self.config.time_limit

    def _schedule_actors(self) -> None:
        g = self.game
        if g is None or g.phase is Phase.ENDED:
            return
        version = self.version
        human_waiting = False
        for seat in acting_players(g):
            st = self.seats[seat]
            assert st is not None
            legal = get_legal_actions(g, seat)
            forced = g.declared_ting[seat] and len(legal) == 1
            if st.bot_controlled or forced:
                delay = 0.0 if forced and not st.bot_controlled else self.config.bot_delay
                self._spawn(self._auto_move(seat, version, delay, timeout=False))
            else:
                human_waiting = True
        if human_waiting and self.config.time_limit:
            if self.deadline is None:
                self.deadline = time.time() + self.config.time_limit
            self._spawn(self._timeout(version, self.deadline))
        elif not human_waiting:
            self.deadline = None

    async def _auto_move(self, seat: int, version: int, delay: float, timeout: bool) -> None:
        if delay:
            await asyncio.sleep(delay)
        async with self.lock:
            if self.game is None or self.version != version:
                return
            await self._auto_move_locked(seat, timeout)

    async def _auto_move_locked(self, seat: int, timeout: bool) -> None:
        g = self.game
        if g is None or seat not in acting_players(g):
            return
        st = self.seats[seat]
        assert st is not None
        legal = get_legal_actions(g, seat)
        agent: Agent = st.agent if (st.agent and st.bot_controlled) else RuleAgent(0.0)
        try:
            action = agent.act(g, seat, legal)
        except Exception:  # a faulty agent must never stall the table
            log.exception("agent %s failed; falling back", agent.name)
            action = legal[0]
        decision = None
        if isinstance(agent, RuleAgent):
            scores = agent.scores(g, seat, legal)
            decision = {"agent": agent.name, "timeout": timeout,
                        "scores": {_aid(a): round(v, 3) for a, v in scores.items()},
                        "chosen": _aid(action)}
        await self._apply(seat, action, decision)

    async def _timeout(self, version: int, deadline: float) -> None:
        await asyncio.sleep(max(0.0, deadline - time.time()))
        async with self.lock:
            g = self.game
            if g is None or self.version != version or self.deadline != deadline:
                return
            pending = [p for p in acting_players(g)
                       if (st := self.seats[p]) is not None and not st.bot_controlled]
            for seat in pending:
                await self._error(seat, "TIMEOUT", "時間到，已替你自動行動")
                await self._auto_move_locked(seat, timeout=True)

    def _spawn(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        self.tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            log.exception("room task failed", exc_info=task.exception())

    # ------------------------------------------------------------ hand end
    async def _hand_finished(self) -> None:
        g, m = self.game, self.match
        assert g is not None and m is not None and g.result is not None
        self.deadline = None
        result = g.result
        METRICS.hand_finished(str(result["kind"]))
        if result["kind"] == "HU":
            await self._broadcast("WIN_DECLARED", {
                "winner": result["winner"], "loser": result.get("loser"),
                "hand": result["hand"], "melds": result["melds"], "flowers": result["flowers"],
                "win_tile": result["win_tile"], "self_draw": result["self_draw"],
                "flower_win": result["flower_win"],
                "tai_breakdown": result["tai_breakdown"], "dealer_tai": result["dealer_tai"],
                "tai_by_payer": result["tai_by_payer"], "payments": result["payments"],
            })
        else:
            await self._broadcast("ROUND_DRAW", draw_summary(g))
        for target, seat in self._audience():
            await self._send(target, "STATE_UPDATE", masked_state(g, seat))
        await self._publish_view()
        if self.save_hook is not None:
            seats = [s.public() if s else None for s in self.seats]
            hand_index = m.hands_played
            decisions = dict(self.decisions)
            actions = list(self.actions)
            try:
                await asyncio.to_thread(self.save_hook, self, g, hand_index, seats, decisions,
                                        actions)
            except Exception:  # persistence must not break play
                log.exception("failed to save hand %s", g.game_id)
        self.match = finish_hand(m, g)
        if self.scenario is not None:
            self.match.finished = True  # practice scenarios are a single hand
        if self.progress_hook is not None:
            final = list(self.match.scores) if self.match.finished else None
            try:
                updates = await asyncio.to_thread(self.progress_hook, self, g, final)
            except Exception:  # progression must not break play
                log.exception("progress update failed in room %s", self.id)
                updates = {}
            for seat, events in updates.items():
                await self._send_seat(seat, "PROGRESS", {"events": events})
        await self._broadcast("ROOM_STATE", self.public())
        if self.match.finished:
            self.status = "GAME_END"
            METRICS.match_finished()
            await self._broadcast("GAME_END", {
                "final_scores": self.match.scores, "ranks": ranks(self.match.scores),
            })
            if self.match_end_hook is not None:
                try:
                    await asyncio.to_thread(self.match_end_hook, self, list(self.match.scores))
                except Exception:
                    log.exception("match end hook failed for room %s", self.id)
            self._close_agents()
            self._persist()
            return
        self.status = "ROUND_END"
        self._persist()
        await self._broadcast("NEXT_HAND_IN", {"seconds": self.config.next_hand_delay})
        self._spawn(self._next_hand_later(self.version))

    async def _next_hand_later(self, version: int) -> None:
        await asyncio.sleep(self.config.next_hand_delay)
        async with self.lock:
            if self.version != version or self.status != "ROUND_END":
                return
            assert self.match is not None
            self.status = "IN_GAME"
            await self._broadcast("NEXT_ROUND", {
                "dealer": self.match.dealer, "dealer_streak": self.match.dealer_streak,
                "round_wind": self.match.round_wind,
            })
            await self._new_hand()

    # ------------------------------------------------------------ messaging
    def _audience(self) -> list[tuple[Socket, int | None]]:
        out: list[tuple[Socket, int | None]] = []
        for st in self.seats:
            if st is not None:
                out.extend((ws, st.index) for ws in st.sockets)
        out.extend((ws, None) for ws in self.spectators)
        return out

    async def _send(self, ws: Socket, kind: str, payload: dict[str, Any]) -> None:
        try:
            await ws.send_json({"type": kind, "payload": payload})
        except Exception:  # closed socket; disconnect() cleans up
            log.debug("send failed", exc_info=True)

    async def _send_seat(self, seat: int, kind: str, payload: dict[str, Any]) -> None:
        st = self.seats[seat]
        if st is not None:
            for ws in list(st.sockets):
                await self._send(ws, kind, payload)

    async def _broadcast(self, kind: str, payload: dict[str, Any]) -> None:
        for ws, _ in self._audience():
            await self._send(ws, kind, payload)
        await self._publish(kind, payload)

    # ------------------------------------------------------------ shared state (Redis)
    @property
    def _shared(self) -> bool:
        """Persisted and relayed: real tables only (not arena or practice scenarios)."""
        return not isinstance(self.store, NullStore) and self.kind != "ARENA" \
            and self.scenario is None

    async def _publish(self, kind: str, payload: dict[str, Any]) -> None:
        if not self._shared:
            return
        try:
            await self.store.publish(self.id, {"type": kind, "payload": payload})
        except Exception:  # Redis trouble must never stop the table
            log.warning("publish failed for room %s", self.id, exc_info=True)

    async def _publish_view(self) -> None:
        if not self._shared or self.game is None:
            return
        view = masked_state(self.game, None)
        try:
            await self.store.set_view(self.id, view)
            await self.store.publish(self.id, {"type": "STATE_UPDATE", "payload": view})
        except Exception:
            log.warning("publish failed for room %s", self.id, exc_info=True)

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id, "code": self.code, "kind": self.kind, "host_id": self.host_id,
            "status": self.status, "config": asdict(self.config),
            "seats": [None if s is None else {
                "index": s.index, "user_id": s.user_id, "name": s.name,
                "bot_level": s.bot_level, "extension_used": s.extension_used,
                "hints_used": s.hints_used,
            } for s in self.seats],
            "match": None if self.match is None else asdict(self.match),
            "hand_seed": self.hand_seed, "actions": list(self.actions),
            "game_id": self.game.game_id if self.game is not None else None,
            "public": self.public(),
            "quick_ratings": list(self.quick_ratings),
        }

    def _persist(self) -> None:
        """Mark the room dirty; one writer task saves the newest snapshot (no reordering)."""
        if not self._shared:
            return
        self._dirty = True
        if self._writer_task is None or self._writer_task.done():
            try:
                self._writer_task = asyncio.get_running_loop().create_task(self._write())
            except RuntimeError:  # called outside the event loop; the next change saves it
                return

    async def _write(self) -> None:
        while self._dirty:
            self._dirty = False
            try:
                if self.status == "GAME_END":
                    await self.store.delete(self.id)
                else:
                    await self.store.save(self.id, self.snapshot())
            except Exception:
                log.warning("saving room %s failed", self.id, exc_info=True)
                return

    def restore(self, snap: dict[str, Any]) -> None:
        """Rebuild seats, match and the current hand from a snapshot (see RoomManager)."""
        from engine.score import ScoringRules as Rules

        self.status = snap["status"]
        now = time.time()
        for raw in snap["seats"]:
            if raw is None or raw["bot_level"] is not None:
                continue  # bots were recreated from config.bot_levels
            self.seats[raw["index"]] = Seat(
                raw["index"], user_id=raw["user_id"], name=raw["name"],
                extension_used=raw["extension_used"], hints_used=raw["hints_used"],
                disconnected_at=now if self.status in ("IN_GAME", "ROUND_END") else None)
        m = snap["match"]
        if m is not None:
            self.match = MatchState(**{**m, "rules": Rules(**m["rules"])})
        self.hand_seed = snap["hand_seed"]
        self.quick_ratings = list(snap.get("quick_ratings") or [])
        if self.status == "IN_GAME" and self.match is not None and self.hand_seed is not None:
            g = start_hand(self.match, seed=self.hand_seed)
            if snap.get("game_id"):
                g = dataclasses.replace(g, game_id=snap["game_id"])  # replays stay linked
            for seat, aid in snap["actions"]:
                g, _ = apply_action(g, seat, decode_action(aid))
            self.game = g
            self.actions = [list(a) for a in snap["actions"]]
        self.version += 1

    async def resume(self) -> None:
        """Restart bots, timers and reconnect windows after a restore."""
        async with self.lock:
            for st in self.seats:
                if st is not None and st.disconnected_at is not None:
                    self._spawn(self._takeover_after_grace(st.index, st.disconnected_at))
            if self.status == "ROUND_END":
                self._spawn(self._next_hand_later(self.version))
            elif self.status == "IN_GAME" and self.game is not None:
                if self.game.phase is Phase.ENDED:
                    await self._hand_finished()
                else:
                    self._schedule_actors()

    async def _error(self, seat: int, code: str, message: str) -> None:
        await self._send_seat(seat, "ERROR", {"code": code, "message": message})

    async def _sync_one(self, seat: int | None, ws: Socket | None) -> None:
        """Send the current state (and pending request) to one seat / socket."""
        targets: list[Socket] = []
        if ws is not None:
            targets = [ws]
        elif seat is not None and (st := self.seats[seat]) is not None:
            targets = list(st.sockets)
        for t in targets:
            await self._send(t, "ROOM_STATE", self.public())
            if self.game is not None:
                await self._send(t, "STATE_UPDATE", masked_state(self.game, seat))
                if seat is not None and seat in acting_players(self.game):
                    await self._send(t, "ACTION_REQUEST", self._request(seat))

    def _close_agents(self) -> None:
        for st in self.seats:
            closer = getattr(st.agent, "close", None) if st else None
            if callable(closer):
                closer()

    async def close(self) -> None:
        for t in list(self.tasks):
            t.cancel()
        self._close_agents()


_SEAT_NUMERALS = "一二三四"


def bot_name(seat: int, level: int) -> str:
    return f"電腦{_SEAT_NUMERALS[seat]}號（{LEVEL_NAMES.get(level, '')}）"


def _aid(a: Action) -> int:
    return encode_action(a)


class RoomManager:
    def __init__(self, save_hook: SaveHook | None = None, store: RoomStore | None = None,
                 progress_hook: Any = None) -> None:
        self.rooms: dict[str, Room] = {}
        self.by_code: dict[str, str] = {}
        self.save_hook = save_hook
        self.store: RoomStore = store or NullStore()
        self.progress_hook = progress_hook
        self._quick_lock = asyncio.Lock()

    def _code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            if code not in self.by_code:
                return code

    def create(self, room_id: str, kind: str, config: RoomConfig, host_id: str | None,
               code: str | None = None) -> Room:
        code = code or self._code()
        room = Room(room_id, code, kind, config, host_id, self.save_hook, self.progress_hook)
        room.store = self.store
        self.rooms[room_id] = room
        self.by_code[code] = room_id
        return room

    def get(self, room_id: str) -> Room | None:
        return self.rooms.get(room_id)

    def get_by_code(self, code: str) -> Room | None:
        rid = self.by_code.get(code.upper())
        return self.rooms.get(rid) if rid else None

    def find_quick(self, rating: float = 1500.0) -> Room | None:
        """A waiting quick-match room whose players average within ±QUICK_RATING_RANGE of
        `rating` (the closest one); None means open a new room."""
        best: tuple[float, Room] | None = None
        for r in self.rooms.values():
            if r.kind != "QUICK" or r.status != "WAITING" or all(s is not None for s in r.seats):
                continue
            avg = sum(r.quick_ratings) / len(r.quick_ratings) if r.quick_ratings else rating
            gap = abs(avg - rating)
            if gap <= QUICK_RATING_RANGE and (best is None or gap < best[0]):
                best = (gap, r)
        return best[1] if best else None

    async def schedule_quick_start(self, room: Room) -> None:
        async def later() -> None:
            await asyncio.sleep(room.config.quick_wait)
            async with room.lock:
                if room.status == "WAITING":
                    await room._start_locked()

        room._spawn(later())

    async def restore(self) -> int:
        """Bring back this instance's rooms from Redis after a restart; returns the count."""
        restored = 0
        for snap in await self.store.load_owned():
            if snap.get("status") == "GAME_END":
                await self.store.delete(snap["id"])
                continue
            try:
                cfg = RoomConfig(**snap["config"])
                room = self.create(snap["id"], snap["kind"], cfg, snap["host_id"], snap["code"])
                room.restore(snap)
                await room.resume()
                restored += 1
            except Exception:  # a broken snapshot must not block startup
                log.exception("could not restore room %s", snap.get("id"))
                self.rooms.pop(snap.get("id", ""), None)
                await self.store.delete(snap.get("id", ""))
        return restored

    async def shutdown(self) -> None:
        for r in self.rooms.values():
            await r.close()
        await self.store.close()
