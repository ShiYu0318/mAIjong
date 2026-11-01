"""Explicit device placement for new offline experiments; never alters active runs."""
import torch


def move_learner(learner, device: str):
    destination = torch.device(device)
    if destination.type == 'mps' and not torch.backends.mps.is_available():
        raise ValueError('MPS is unavailable')
    destination = torch.empty(0, device=destination).device
    optimizers = [learner.actor_opt, learner.q_opt, learner.v_opt]
    if any(optimizer.state for optimizer in optimizers):
        raise ValueError('Place the learner before its first optimizer step')
    for key in ['actor', 'reference', 'q1', 'q2', 'value', 'q1_target', 'q2_target']:
        getattr(learner, key).to(destination)
    for optimizer in optimizers:
        parameters = [p for group in optimizer.param_groups for p in group['params']]
        if any(p.device != destination for p in parameters):
            raise ValueError('Optimizer parameter identity changed during device placement')
    return learner
