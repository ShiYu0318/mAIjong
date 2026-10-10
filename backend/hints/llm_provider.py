"""Natural-language explanations for hints and coaching (SPEC P5-4, OQ-08).

TemplateProvider is the default and needs no network. Set HINT_LLM_PROVIDER=openai and
HINT_LLM_API_KEY to use an OpenAI-compatible chat completion endpoint (optionally
HINT_LLM_BASE_URL / HINT_LLM_MODEL); any failure falls back to the template.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol

import httpx

from backend.config import get_settings
from engine import tiles

log = logging.getLogger("maijong.hints")


def shanten_text(sh: int) -> str:
    if sh < 0:
        return "胡牌"
    if sh == 0:
        return "聽牌"
    return f"{sh} 向聽"


def tile_list(ids: list[int], limit: int = 8) -> str:
    names = [tiles.name(t) for t in ids[:limit]]
    more = "等" if len(ids) > limit else ""
    return "、".join(names) + more


def template_explain(cands: list[dict[str, Any]], chosen: int | None = None) -> str:
    """Plain-language summary of the best discard (and the chosen one if different)."""
    if not cands:
        return ""
    best = cands[0]
    parts = [f"建議打 {best['name']}：打出後{shanten_text(best['shanten_after'])}"]
    if best["shanten_after"] == 0:
        parts.append(f"聽 {tile_list(best['waits'])}，還有 {best['uke_count']} 張可胡")
        if best.get("best_tai") is not None:
            parts.append(f"胡牌最多約 {best['best_tai']} 台（不含莊家台）")
    else:
        parts.append(f"有效進張 {len(best['uke_ire'])} 種、{best['uke_count']} 張"
                     f"（{tile_list(best['uke_ire'])}）")
    if best.get("danger", 0) >= 0.5:
        parts.append("不過這張牌有放槍風險")
    text = "，".join(parts) + "。"
    if chosen is not None and chosen != best["tile"]:
        mine = next((c for c in cands if c["tile"] == chosen), None)
        if mine is not None:
            if mine["shanten_after"] > best["shanten_after"]:
                text += (f"你打的 {mine['name']} 會讓手牌退到"
                         f"{shanten_text(mine['shanten_after'])}。")
            elif mine["uke_count"] < best["uke_count"]:
                text += (f"你打的 {mine['name']} 同樣是{shanten_text(mine['shanten_after'])}，"
                         f"但進張只剩 {mine['uke_count']} 張。")
            elif mine["danger"] > best["danger"] + 0.2:
                text += f"你打的 {mine['name']} 進張相同，但比較危險。"
            else:
                text += f"你打的 {mine['name']} 也很接近最佳選擇。"
    return text


class HintLLMProvider(Protocol):
    async def explain(self, cands: list[dict[str, Any]], chosen: int | None = None) -> str: ...


class TemplateProvider:
    async def explain(self, cands: list[dict[str, Any]], chosen: int | None = None) -> str:
        return template_explain(cands, chosen)


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def explain(self, cands: list[dict[str, Any]], chosen: int | None = None) -> str:
        fallback = template_explain(cands, chosen)
        top = [{k: c[k] for k in ("name", "shanten_after", "uke_count", "danger")}
               for c in cands[:5]]
        prompt = (
            "你是台灣十六張麻將（神來也規則）的教練。根據以下候選棄牌分析，用兩三句繁體中文"
            "向新手解釋最佳打法與理由，不要提到你是 AI。\n"
            f"分析：{fallback}\n"
            f"候選（前五名）：{top}"
        )
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 200},
                )
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"].strip()
                return text or fallback
        except Exception:
            log.warning("LLM hint failed; using template", exc_info=True)
            return fallback


def get_provider() -> HintLLMProvider:
    st = get_settings()
    if st.hint_llm_provider == "openai" and st.hint_llm_api_key:
        return OpenAICompatibleProvider(
            st.hint_llm_api_key,
            os.environ.get("HINT_LLM_BASE_URL", "https://api.openai.com/v1"),
            os.environ.get("HINT_LLM_MODEL", "gpt-4o"),
        )
    return TemplateProvider()
