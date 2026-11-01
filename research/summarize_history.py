"""python -m research.summarize_history: audit and aggregate the completed history run."""
import hashlib
import json
from pathlib import Path

import numpy as np

from research.reward_analysis import crossed_interval

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/research-20261101/history-ablation-01'


def main():
    plan = json.loads((OUT / 'manifest.json').read_text())
    seeds = sorted({cfg['seed'] for cfg in plan['configs'].values()})
    summary = []
    lines = ['# 公開歷史 PPO 配對結果（僅存本機）', '',
             '> legacy-info-v1：規則代理當時讀取對手暗槓牌種；以下不能作公平棋力證據。', '',
             '兩組均使用score、gamma=1、相同互動步數。比較有歷史減無歷史的淨支付差。',
             'Crossed bootstrap同時重採樣訓練seed與共享洗牌block；三seed僅能作探索性估計。', '',
             '| 對手池 | 淨分差／手 | 95% CI | 各訓練seed均值 |',
             '| --- | ---: | --- | --- |']
    input_hashes = {}
    for pool, opponent in enumerate(plan['evaluation']['pools']):
        matrix = []
        for seed in seeds:
            path = OUT / f'paired-{seed}-pool{pool}.jsonl'
            input_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            rows = [json.loads(x) for x in path.read_text().splitlines()]
            if len(rows) != plan['evaluation']['blocks']:
                raise ValueError('Incomplete history evaluation')
            hashes = [json.loads((OUT / f'research-history01-{h}-{seed}-result.json')
                                 .read_text())['checkpoint_sha256'] for h in [0, 1]]
            for k, row in enumerate(rows):
                if row['seed'] != plan['evaluation']['seed_start'] + pool * 100000 + k:
                    raise ValueError('Paired seed mismatch')
                if row['checkpoint_hashes'] != hashes:
                    raise ValueError('Checkpoint mismatch')
                if row['mean_difference'] != np.mean(
                        [a['score'] - b['score'] for a, b in row['pairs']]):
                    raise ValueError('Payment mean mismatch')
            matrix.append([row['mean_difference'] for row in rows])
        matrix = np.asarray(matrix)
        low, high = crossed_interval(matrix)
        result = {'opponent': opponent, 'mean': float(matrix.mean()), 'ci95': [low, high],
                  'training_seed_means': matrix.mean(1).tolist()}
        summary.append(result)
        lines.append(f'| {opponent} | {result["mean"]:+.2f} | [{low:+.2f}, {high:+.2f}] | '
                     + ', '.join(f'{x:+.2f}' for x in result['training_seed_means']) + ' |')
    lines += ['', '兩個對手池分開報告，未依結果挑選seed；本輪未證明棋力提升。',
              '此為每次決策重編碼最近128個事件的GRU，不是整場持續記憶。',
              '歷史分支增加算力且改變訓練亂數消耗；選模仍是64手胡牌率優先。',
              '不能由短預算無顯著差異推論公開歷史永遠沒有價值。']
    (ROOT / 'research/HISTORY_RESULTS.md').write_text('\n'.join(lines) + '\n')
    (OUT / 'crossed-analysis.json').write_text(json.dumps(
        {'summaries': summary, 'inputs': input_hashes, 'resamples': 10000, 'seed': 823}, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
