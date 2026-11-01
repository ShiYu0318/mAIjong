"""Audit archived counterfactual labels before reuse; no independent-hand claim without IDs."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/research-20261101/rollout-asset-audit-01.json'


def main():
    seen_context, seen_labels = set(), set()
    per_file_contexts = {}
    results = []
    for path in sorted((ROOT / 'data/rollq').glob('*.npz')):
        with np.load(path, allow_pickle=False) as archive:
            x, s = archive['tiles'].astype(np.float32), archive['scalars'].astype(np.float32)
            q, chosen = archive['q'].astype(np.float32), archive['chosen'].astype(np.int64)
            fields = archive.files
        if not np.isfinite(x).all() or not np.isfinite(s).all() or np.isinf(q).any():
            raise ValueError('Nonfinite features or infinite Q labels')
        mask = ~np.isnan(q)
        if not (mask.sum(1) >= 2).all() or len(x) != len(q):
            raise ValueError('Malformed counterfactual records')
        qz = np.nan_to_num(q)
        span = np.nanmax(q, axis=1) - np.nanmin(q, axis=1)
        contexts, labels = set(), set()
        for i in range(len(q)):
            context = hashlib.sha256(x[i].tobytes() + s[i].tobytes()).digest()
            label = hashlib.sha256(context + chosen[i].tobytes() + np.packbits(mask[i]).tobytes()
                                   + qz[i].tobytes()).digest()
            contexts.add(context)
            labels.add(label)
        valid_chosen = (chosen >= 0) & (chosen < 34)
        chosen_in_candidates = np.zeros(len(q), dtype=bool)
        rows = np.flatnonzero(valid_chosen)
        chosen_in_candidates[valid_chosen] = mask[rows, chosen[valid_chosen]]
        row = {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'fields': fields, 'rows': len(q), 'unique_contexts': len(contexts),
               'duplicate_context_rows_within_file': len(q) - len(contexts),
               'contexts_shared_with_previous_files': len(contexts & seen_context),
               'labels_shared_with_previous_files': len(labels & seen_labels),
               'informative_label_fraction': float((span > 0).mean()),
               'chosen_in_candidate_fraction': float(chosen_in_candidates.mean()),
               'candidate_count_mean': float(mask.sum(1).mean()),
               'label_span_quantiles': np.quantile(span, [0.5, 0.9, 0.99]).tolist(),
               'maximum_absolute_payment': float(np.nanmax(np.abs(q)))}
        results.append(row)
        per_file_contexts[path.name] = contexts
        seen_context.update(contexts)
        seen_labels.update(labels)
        print(json.dumps(row), flush=True)
    pairs = []
    names = list(per_file_contexts)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            overlap = len(per_file_contexts[left] & per_file_contexts[right])
            pairs.append({'left': left, 'right': right, 'shared_contexts': overlap})
    output = {'files': results, 'total_rows': sum(r['rows'] for r in results),
              'unique_contexts': len(seen_context), 'unique_labeled_records': len(seen_labels),
              'pairwise_context_overlap': pairs,
              'limitations': ['No hand seed or episode ID in these archives',
                              'Different contexts do not prove independent hands',
                              'One-future label span is not expected advantage']}
    OUT.write_text(json.dumps(output, indent=2))
    lines = ['# 既有反事實 Rollout 資產稽核（僅存本機）', '',
             '| 檔案 | 筆數 | 與前檔共享局面 | 共享完整標籤 | 非零價差比例 | Teacher在候選內 |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in results:
        lines.append(f'| {row["file"]} | {row["rows"]:,} | '
                     f'{row["contexts_shared_with_previous_files"]:,} | '
                     f'{row["labels_shared_with_previous_files"]:,} | '
                     f'{row["informative_label_fraction"]:.2%} | '
                     f'{row["chosen_in_candidate_fraction"]:.2%} |')
    lines += ['', f'共{output["total_rows"]:,}筆，{len(seen_context):,}種不同CNN局面，'
              f'{len(seen_labels):,}種完整標籤。',
              '局面hash使用float32標準化tiles與scalars，完整標籤另含teacher選擇、候選mask及Q。',
              '這些檔案沒有hand seed／episode ID；不能以row-random split宣稱整手獨立泛化。',
              '不同局面也可能來自同一手，因此沒有重複不代表沒有episode重疊。',
              '本輪只稽核資料，不選checkpoint或調整出牌margin。']
    (ROOT / 'research/ROLLOUT_ASSETS.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
