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
import logging
import random
import secrets
import string
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ai.agents import LEVEL_NAMES, Agent, RuleAgent, create_agent
from backend.config import get_settings
from backend.ws.view import legal_actions_payload, masked_state, visible_event
from engine.actions import Action, encode_action
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


@dataclass
class Seat:
    index: int
    user_id: str | None = None
    name: str = ""
    bot_level: int | None = None  # set for bot seats
    agent: Agent | None = None
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
            "taken_over": self.taken_over, "user_id": self.user_id,
        }


SaveHook = Any  # callable(room, game_state) -> None, run in a worker thread


class Room:
    def __init__(self, room_id: str, code: str, kind: str, config: RoomConfig,
                 host_id: str | None, save_hook: SaveHook | None = None) -> None:
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
        self.rng = random.Random()
        self.tasks: set[asyncio.Task[Any]] = set()
        self.deadline: float | None = None
        self.decisions: dict[int, dict[str, Any]] = {}
        for i, lvl in enumerate(config.bot_levels):
            if lvl is not None:
                self.seats[i] = Seat(i, name=bot_name(i, lvl), bot_level=lvl,
                                     agent=create_agent(lvl))

    # ------------------------------------------------------------ seating
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
        self.game = start_hand(self.match, seed=self.rng.randrange(2**62))
        self.decisions = {}
        self.version += 1
        for seat in range(4):
            await self._send_seat(seat, "DEAL", {
                "hand": list(self.game.hands[seat]), "flowers": list(self.game.flowers[seat]),
            })
        await self._after_change([])

    async def handle(self, seat: int, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        payload = msg.get("payload") or {}
        if kind == "PING":
            await self._send_seat(seat, "PONG", {})
            return
        async with self.lock:
            if kind == "CHAT":
                text = str(payload.get("message", ""))[:200]
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
            else:
                await self._error(seat, "UNKNOWN_MESSAGE", f"unknown type {kind!r}")

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
        before = set(acting_players(self.game))
        self.game, events = apply_action(self.game, seat, action)
        if not set(acting_players(self.game)) <= before:
            self.deadline = None  # someone new must act: restart the clock
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
        if g.phase is Phase.ENDED:
            await self._hand_finished()
            return
        for target, seat in self._audience():
            await self._send(target, "STATE_UPDATE", masked_state(g, seat))
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
        }

    # ------------------------------------------------------------ bots & timers
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
            await self._broadcast("ROUND_DRAW", {"reason": result.get("reason")})
        for target, seat in self._audience():
            await self._send(target, "STATE_UPDATE", masked_state(g, seat))
        if self.save_hook is not None:
            seats = [s.public() if s else None for s in self.seats]
            hand_index = m.hands_played
            decisions = dict(self.decisions)
            try:
                await asyncio.to_thread(self.save_hook, self, g, hand_index, seats, decisions)
            except Exception:  # persistence must not break play
                log.exception("failed to save hand %s", g.game_id)
        self.match = finish_hand(m, g)
        await self._broadcast("ROOM_STATE", self.public())
        if self.match.finished:
            self.status = "GAME_END"
            await self._broadcast("GAME_END", {
                "final_scores": self.match.scores, "ranks": ranks(self.match.scores),
            })
            return
        self.status = "ROUND_END"
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

    async def close(self) -> None:
        for t in list(self.tasks):
            t.cancel()


_SEAT_NUMERALS = "一二三四"


def bot_name(seat: int, level: int) -> str:
    return f"電腦{_SEAT_NUMERALS[seat]}號（{LEVEL_NAMES.get(level, '')}）"


def _aid(a: Action) -> int:
    return encode_action(a)


class RoomManager:
    def __init__(self, save_hook: SaveHook | None = None) -> None:
        self.rooms: dict[str, Room] = {}
        self.by_code: dict[str, str] = {}
        self.save_hook = save_hook
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
        room = Room(room_id, code, kind, config, host_id, self.save_hook)
        self.rooms[room_id] = room
        self.by_code[code] = room_id
        return room

    def get(self, room_id: str) -> Room | None:
        return self.rooms.get(room_id)

    def get_by_code(self, code: str) -> Room | None:
        rid = self.by_code.get(code.upper())
        return self.rooms.get(rid) if rid else None

    def find_quick(self) -> Room | None:
        for r in self.rooms.values():
            if r.kind == "QUICK" and r.status == "WAITING" and any(s is None for s in r.seats):
                return r
        return None

    async def schedule_quick_start(self, room: Room) -> None:
        async def later() -> None:
            await asyncio.sleep(room.config.quick_wait)
            async with room.lock:
                if room.status == "WAITING":
                    await room._start_locked()

        room._spawn(later())

    async def shutdown(self) -> None:
        for r in self.rooms.values():
            await r.close()
