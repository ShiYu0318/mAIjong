"""Player progression (docs design §8): levels, coins, daily bonus, missions, achievements
and cosmetics. Coins only unlock cosmetics: no wagering, no cash value, no lootboxes.

Everything is driven by two hooks called by the room hub: `record_hand` after each hand
and `record_match` after a full game. Both return client events (level-ups, completed
missions, unlocked achievements) that the hub sends to the player's seat.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.models import User, UserProgress

TZ = ZoneInfo("Asia/Taipei")
MAX_LEVEL = 99

# ------------------------------------------------------------------ levels & ranks


def xp_for_next(level: int) -> int:
    return 100 + 40 * (level - 1)


RANKS: list[tuple[str, str, float]] = [  # id, name, minimum rating
    ("novice", "新手", float("-inf")),
    ("adept", "熟手", 1450),
    ("skilled", "好手", 1550),
    ("expert", "高手", 1650),
    ("king", "雀王", 1750),
    ("god", "雀神", 1900),
]


def rank_for(rating: float) -> dict[str, Any]:
    i = 0
    while i + 1 < len(RANKS) and rating >= RANKS[i + 1][2]:
        i += 1
    rid, name, lo = RANKS[i]
    nxt = RANKS[i + 1] if i + 1 < len(RANKS) else None
    low = lo if lo != float("-inf") else 1350.0
    progress = 1.0 if nxt is None else max(0.0, min(1.0, (rating - low) / (nxt[2] - low)))
    return {"id": rid, "name": name, "next": nxt[1] if nxt else None,
            "next_at": nxt[2] if nxt else None, "progress": progress}


# ------------------------------------------------------------------ catalogs


@dataclass(frozen=True)
class MissionDef:
    id: str
    name: str
    target: int
    reward: int


MISSION_POOL = [
    MissionDef("hands", "打完 6 手", 6, 100),
    MissionDef("wins", "胡牌 2 次", 2, 150),
    MissionDef("self_draw", "自摸 1 次", 1, 150),
    MissionDef("big_win", "胡 5 台以上 1 次", 1, 200),
    MissionDef("ting", "宣告聽牌 3 次", 3, 120),
    MissionDef("match", "打完一場", 1, 120),
    MissionDef("first", "拿下第一名 1 次", 1, 250),
]
MISSIONS = {m.id: m for m in MISSION_POOL}
DAILY_MISSIONS = 3


@dataclass(frozen=True)
class AchievementDef:
    id: str
    name: str
    description: str
    reward: int


ACHIEVEMENTS = [
    AchievementDef("first_win", "初胡", "第一次胡牌", 200),
    AchievementDef("first_tsumo", "一摸到底", "第一次自摸", 200),
    AchievementDef("ten_tai", "十台大牌", "單手 10 台以上", 500),
    AchievementDef("full_flush", "清一色", "胡清一色", 400),
    AchievementDef("all_pungs", "碰碰胡", "胡碰碰胡", 300),
    AchievementDef("big_honors", "大三元／大四喜", "胡大三元或大四喜", 800),
    AchievementDef("eight_flowers", "八仙過海", "胡八仙過海", 800),
    AchievementDef("heaven", "天胡地胡", "胡天胡、地胡或人胡", 1000),
    AchievementDef("ten_matches", "十將老手", "打完 10 場", 300),
    AchievementDef("hundred_hands", "百手", "打完 100 手", 300),
    AchievementDef("level_10", "等級 10", "達到等級 10", 300),
    AchievementDef("level_30", "等級 30", "達到等級 30", 800),
]
ACHIEVEMENT_BY_ID = {a.id: a for a in ACHIEVEMENTS}
TAI_ACHIEVEMENTS = {"T24": "full_flush", "T29": "all_pungs", "T21": "big_honors",
                    "T19": "big_honors", "T13": "eight_flowers", "T15": "heaven",
                    "T16": "heaven", "T17": "heaven"}

SHOP: dict[str, list[dict[str, Any]]] = {
    "tile_back": [
        {"id": "jade", "name": "翡翠", "price": 0},
        {"id": "sapphire", "name": "寶藍", "price": 800},
        {"id": "rouge", "name": "胭脂紅", "price": 800},
        {"id": "midnight", "name": "午夜黑", "price": 1500},
        {"id": "gilded", "name": "鎏金", "price": 2000},
    ],
    "table": [
        {"id": "emerald", "name": "翡翠絨", "price": 0},
        {"id": "ocean", "name": "深海藍", "price": 1000},
        {"id": "wine", "name": "酒紅", "price": 1000},
        {"id": "amethyst", "name": "紫晶", "price": 1500},
    ],
    "win_effect": [
        {"id": "gold", "name": "金光", "price": 0},
        {"id": "fireworks", "name": "煙火", "price": 1200},
        {"id": "sakura", "name": "櫻花", "price": 1200},
        {"id": "thunder", "name": "雷光", "price": 2000},
    ],
}
DEFAULT_EQUIPPED = {slot: items[0]["id"] for slot, items in SHOP.items()}

HAND_XP, WIN_XP, TAI_XP, TSUMO_XP = 10, 20, 2, 10
MATCH_XP = {1: 60, 2: 40, 3: 25, 4: 15}
MATCH_COINS = {1: 300, 2: 150, 3: 80, 4: 40}
BONUS_BASE, BONUS_STEP, BONUS_MAX_DAYS = 500, 50, 7


def today(now: datetime | None = None) -> date:
    return (now or datetime.now(TZ)).astimezone(TZ).date()


# ------------------------------------------------------------------ state


def get_progress(db: Session, user: User) -> UserProgress:
    p = db.get(UserProgress, user.id)
    if p is None:
        p = UserProgress(user_id=user.id, equipped=dict(DEFAULT_EQUIPPED),
                         owned=[f"{s}:{i}" for s, i in DEFAULT_EQUIPPED.items()],
                         achievements=[], missions=[], stats={})
        db.add(p)
        db.flush()
    return p


def _missions_for(user_id: str, day: date) -> list[dict[str, Any]]:
    picks = random.Random(f"{user_id}:{day.isoformat()}").sample(MISSION_POOL, DAILY_MISSIONS)
    return [{"id": m.id, "progress": 0, "claimed": False} for m in picks]


def ensure_today(p: UserProgress, now: datetime | None = None) -> None:
    day = today(now).isoformat()
    if p.missions_day != day:
        p.missions_day = day
        p.missions = _missions_for(p.user_id, today(now))


def bonus_status(p: UserProgress, now: datetime | None = None) -> dict[str, Any]:
    t = today(now)
    last = date.fromisoformat(p.bonus_day) if p.bonus_day else None
    streak = p.bonus_streak + 1 if last == t - timedelta(days=1) else 1
    amount = BONUS_BASE + BONUS_STEP * (min(streak, BONUS_MAX_DAYS) - 1)
    available = last != t
    return {"available": available, "amount": amount,
            "streak": streak if available else p.bonus_streak}


def claim_bonus(p: UserProgress, now: datetime | None = None) -> int:
    status = bonus_status(p, now)
    if not status["available"]:
        raise ValueError("bonus already claimed today")
    p.bonus_day = today(now).isoformat()
    p.bonus_streak = status["streak"]
    p.coins += status["amount"]
    return int(status["amount"])


def claim_mission(p: UserProgress, mission_id: str, now: datetime | None = None) -> int:
    ensure_today(p, now)
    missions = [dict(m) for m in p.missions]
    for m in missions:
        if m["id"] == mission_id:
            d = MISSIONS[mission_id]
            if m["claimed"]:
                raise ValueError("already claimed")
            if m["progress"] < d.target:
                raise ValueError("mission not complete")
            m["claimed"] = True
            p.missions = missions
            p.coins += d.reward
            return d.reward
    raise KeyError(mission_id)


def buy(p: UserProgress, slot: str, item: str) -> int:
    entry = next((x for x in SHOP.get(slot, []) if x["id"] == item), None)
    if entry is None:
        raise KeyError(f"{slot}:{item}")
    key = f"{slot}:{item}"
    if key in p.owned:
        raise ValueError("already owned")
    if p.coins < entry["price"]:
        raise ValueError("not enough coins")
    p.coins -= entry["price"]
    p.owned = [*p.owned, key]
    return int(entry["price"])


def equip(p: UserProgress, slot: str, item: str) -> None:
    if f"{slot}:{item}" not in p.owned:
        raise ValueError("not owned")
    p.equipped = {**p.equipped, slot: item}


# ------------------------------------------------------------------ game hooks


def _add_xp(p: UserProgress, amount: int, events: list[dict[str, Any]]) -> None:
    p.xp += amount
    while p.level < MAX_LEVEL and p.xp >= xp_for_next(p.level):
        p.xp -= xp_for_next(p.level)
        p.level += 1
        reward = p.level * 20
        p.coins += reward
        events.append({"type": "LEVEL_UP", "level": p.level, "coins": reward})
        for lvl, aid in ((10, "level_10"), (30, "level_30")):
            if p.level >= lvl:
                _unlock(p, aid, events)


def _unlock(p: UserProgress, achievement: str, events: list[dict[str, Any]]) -> None:
    if achievement in p.achievements:
        return
    a = ACHIEVEMENT_BY_ID[achievement]
    p.achievements = [*p.achievements, achievement]
    p.coins += a.reward
    events.append({"type": "ACHIEVEMENT", "id": a.id, "name": a.name, "coins": a.reward})


def _bump(p: UserProgress, mission: str, n: int, events: list[dict[str, Any]]) -> None:
    missions = [dict(m) for m in p.missions]
    for m in missions:
        if m["id"] == mission and not m["claimed"]:
            target = MISSIONS[mission].target
            before = m["progress"]
            m["progress"] = min(target, before + n)
            if before < target <= m["progress"]:
                events.append({"type": "MISSION_DONE", "id": mission,
                               "name": MISSIONS[mission].name, "coins": MISSIONS[mission].reward})
    p.missions = missions


def _stat(p: UserProgress, key: str, n: int = 1) -> int:
    stats = dict(p.stats)
    value = int(stats.get(key, 0)) + n
    stats[key] = value
    p.stats = stats
    return value


def record_hand(db: Session, user: User, seat: int, result: dict[str, Any], declared: bool,
                now: datetime | None = None) -> list[dict[str, Any]]:
    """Progress for one finished hand from `seat`'s point of view."""
    p = get_progress(db, user)
    ensure_today(p, now)
    events: list[dict[str, Any]] = []
    xp = HAND_XP
    hands = _stat(p, "hands")
    _bump(p, "hands", 1, events)
    if declared:
        _bump(p, "ting", 1, events)
    if result.get("kind") == "HU" and result.get("winner") == seat:
        items = result.get("tai_breakdown") or []
        tai = sum(int(i.get("tai", 0)) for i in items)
        xp += WIN_XP + TAI_XP * tai
        _stat(p, "wins")
        _bump(p, "wins", 1, events)
        _unlock(p, "first_win", events)
        if result.get("self_draw"):
            xp += TSUMO_XP
            _stat(p, "self_draws")
            _bump(p, "self_draw", 1, events)
            _unlock(p, "first_tsumo", events)
        if tai >= 5:
            _bump(p, "big_win", 1, events)
        if tai >= 10:
            _unlock(p, "ten_tai", events)
        for item in items:
            if item.get("id") in TAI_ACHIEVEMENTS:
                _unlock(p, TAI_ACHIEVEMENTS[item["id"]], events)
    if hands >= 100:
        _unlock(p, "hundred_hands", events)
    _add_xp(p, xp, events)
    events.insert(0, {"type": "XP", "xp": xp})
    return events


def record_match(db: Session, user: User, rank: int, now: datetime | None = None
                 ) -> list[dict[str, Any]]:
    """Progress for a finished game (rank 1-4)."""
    p = get_progress(db, user)
    ensure_today(p, now)
    events: list[dict[str, Any]] = []
    coins = MATCH_COINS.get(rank, 0)
    p.coins += coins
    matches = _stat(p, "matches")
    _bump(p, "match", 1, events)
    if rank == 1:
        _bump(p, "first", 1, events)
    if matches >= 10:
        _unlock(p, "ten_matches", events)
    xp = MATCH_XP.get(rank, 0)
    _add_xp(p, xp, events)
    events.insert(0, {"type": "MATCH_REWARD", "rank": rank, "coins": coins, "xp": xp})
    return events


# ------------------------------------------------------------------ views


def profile(db: Session, user: User, now: datetime | None = None) -> dict[str, Any]:
    p = get_progress(db, user)
    ensure_today(p, now)
    return {
        "level": p.level, "xp": p.xp, "xp_next": xp_for_next(p.level), "coins": p.coins,
        "rank": rank_for(user.elo_human), "bonus": bonus_status(p, now),
        "missions": [{**m, "name": MISSIONS[m["id"]].name, "target": MISSIONS[m["id"]].target,
                      "reward": MISSIONS[m["id"]].reward} for m in p.missions],
        "achievements": [{"id": a.id, "name": a.name, "description": a.description,
                          "reward": a.reward, "unlocked": a.id in p.achievements}
                         for a in ACHIEVEMENTS],
        "equipped": p.equipped, "owned": p.owned, "stats": p.stats,
    }


def shop(p: UserProgress) -> dict[str, list[dict[str, Any]]]:
    return {slot: [{**item, "owned": f"{slot}:{item['id']}" in p.owned,
                    "equipped": p.equipped.get(slot) == item["id"]} for item in items]
            for slot, items in SHOP.items()}
