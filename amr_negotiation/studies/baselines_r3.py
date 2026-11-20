"""Baseline strength checks (T-ASE revision WP6).

    python studies/baselines_r3.py [OUT_DIR]   # -> OUT_DIR/{S11a_rule_sensitivity,S11b_backoff,S11c_staging}.csv,
                                               #    studies/report_r2/baselines_r3.md
S11a  one-at-a-time threshold sensitivity of both rulebooks on the S1 (single bay, 30 seeds), S2 (heterogeneous,
      15 seeds) and S4 (two bays, 20 seeds) grids: urgency threshold, first_in_corridor min_gap,
      refuge_behind_within distance (default rulebook) and closest_refuge tie (proximity rulebook).
S11b  zero-communication baselines: `reactive` (patience U[2, 6] s) and `backoff` (randomized exponential
      backoff, patience U[0, 6·2^k] s after k earlier reactive yields), S1 and S4 grids, 60 | 20 seeds.
S11c  corridor reservation with the waiting robot's end-room parking spot at the corridor mouth (default) or
      staged 1.2 | 2.0 m back from it, S1 grid, 30 seeds.
Excess delay is per draw against the best forced yielder (`oracle`; `oracle_w` for S2); failures count 180 s/robot.
"""
import copy
import math
import multiprocessing as mp
import os
import sys
from pathlib import Path

import pandas as pd
import run_studies as RS
import yaml
from analyse_helpers import rate

GRIDS = {'S1': (RS.S, {'bays.0.x': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]}, [0.0, 8.0], 30),
         'S2': (RS.S, {'agents.1.urgency': [1.0, 3.0], 'agents.1.loaded': ['false', 'true'],
                       'agents.1.v_max': [0.26, 0.13], 'bays.0.x': [2.0, 4.0, 6.0]}, [0.0, 8.0], 15),
         'S4': ('scenarios/corridor_two_bays.yaml', {'bays.0.x': [2.0, 3.0, 4.0], 'bays.1.x': [6.0, 7.0, 8.0],
                                                    'bays.1.side': [1, -1]}, [0.0, 10.0], 20)}
SWEEP = {'urgency': ('threshold', [0.25, 1.0, 2.5]), 'first_in_corridor': ('min_gap', [0.5, 2.0, 4.0]),
         'refuge_behind_within': ('distance', [1.0, 3.0, 4.0]), 'closest_refuge': ('tie', [0.05, 0.5, 1.0])}
_SC = RS.SW.load_scenario(str(RS.ROOT / RS.S))
OFF0 = round(_SC.robot.radius + 2 * _SC.clearance + 0.3, 3)  # default room parking offset
REFS = [{'name': 'oracle'}, {'name': 'oracle_w', 'label': 'oracle_w'}]


def rulebook_variants():
    out = []
    for rb in ('rules_default', 'rules_proximity'):
        rules = yaml.safe_load(Path(RS.RB[rb]).read_text())['rules']
        out.append({'name': 'rule_based', 'rulebook': rules, 'label': f'{rb}|base'})
        for i, r in enumerate(rules):
            if r['rule'] in SWEEP:
                par, vals = SWEEP[r['rule']]
                for v in vals:
                    rr = copy.deepcopy(rules); rr[i][par] = v
                    out.append({'name': 'rule_based', 'rulebook': rr, 'label': f'{rb}|{r["rule"]}.{par}={v}'})
    return out


def build(study, g, pols, seeds=None, extra=None):
    scen, grid, sd, n = GRIDS[g]
    spec = {'scenario': scen, 'seeds': seeds or n, 'policies': pols, 'grid': {**(extra or {}), **grid},
            'random': {'agents.1.start_delay': sd}}
    return [(f'{study}_{g}', *j[1:]) for j in RS.build(study, spec)]


def all_jobs(smoke):
    s = (lambda n: 1) if smoke else (lambda n: n)
    j = []
    for g in GRIDS:
        j += build('S11a', g, rulebook_variants() + REFS, s(GRIDS[g][3]))
    for g, n in (('S1', 60), ('S4', 20)):
        j += build('S11b', g, [{'name': 'reactive'}, {'name': 'backoff'}, {'name': 'fixed_priority'}] + REFS, s(n))
    j += build('S11c', 'S1', [{'name': 'reservation'}, {'name': 'rule_based', 'label': 'rules_default'},
                              {'name': 'cost_bid'}] + REFS, s(30), {'room_park_offset': [OFF0, 1.2, 2.0]})
    return j


def excess(df, ref, metric, cells):
    v = df[metric].where(df.success.astype(bool), 360.0)
    w = df.assign(v=v).pivot_table(index=cells + ['seed'], columns='label', values='v', aggfunc='first')
    return w.sub(w[ref], axis=0)


def ci(x):
    x = pd.Series(x).dropna(); return 1.96 * x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else float('nan')


def report(df):
    md = ['# Baseline strength checks (WP6)', '', __doc__.split('\n', 4)[4].strip(), '']
    for st, g in df.groupby('study', sort=False):
        grid = GRIDS[st.split('_')[1]][1]
        cells = list(grid) + (['room_park_offset'] if st.startswith('S11c') else [])
        ref, metric = ('oracle_w', 'wdelay') if st.endswith('S2') else ('oracle', 'total_delay')
        w = excess(g, ref, metric, cells)
        md += [f'\n## {st}\n', '| policy | N | success | collisions | excess delay [s] |', '|---|---|---|---|---|']
        if st.startswith('S11c'):
            for (off, lab), h in g.groupby(['room_park_offset', 'label']):
                e = w.xs(off, level='room_park_offset')[lab]
                md.append(f'| `{lab}`, park offset {off} m | {len(h)} | {rate(h.success.astype(bool))} | '
                          f'{int(h.collision.sum())} | {e.mean():.2f} ± {ci(e):.2f} |')
            continue
        for lab, h in g.groupby('label', sort=False):
            if lab in ('oracle', 'oracle_w'):
                continue
            e = w[lab]
            md.append(f'| `{lab}` | {len(h)} | {rate(h.success.astype(bool))} | {int(h.collision.sum())} | '
                      f'{e.mean():.2f} ± {ci(e):.2f} |')
    return md


if __name__ == '__main__':
    out = Path(sys.argv[1] if len(sys.argv) > 1 else 'studies/results'); out.mkdir(parents=True, exist_ok=True)
    with mp.Pool(8) as pool:
        rows = pool.map(RS.job, all_jobs(bool(os.environ.get('SMOKE'))), chunksize=4)
    df = pd.DataFrame(rows)
    for st in ('S11a', 'S11b', 'S11c'):
        df[df.study.str.startswith(st)].dropna(axis=1, how='all').to_csv(out / f'{st}.csv', index=False)
    md = report(df)
    (Path(__file__).parent / 'report_r2/baselines_r3.md').write_text('\n'.join(md) + '\n'); print('\n'.join(md))
