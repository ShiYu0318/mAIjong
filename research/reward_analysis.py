"""Crossed seed/deal bootstrap for the local reward experiment."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / 'runs/research-20261101/reward-ablation-eval-01'
TRAIN = ROOT / 'runs/research-20261101/reward-ablation-01'


def crossed_interval(values: np.ndarray, seed: int = 823, resamples: int = 10000
                     ) -> tuple[float, float]:
    """Independently sample training seeds and shared deals, preserving their crossing.

    Deal indices are shared by all sampled training seeds within each replicate.
    This does not treat the same wall evaluated by three models as three new walls.
    With only three training seeds, coverage of unseen training runs is uncertain.
    """
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or min(values.shape) < 1 or not np.isfinite(values).all():
        raise ValueError('Expected a finite, nonempty seed-by-deal matrix')
    if resamples < 1:
        raise ValueError('resamples must be positive')
    seed_rng, deal_rng = [np.random.default_rng(s)
                          for s in np.random.SeedSequence(seed).spawn(2)]
    rows = seed_rng.integers(values.shape[0], size=(resamples, values.shape[0]))
    cols = deal_rng.integers(values.shape[1], size=(resamples, values.shape[1]))
    samples = values[rows[:, :, None], cols[:, None, :]].mean(axis=(1, 2))
    low, high = np.quantile(samples, [0.025, 0.975])
    return float(low), float(high)


def load_matrix(directory: Path, reward: str, pool: int) -> np.ndarray:
    plan = json.loads((directory / 'manifest.json').read_text())
    result = []
    for seed in plan['seeds']:
        name = f'research-reward01-{reward}-{seed}'
        rows = [json.loads(line) for line in
                (directory / f'{name}-pool{pool}.jsonl').read_text().splitlines()]
        summary = json.loads((directory / f'{name}-pool{pool}-summary.json').read_text())
        if len(rows) != plan['blocks'] or summary['blocks'] != plan['blocks']:
            raise ValueError('Incomplete evaluation; do not pool incomplete seeds')
        for i, row in enumerate(rows):
            expected_seed = plan['deal_seed_start'] + pool * 100000 + i
            if row['seed'] != expected_seed:
                raise ValueError('Shared deal seeds do not align')
            if row['checkpoint_sha256'] != summary['checkpoint_sha256']:
                raise ValueError('Checkpoint changed within evaluation')
            difference = np.mean([a['score'] - b['score'] for a, b in row['pairs']])
            if difference != row['mean_difference']:
                raise ValueError('Stored mean does not match per-seat payments')
        result.append([row['mean_difference'] for row in rows])
    return np.asarray(result, dtype=float)


def main():
    plan = json.loads((EVAL / 'manifest.json').read_text())
    lines = ['# Reward 跨訓練種子分析（僅存本機）', '',
             '> legacy-info-v1：規則代理當時讀取對手暗槓牌種；以下不能作公平棋力證據。', '',
             '三個 training seeds 與每池128個共享洗牌block。淨分差皆為每手點數。',
             '95%區間分別重採樣訓練seed與牌局；同一牌局在各seed間保持配對。',
             '只有三個訓練seed，區間屬探索性估計；未做多重比較校正。', '',
             '| 對手池 | 比較 | 平均差／手 | Crossed bootstrap 95% CI | 各訓練seed均值 |',
             '| --- | --- | ---: | --- | --- |']
    summaries = []
    for pool, opponent in enumerate(plan['pools']):
        matrices = {r: load_matrix(EVAL, r, pool) for r in plan['rewards']}
        comparisons = [(r + ' − initial', data) for r, data in matrices.items()]
        comparisons += [('score − potential', matrices['score'] - matrices['potential']),
                        ('discounted − score', matrices['discounted'] - matrices['score']),
                        ('discounted − potential',
                         matrices['discounted'] - matrices['potential'])]
        for label, data in comparisons:
            low, high = crossed_interval(data)
            per_seed = data.mean(axis=1).tolist()
            summaries.append({'opponent': opponent, 'comparison': label,
                              'mean': float(data.mean()), 'ci95': [low, high],
                              'training_seed_means': per_seed})
            lines.append(f'| {opponent} | {label} | {data.mean():+.2f} | '
                         f'[{low:+.2f}, {high:+.2f}] | '
                         + ', '.join(f'{x:+.2f}' for x in per_seed) + ' |')
    lines += ['', 'reward間差異在相同訓練seed、相同洗牌block上相減後重採樣。',
              '各reward與initial比較並未證明超越CEM本人；CEM在這裡是另外三席的對手池。',
              '若參考本分析選新方案，下一輪正式確認必須使用新的獨立牌局。']
    (ROOT / 'research/REWARD_ANALYSIS.md').write_text('\n'.join(lines) + '\n')
    inputs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in EVAL.glob('*.jsonl')}
    (EVAL / 'crossed-analysis.json').write_text(json.dumps(
        {'summaries': summaries, 'input_sha256': inputs,
         'resamples': 10000, 'seed': 823}, indent=2))
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
