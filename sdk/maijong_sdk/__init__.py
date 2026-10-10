"""mAIjong community SDK: build, train and submit Taiwanese 16-tile mahjong agents."""

from maijong_sdk.base_agent import BaseAgent
from maijong_sdk.types import Action, ActionType, GameInfo, Observation, observe

__version__ = "1.0.0"
__all__ = ["Action", "ActionType", "BaseAgent", "GameInfo", "Observation", "observe"]
