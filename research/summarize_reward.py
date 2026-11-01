"""Render local research tables, keeping absent results explicitly incomplete."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / 'runs/research-20261101/reward-ablation-eval-01'
TRAIN = ROOT / 'runs/research-20261101/reward-ablation-01'
lines = ['# Reward 消融即時結果（僅存本機）', '',
         '> legacy-info-v1：規則代理當時讀取對手暗槓牌種；以下不能作公平棋力證據。', '',
         '比較對象是初始 ppo_v7。區間以獨立洗牌 block bootstrap 計算。',
         '此表是探索性比較，不作多重比較後的正式優勝宣告。', '',
         '| Reward | 訓練 seed | 對手池 | Blocks | 淨分差／手 | 95% CI |',
         '| --- | --- | --- | ---: | ---: | --- |']
completed = 0
trained = 0
for seed in [20261102, 20261103, 20261104]:
    for reward in ['potential', 'score', 'discounted']:
        name = f'research-reward01-{reward}-{seed}'
        trained += (TRAIN / (name + '-result.json')).exists()
        for pool in [0, 1]:
            path = EVAL / f'{name}-pool{pool}-summary.json'
            if path.exists():
                result = json.loads(path.read_text())
                lo, hi = result['bootstrap_ci95']
                lines.append(f'| {reward} | {seed} | {pool} | {result["blocks"]} | '
                             f'{result["mean_difference"]:+.2f} | [{lo:+.2f}, {hi:+.2f}] |')
                completed += 1
            else:
                lines.append(f'| {reward} | {seed} | {pool} | — | 尚未完成 | — |')
lines += ['', f'完成訓練 {trained}/9，完成評估 {completed}/18。',
          'Pool 0 是 rule，Pool 1 是 CEM；兩池分別報告，未混合平均。',
          '未完成三個 training seeds 前不計算跨訓練seed聚合結論。']
(ROOT / 'research/RESULTS.md').write_text('\n'.join(lines) + '\n')
print(f'Trained {trained}/9; evaluated {completed}/18; local RESULTS.md updated')
