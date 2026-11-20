"""Bursty packet loss and blackouts on fresh seeds (T-ASE revision WP7).

    python studies/burst_loss.py [OUT_DIR]   # -> OUT_DIR/S8d_burst_loss.csv, studies/report_r2/burst_loss.md

S8b/S8c used i.i.d. loss on seeds 0–19 of the grid the safeguards were tuned on. Here, on seeds 1000–1019 and
loss levels not used before:
  iid       independent loss at mean rate L ∈ {0.6, 0.8, 0.95};
  burst     Gilbert–Elliott (loss_bad 1, loss_good 0) with the same mean loss and mean burst length
            ℓ ∈ {5, 25, 100} messages (p_bg = 1/ℓ, p_gb = p_bg·L/(1−L));
  blackout  no message gets through for [t0, t0 + T), t0 ∈ {3, 8} s, T ∈ {10, 40} s, otherwise lossless.
Single bay, v_max 0.5 m/s, latency 0.5 s, detection range 1.5 | 6 m. "negotiated" = at least one negotiated
decision recorded; otherwise the robots resolved the encounter with the reactive fallback (Lidar and timers).
"""
import multiprocessing as mp
import os
import sys
from pathlib import Path

import pandas as pd
import run_studies as RS
from analyse_helpers import rate

from amr_negotiation import sim2d

POLS = [{'name': 'fixed_priority'}, {'name': 'rule_based', 'rulebook': RS.RB['rules_default'], 'label': 'rules_default'},
        {'name': 'rule_based', 'rulebook': RS.RB['rules_proximity'], 'label': 'rules_proximity'}, {'name': 'cost_bid'}]
LOSS, BURST, BLACK = (0.6, 0.8, 0.95), (5, 25, 100), [(t0, T) for t0 in (3.0, 8.0) for T in (10.0, 40.0)]
DET = (1.5, 6.0)


def channels():
    ch = [('iid', f'L={L}', {'loss': L}) for L in LOSS]
    ch += [('burst', f'L={L}, len={n}', {'loss': 0.0, 'burst': {'p_bg': 1 / n, 'p_gb': min(1.0, L / (1 - L) / n),
                                                                  'loss_bad': 1.0, 'loss_good': 0.0}})
           for L in LOSS for n in BURST]
    ch += [('blackout', f't0={t0:g}, T={T:g}', {'loss': 0.0, 'blackout': [t0, t0 + T]}) for t0, T in BLACK]
    return ch


def job(a):
    kind, name, comms, pol, det, seed = a
    sd = round(float(RS.np.random.default_rng(10_000 + seed).uniform(0, 8)), 3)
    sc = RS.SW.apply_overrides(RS.SW.load_scenario(str(RS.ROOT / RS.S)), RS.SW._overrides(
        {'robot.v_max': 0.5, 'agents.1.start_delay': sd}))
    sc.comms = {**sc.comms, 'latency': 0.5, 'jitter': 0.02, **comms}
    p = {k: v for k, v in pol.items() if k != 'label'}
    p['agent_params'] = {'detect_range': det}
    r = sim2d.run_episode(sc, p, seed=seed)
    neg = [d for d in r['decisions'] if d.get('rule') != 'reactive']
    return {'kind': kind, 'channel': name, 'label': pol.get('label', pol['name']), 'detect_range': det, 'seed': seed,
            'success': r['success'], 'collision': r['collision'], 'deadlock': r['deadlock'],
            'total_delay': r.get('total_delay'), 'n_decisions': len(r['decisions']), 'negotiated': bool(neg),
            'msgs_dropped': r.get('msgs_dropped'), 'msgs': r.get('msgs')}


def report(df):
    md = ['# Bursty loss and blackouts (WP7)', '', __doc__.split('\n\n', 1)[1].strip(), '',
          '| channel | policy | success | collision | deadlock | negotiated | delay when successful [s] |',
          '|---|---|---|---|---|---|---|']
    for (k, ch, lab), g in df.groupby(['kind', 'channel', 'label'], sort=False):
        ok = g[g.success]
        md.append(f'| {k}: {ch} | `{lab}` | {rate(g.success)} | {rate(g.collision)} | {rate(g.deadlock)} | '
                  f'{rate(g.negotiated)} | {ok.total_delay.mean():.1f} |')
    md += ['', '**Pooled by channel type**', '', '| channel type | N | collisions | success | negotiated |', '|---|---|---|---|---|']
    for k, g in df.groupby('kind', sort=False):
        md.append(f'| {k} | {len(g)} | {int(g.collision.sum())} ({rate(g.collision)}) | {rate(g.success)} | {rate(g.negotiated)} |')
    return md


if __name__ == '__main__':
    out = Path(sys.argv[1] if len(sys.argv) > 1 else 'studies/results'); out.mkdir(parents=True, exist_ok=True)
    seeds = range(1000, 1002 if os.environ.get('SMOKE') else 1020)
    jobs = [(k, n, c, p, d, s) for k, n, c in channels() for p in POLS for d in DET for s in seeds]
    with mp.Pool(8) as pool:
        df = pd.DataFrame(pool.map(job, jobs, chunksize=4))
    for c in ('success', 'collision', 'deadlock'):
        df[c] = df[c].astype(bool)
    df.to_csv(out / 'S8d_burst_loss.csv', index=False)
    md = report(df)
    (Path(__file__).parent / 'report_r2/burst_loss.md').write_text('\n'.join(md) + '\n'); print('\n'.join(md))
