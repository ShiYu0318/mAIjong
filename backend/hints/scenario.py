"""Judging the key move of a practice scenario (SPEC 04.6): the player's first decision.

Discard drills use the same ranking as hints and the decision quiz (shanten, useful tiles,
danger); call drills compare with what the Lv5 agent would do in the same spot."""

from __future__ import annotations

from typing import Any

from ai.agents import LEVEL5_PARAMS
from ai.agents.rule_agent import RuleAgent
from ai.explainability.candidate_scorer import score_all_discards
from backend.hints.llm_provider import template_explain
from engine.actions import Action, ActionType
from engine.game import GameState, get_legal_actions
from engine.tiles import name as tile_name

_CALL_WORDS = {
    ActionType.PON: "碰", ActionType.KONG: "槓", ActionType.HU: "胡", ActionType.PASS: "過",
    ActionType.CHI_LOW: "吃", ActionType.CHI_MID: "吃", ActionType.CHI_HIGH: "吃",
    ActionType.DISCARD: "打出", ActionType.TING: "打出並宣告聽牌",
}


def _word(a: Action) -> str:
    word = _CALL_WORDS.get(a.type, a.type.value)
    return f"{word} {tile_name(a.tile)}" if a.tile is not None else word


def judge(state: GameState, seat: int, action: Action) -> dict[str, Any]:
    """SCENARIO_RESULT payload for `action`, taken from `state` (before it is applied)."""
    if action.type in (ActionType.DISCARD, ActionType.TING) and action.tile is not None:
        cands = [c.to_dict() for c in score_all_discards(state, seat)]
        rank = next((i for i, c in enumerate(cands) if c["tile"] == action.tile), len(cands) - 1)
        best, mine = cands[0], cands[rank]
        good = mine["shanten_after"] == best["shanten_after"] and \
            mine["uke_count"] >= 0.9 * best["uke_count"]
        return {"kind": "discard", "verdict": "best" if rank == 0 else "good" if good else "worse",
                "rank": rank + 1, "best": best, "chosen": mine, "candidates": cands[:6],
                "explanation": template_explain(cands, action.tile)}
    legal = get_legal_actions(state, seat)
    expert = RuleAgent(0.0, 0, params=LEVEL5_PARAMS).act(state, seat, legal)
    same = expert.type == action.type and expert.tile == action.tile
    text = (f"和 AI 高手的選擇一樣：{_word(expert)}。" if same
            else f"AI 高手在這裡會選擇「{_word(expert)}」，你選了「{_word(action)}」。")
    return {"kind": "call", "verdict": "best" if same else "worse",
            "best": expert.to_dict(), "chosen": action.to_dict(), "explanation": text}
