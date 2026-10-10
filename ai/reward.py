"""Tai-oriented reward shaping (SPEC 05.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_REWARD_CONFIG: dict[str, float] = {
    "shanten_improve": 0.05,  # per step of shanten reduction
    "uke_ire_improve": 0.005,  # per additional effective tile
    "flower_supplement": 0.02,  # drawing one of one's own seat flowers
    "win_tai_coeff": 0.5,  # × final tai
    "deal_in_penalty": -1.0,  # × tai paid when dealing in
    "tenpai_bonus": 0.1,  # reaching tenpai
    "exhausted_wall": -0.05,  # hand ends without a winner
    "discount_gamma": 0.99,
    "illegal_penalty": -0.1,  # unmasked illegal action (replaced by a legal one)
}


@dataclass
class StepData:
    seat: int
    shanten_before: int
    shanten_after: int
    uke_ire_before: int
    uke_ire_after: int
    own_flowers_gained: int = 0
    is_final: bool = False


@dataclass
class GameResult:
    winner: int | None
    tai: int  # winner's tai against the agent's seat (or overall)
    deal_in: int | None  # seat that dealt in
    deal_in_tai: int
    is_draw: bool

    @staticmethod
    def from_result(result: dict[str, Any], seat: int) -> GameResult:
        if result["kind"] == "DRAW":
            return GameResult(None, 0, None, 0, True)
        winner = result["winner"]
        by_payer = {int(k): v for k, v in result.get("tai_by_payer", {}).items()}
        tai = max(by_payer.values(), default=0)
        loser = result.get("loser") if not result.get("self_draw") else None
        deal_in_tai = by_payer.get(seat, 0) if loser == seat else 0
        return GameResult(winner, tai, loser, deal_in_tai, False)


def compute_shaped_reward(
    step: StepData,
    trajectory: list[StepData],
    final_result: GameResult | None,
    config: dict[str, float] | None = None,
) -> float:
    config = config or DEFAULT_REWARD_CONFIG
    r = 0.0
    delta_sh = step.shanten_before - step.shanten_after
    if delta_sh > 0:
        r += config["shanten_improve"] * delta_sh
    delta_uke = step.uke_ire_after - step.uke_ire_before
    if delta_uke > 0:
        r += config["uke_ire_improve"] * delta_uke
    if step.shanten_before >= 1 and step.shanten_after == 0:
        r += config["tenpai_bonus"]
    r += config["flower_supplement"] * step.own_flowers_gained

    # terminal rewards are given once, on the seat's final step
    if not step.is_final or final_result is None:
        return r
    if final_result.winner == step.seat:
        r += config["win_tai_coeff"] * final_result.tai
    if final_result.deal_in == step.seat:
        r += config["deal_in_penalty"] * final_result.deal_in_tai
    if final_result.is_draw:
        r += config["exhausted_wall"]
    return r
