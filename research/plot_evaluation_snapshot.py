# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib>=3.9", "numpy>=1.26"]
# ///
"""Static forest plots of completed exploratory comparisons; all artifacts stay local."""
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'runs/research-20261101'
OUT = BASE / 'figures/evaluation-legacy-info-v1'


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    inputs = {}

    def read(path):
        inputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        return json.loads(path.read_text())

    reward = read(BASE / 'reward-ablation-eval-01/crossed-analysis.json')['summaries']
    history = read(BASE / 'history-ablation-01/crossed-analysis.json')['summaries']
    reward_points = []
    for row in reward:
        if row['comparison'].endswith('initial'):
            pool = 'Rule' if row['opponent'] == 'rule' else 'CEM'
            label = row['comparison'].split(' ')[0].capitalize() + ' / ' + pool
            reward_points.append((label, row['mean'], row['ci95'], pool))
    history_points = [(('Rule' if row['opponent'] == 'rule' else 'CEM'), row['mean'], row['ci95'],
                       'Rule' if row['opponent'] == 'rule' else 'CEM') for row in history]
    iql_points = []
    for mode in ['iql05', 'iql07']:
        for pool in [0, 1]:
            row = read(BASE / 'iql-ablation-eval-01' /
                       f'{mode}-bc-20261108-pool{pool}-summary.json')
            name = ('tau=0.5' if mode == 'iql05' else 'tau=0.7')
            name += ' / Rule' if pool == 0 else ' / CEM'
            iql_points.append((name, row['mean_difference'], row['bootstrap_ci95'],
                               'Rule' if pool == 0 else 'CEM'))
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.titlesize': 12, 'axes.labelsize': 10})
    figure, axes = plt.subplots(1, 3, figsize=(15, 6.8))
    colors = {'Rule': '#286487', 'CEM': '#b36927'}
    panels = [('Reward ablation | 3 training seeds\nBaseline: initial PPO', reward_points),
              ('Public-history PPO | 3 training seeds\nBaseline: no-history PPO', history_points),
              ('IQL | first training seed only\nBaseline: matched BC', iql_points)]
    for axis, (title, points) in zip(axes, panels, strict=True):
        y = np.arange(len(points))[::-1]
        for position, (_, mean, (low, high), pool) in zip(y, points, strict=True):
            axis.errorbar(mean, position, xerr=[[mean - low], [high - mean]], fmt='o',
                          color=colors[pool], capsize=4, markersize=6, linewidth=1.6)
        axis.set_yticks(y, [point[0] for point in points])
        axis.axvline(0, color='#69737b', linestyle='--', linewidth=1)
        axis.set_title(title, loc='left', pad=18, fontweight='bold')
        axis.set_xlabel('Mean net-payment difference / hand')
        axis.set_ylim(-0.7, len(points) - 0.3)
        axis.grid(axis='x', color='#e4e9ec', linewidth=0.8)
        axis.set_axisbelow(True)
        for spine in ['top', 'right', 'left']:
            axis.spines[spine].set_visible(False)
        axis.spines['bottom'].set_color('#cad0d5')
        axis.tick_params(axis='y', length=0, pad=8)
    figure.suptitle('Legacy benchmark | Not valid for fair-information strength claims',
                    fontsize=18, fontweight='bold', x=0.06, ha='left', y=0.97)
    figure.text(0.06, 0.89,
                'Pre-fix rule agents used concealed opponent-kong identities. '
                'These results are retained only as research history.',
                color='#9d4628', fontsize=11)
    figure.text(0.06, 0.065,
                '95% bootstrap intervals. Reward/history resample training seeds and shared deals; '
                'IQL uses deal blocks only.\n'
                'Panels have different baselines and x-axis scales. '
                'Local pools only; no SOTA claim.',
                color='#59656e', fontsize=10, va='bottom')
    figure.subplots_adjust(left=0.12, right=0.98, top=0.80, bottom=0.23, wspace=0.85)
    figure.savefig(OUT / 'evaluation.png', dpi=180, facecolor='white')
    figure.savefig(OUT / 'evaluation.svg', facecolor='white')
    plt.close(figure)
    (OUT / 'manifest.json').write_text(json.dumps(
        {'matplotlib': matplotlib.__version__, 'numpy': np.__version__, 'inputs': inputs,
         'information_contract': 'legacy-info-v1', 'fair_strength_claims_valid': False,
         'note': 'Completed reward/history and preregistered first IQL training seed only'},
        indent=2))
    print(str(OUT / 'evaluation.png'))


if __name__ == '__main__':
    main()
