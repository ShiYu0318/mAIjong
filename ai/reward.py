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
    # extensions (off in the SPEC 05.4 defaults):
    "potential_shaping": 0.0,  # 1 = symmetric, potential-based shaping (see below)
    "score_coeff": 0.0,  # × points won or paid at the end of the hand
}

# SPEC 05.4 shaping only rewards improvements, so breaking a hand apart costs nothing and
# rebuilding it pays again: a policy can farm shaping reward instead of winning. The
# "potential" preset makes shaping a potential difference Φ(s') − Φ(s) (penalising
# regressions, Φ = 0 at the end; legacy behavior without a discount correction) and replaces
# the tai terms with the actual points, which also counts paying for others' self-draws.
REWARD_PRESETS: dict[str, dict[str, float]] = {
    "spec": DEFAULT_REWARD_CONFIG,
    "potential": {**DEFAULT_REWARD_CONFIG, "potential_shaping": 1.0, "score_coeff": 0.005,
                  "win_tai_coeff": 0.0, "deal_in_penalty": 0.0},
}


# Pure payment objective and its discount-correct potential-based counterpart.
# Keep legacy presets unchanged so historical experiments remain reproducible.
REWARD_PRESETS["score"] = {
    **DEFAULT_REWARD_CONFIG,
    "shanten_improve": 0.0, "uke_ire_improve": 0.0, "tenpai_bonus": 0.0,
    "flower_supplement": 0.0, "win_tai_coeff": 0.0, "deal_in_penalty": 0.0,
    "exhausted_wall": 0.0, "score_coeff": 0.005,
}
REWARD_PRESETS["discounted"] = {
    **REWARD_PRESETS["score"],
    "potential_shaping": 1.0, "discounted_potential": 1.0,
    "shanten_improve": 0.05, "uke_ire_improve": 0.005, "tenpai_bonus": 0.1,
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
    payment: int = 0  # points this seat won (+) or paid (−) for the hand

    @staticmethod
    def from_result(result: dict[str, Any], seat: int) -> GameResult:
        payment = int((result.get("payments") or [0, 0, 0, 0])[seat])
        if result["kind"] == "DRAW":
            return GameResult(None, 0, None, 0, True, payment)
        winner = result["winner"]
        by_payer = {int(k): v for k, v in result.get("tai_by_payer", {}).items()}
        tai = max(by_payer.values(), default=0)
        loser = result.get("loser") if not result.get("self_draw") else None
        deal_in_tai = by_payer.get(seat, 0) if loser == seat else 0
        return GameResult(winner, tai, loser, deal_in_tai, False, payment)


def compute_shaped_reward(
    step: StepData,
    trajectory: list[StepData],
    final_result: GameResult | None,
    config: dict[str, float] | None = None,
) -> float:
    config = config or DEFAULT_REWARD_CONFIG
    if config.get("potential_shaping"):
        return _potential_reward(step, final_result, config)
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
    r += config.get("score_coeff", 0.0) * final_result.payment
    if final_result.winner == step.seat:
        r += config["win_tai_coeff"] * final_result.tai
    if final_result.deal_in == step.seat:
        r += config["deal_in_penalty"] * final_result.deal_in_tai
    if final_result.is_draw:
        r += config["exhausted_wall"]
    return r


def _potential(shanten: int, uke_ire: int, config: dict[str, float]) -> float:
    return (-config["shanten_improve"] * shanten + config["uke_ire_improve"] * uke_ire
            + config["tenpai_bonus"] * (shanten == 0))


def _potential_reward(step: StepData, final_result: GameResult | None,
                      config: dict[str, float]) -> float:
    before = _potential(step.shanten_before, step.uke_ire_before, config)
    after = 0.0 if step.is_final else _potential(step.shanten_after, step.uke_ire_after,
                                                 config)
    gamma = config["discount_gamma"] if config.get("discounted_potential") else 1.0
    r = gamma * after - before + config["flower_supplement"] * step.own_flowers_gained
    if step.is_final and final_result is not None:
        r += config.get("score_coeff", 0.0) * final_result.payment
        if final_result.winner == step.seat:
            r += config["win_tai_coeff"] * final_result.tai
        if final_result.deal_in == step.seat:
            r += config["deal_in_penalty"] * final_result.deal_in_tai
        if final_result.is_draw:
            r += config["exhausted_wall"]
    return r
