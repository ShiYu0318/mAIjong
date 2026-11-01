"""Render completed IQL comparisons and policy diagnostics without pooling missing runs."""
import hashlib
import json
from pathlib import Path

import numpy as np

from research.reward_analysis import crossed_interval

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / 'runs/research-20261101/iql-ablation-01'
EVAL = ROOT / 'runs/research-20261101/iql-ablation-eval-01'


def verified_rows(stem, plan, pool):
    summary = json.loads((EVAL / (stem + '-summary.json')).read_text())
    rows = [json.loads(x) for x in (EVAL / (stem + '.jsonl')).read_text().splitlines()]
    if len(rows) != plan['blocks'] or summary['blocks'] != len(rows):
        raise ValueError('Incomplete evaluation')
    for k, row in enumerate(rows):
        if row['seed'] != plan['deal_seed_start'] + pool * 100000 + k:
            raise ValueError('Shared deal seed mismatch')
        if row['checkpoint_hashes'] != summary['checkpoint_hashes']:
            raise ValueError('Checkpoint hash mismatch')
        if row['mean_difference'] != np.mean([a['score'] - b['score'] for a, b in row['pairs']]):
            raise ValueError('Payment difference mismatch')
    return summary, np.asarray([r['mean_difference'] for r in rows])


def main():
    plan = json.loads((EVAL / 'manifest.json').read_text())
    training = json.loads((TRAIN / 'manifest.json').read_text())
    trained = sum((TRAIN / f'research-iql01-{mode}-{seed}-result.json').exists()
                  for seed in training['seeds'] for mode in training['modes'])
    lines = ['# IQL／BC 即時結果（僅存本機）', '',
             '> legacy-info-v1：規則代理當時讀取對手暗槓牌種；以下不能作公平棋力證據。', '',
             f'完成訓練 {trained}/9。固定最後600步actor模型，不依以下分數選checkpoint。',
             '每比較、每池128個洗牌block；每block雙代理各四席，支付差單位為點／手。',
             'IQL對同訓練seed的BC，BC另對initial。未完成資料不填0、不聚合缺失seed。', '',
             '| 訓練seed | 比較 | 池 | 淨分差／手 | 95% block bootstrap CI |',
             '| --- | --- | --- | ---: | --- |']
    complete, summaries, matrices = 0, [], {}
    for seed in plan['seeds']:
        for comparison in plan['comparisons']:
            for pool in range(len(plan['pools'])):
                stem = f'{comparison}-{seed}-pool{pool}'
                if not (EVAL / (stem + '-summary.json')).exists():
                    lines.append(f'| {seed} | {comparison} | {pool} | 尚未完成 | — |')
                    continue
                result, values = verified_rows(stem, plan, pool)
                low, high = result['bootstrap_ci95']
                lines.append(f'| {seed} | {comparison} | {pool} | '
                             f'{result["mean_difference"]:+.2f} | [{low:+.2f}, {high:+.2f}] |')
                matrices.setdefault((comparison, pool), {})[seed] = values
                complete += 1
    lines += ['', f'完成評估 {complete}/18。Pool0=rule；Pool1的其他三席對手為CEM。',
              '', '## 三訓練seed聚合', '']
    for comparison in plan['comparisons']:
        for pool in range(len(plan['pools'])):
            rows = matrices.get((comparison, pool), {})
            if set(rows) != set(plan['seeds']):
                lines.append(f'- {comparison}／Pool{pool}：三seed尚未完整，不聚合。')
                continue
            matrix = np.stack([rows[s] for s in plan['seeds']])
            low, high = crossed_interval(matrix)
            summary = {'comparison': comparison, 'pool': pool, 'mean': float(matrix.mean()),
                       'ci95': [low, high], 'training_seed_means': matrix.mean(1).tolist()}
            summaries.append(summary)
            lines.append(f'- {comparison}／Pool{pool}：{matrix.mean():+.2f} '
                         f'[{low:+.2f}, {high:+.2f}]，crossed seed/deal bootstrap。')
    lines += ['', '## Validation 非強制決策診斷', '',
              '此fold可能已被initial actor看過；NLL與TD誤差不能當成獨立棋力。',
              '以下只列合法分支數>1的決策，避免forced actions膨脹策略一致率。', '',
              '| 模型 | 子群 | 筆數 | 與BC貪婪動作一致 | KL(BC‖IQL) | 權重ESS比例 |',
              '| --- | --- | ---: | ---: | ---: | ---: |']
    for path in sorted(TRAIN.glob('*-diagnostics.json')):
        result = json.loads(path.read_text())
        for group in ['choice', 'discard_choice', 'response_choice', 'threatened_choice']:
            stats = result['folds']['validation'][group]
            if stats['count']:
                lines.append(f'| {result["model"]} | {group} | {stats["count"]} | '
                             f'{stats["greedy_agreement_bc"]:.2%} | '
                             f'{stats["kl_from_bc"]:.6f} | {stats["weight_ess_fraction"]:.4f} |')
    lines += ['', '只有三個訓練seed，所有比較屬探索性，未做多重比較校正。',
              'AWR權重接近1與極小KL可解釋為接近BC；仍需對局證據驗證是否改善。']
    (ROOT / 'research/IQL_RESULTS.md').write_text('\n'.join(lines) + '\n')
    (EVAL / 'crossed-analysis.json').write_text(json.dumps(
        {'completed_comparisons': complete, 'summaries': summaries,
         'inputs': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in EVAL.glob('*-summary.json')}}, indent=2))
    print(f'Trained {trained}/9, evaluated {complete}/18; local IQL_RESULTS.md updated')


if __name__ == '__main__':
    main()
