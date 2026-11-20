"""Summarise sigma_robustness.py output -> studies/report_r2/sigma_robustness.md (paired, stratified bootstrap CIs)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(sys.argv[1] if len(sys.argv) > 1 else 'studies/results')
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).parent / 'report_r2/sigma_robustness.md')
RNG = np.random.default_rng(0); NB = 2000; T_MAX = 180.0
CELL = {'S7h': ['agents.1.urgency', 'agents.1.loaded', 'agents.1.v_max', 'bays.0.x'], 'S7d': ['bays.0.x']}


def boot(d, strata):
    groups = [np.flatnonzero(strata == s) for s in np.unique(strata)]
    m = [d[np.concatenate([g[RNG.integers(0, len(g), len(g))] for g in groups])].mean() for _ in range(NB)]
    return np.percentile(m, [2.5, 97.5])


def fmt(d, strata):
    lo, hi = boot(d, strata)
    return f'{d.mean():+.2f} [{lo:+.2f}, {hi:+.2f}]'


def values(df, metric):
    return df[metric].where(df.success.astype(bool), 2 * T_MAX)


def section(name, metric, ref, arm, cells):
    df = pd.read_csv(D / f'{name}.csv')
    df['v'] = values(df, metric)
    refs = df[df.label != 'cost_bid'].pivot_table(index=cells + ['seed'], columns='label', values='v')
    md = [f'| {arm} | N | cost_bid Δπ | − rules_default | − rules_proximity | − fixed_priority | same yielder as {ref} |',
          '|---|---|---|---|---|---|---|']
    keys = [c for c in ('noise', 'bid_sigma', 'planner_side', 'planner_error') if c in df]
    cb = df[df.label == 'cost_bid']
    ry = df[df.label == ref].set_index(cells + ['seed']).yielder
    for k, g in cb.groupby([c for c in keys if c in cb]):
        w = g.set_index(cells + ['seed']).v
        r = refs.loc[w.index]
        strata = np.array(['|'.join(map(str, i[:-1])) for i in w.index])
        same = (g.set_index(cells + ['seed']).yielder == ry.loc[w.index]).mean()
        cols = [fmt((w - r[ref]).values, strata)] + [fmt((w - r[p]).values, strata) for p in ('rules_default', 'rules_proximity', 'fixed_priority')]
        md.append(f"| {', '.join(map(str, k))} | {len(w)} | " + ' | '.join(cols) + f' | {100 * same:.0f}% |')
    return md


md = ['# Cost bidding under estimate error (WP3)', '',
      'Mean paired difference per draw, 95% stratified bootstrap CI (seeds resampled within grid cells); '
      'failures charged 180 s per robot. Negative “− policy” = cost_bid better.', '',
      '## S7h — heterogeneous robots (urgency-weighted delay, vs oracle_w)', '']
md += section('S7h', 'wdelay', 'oracle_w', 'noise, σ', CELL['S7h'])
md += ['', '## S7d — single bay, densified σ (total delay, vs oracle)', '']
md += section('S7d', 'total_delay', 'oracle', 'noise, σ', CELL['S7d'])
md += ['', '## S7m — planner mis-specification of reverse speed and turn rate (σ = 0)', '']
for name, metric, ref, c in (('S7m_S1', 'total_delay', 'oracle', CELL['S7d']), ('S7m_S2', 'wdelay', 'oracle_w', CELL['S7h'])):
    md += ['', f'**{name[-2:]} grid**', ''] + section(name, metric, ref, 'planner side, error', c)
OUT.write_text('\n'.join(md) + '\n'); print('\n'.join(md))
