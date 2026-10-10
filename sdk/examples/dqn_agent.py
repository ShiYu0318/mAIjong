"""Agent that plays with a model trained by dqn_example.py (model.pt next to this file)."""

from pathlib import Path

import torch
from dqn_example import QNet
from maijong_sdk import Action, BaseAgent, Observation
from maijong_sdk.features import encode, legal_mask
from maijong_sdk.types import decode_action


class DQNAgent(BaseAgent):
    def __init__(self) -> None:
        self.q = QNet()
        path = Path(__file__).with_name("model.pt")
        if path.exists():
            self.q.load_state_dict(torch.load(path, map_location="cpu"))
        self.q.eval()

    @torch.no_grad()
    def decide(self, obs: Observation, legal_actions: list[Action]) -> Action:
        tiles, scalars = encode(obs)
        qs = self.q(torch.from_numpy(tiles)[None], torch.from_numpy(scalars)[None])[0]
        mask = torch.from_numpy(legal_mask(legal_actions))
        return decode_action(int(qs.masked_fill(~mask, -1e9).argmax()))
