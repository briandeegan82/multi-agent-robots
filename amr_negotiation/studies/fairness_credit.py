"""Repeated-encounter fairness credit, held-out λ and noisy cost estimates (T-ASE revision WP4).

    python studies/fairness_credit.py [OUT_DIR]   # -> OUT_DIR/S10b_*.csv and studies/report_r2/fairness_credit.md

Encounter costs come from forced-yielder runs (`run_studies_r2.job10`), as in S10. Sequences 0–49 are the S10
sequences and serve as the selection set for λ; sequences 100–199 are fresh and are used only for reporting.

Rules (o = yielder, ō = the other robot, D = cumulative delay before the encounter, d(o) = this encounter's delays):
  credit   argmin_o  d_A(o) + d_B(o) + λ (D_o − D_ō)                      Eq. (10) of the revised manuscript
  balance  argmin_o  d_A(o) + d_B(o) + λ |(D_A + d_A(o)) − (D_B + d_B(o))|   the |·| form printed in the reviewed PDF
Decisions use estimates d̂_i(o) = d_i(o)·exp(σ ε), ε ~ N(0,1) drawn per (sequence, encounter, robot, outcome);
cumulative delays D accumulate the true delays, so σ > 0 is an open-loop decision under estimate error with
closed-loop accounting.
"""
import math
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import run_studies_r2 as R2

LAMS = [0.0, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
SIGMAS = [0.0, 0.1, 0.25, 0.5, 1.0]
SELECT, REPORT = range(0, 50), range(100, 200)
J_TARGET = 0.99


def evaluate(encs, rule, lam, sigma):
    D = {'A': 0.0, 'B': 0.0}; n = {'A': 0, 'B': 0}; last = None
    for c in encs:
        rng = np.random.default_rng([c['seq'], c['enc'], 7])
        eps = rng.standard_normal(4) * sigma
        d = {(y, i): c[f'{y}_yields_d{i}'] for y in 'AB' for i in 'AB'}
        dh = {k: v * math.exp(e) for (k, v), e in zip(d.items(), eps)}
        tot = {y: dh[y, 'A'] + dh[y, 'B'] for y in 'AB'}
        feas = [y for y in 'AB' if math.isfinite(tot[y])]
        if rule == 'fixed_priority':
            y = 'B'
        elif rule == 'cost':
            y = min(feas, key=tot.get)
        elif rule == 'alternate':
            y = min(feas, key=tot.get) if last is None else ('A' if last == 'B' else 'B')
            y = y if y in feas else feas[0]
        elif rule == 'credit':
            y = min(feas, key=lambda q: tot[q] + lam * (D[q] - D['B' if q == 'A' else 'A']))
        else:
            y = min(feas, key=lambda q: tot[q] + lam * abs(D['A'] + dh[q, 'A'] - D['B'] - dh[q, 'B']))
        D['A'] += d[y, 'A']; D['B'] += d[y, 'B']; n[y] += 1; last = y
    x = [max(0.0, D['A']), max(0.0, D['B'])]
    jain = 1.0 if sum(v * v for v in x) == 0 else sum(x) ** 2 / (2 * sum(v * v for v in x))
    return {'total': D['A'] + D['B'], 'cum_A': D['A'], 'cum_B': D['B'], 'jain': jain, 'yields_A': n['A']}


def table(ev, seqs):
    e = ev[ev.seq.isin(seqs)]
    cost = e[(e.rule == 'cost')].set_index(['sigma', 'seq']).total
    g = e.set_index(['sigma', 'seq'])
    g = g.assign(overhead=100 * (g.total / cost.xs(0.0, level='sigma').reindex(g.index, level='seq') - 1)).reset_index()
    return g.groupby(['rule', 'lam', 'sigma']).agg(overhead=('overhead', 'mean'), overhead_ci=('overhead', lambda v: 1.96 * v.std(ddof=1) / math.sqrt(len(v))),
                                                  jain=('jain', 'mean'), jain_ci=('jain', lambda v: 1.96 * v.std(ddof=1) / math.sqrt(len(v))), n=('seq', 'size')).reset_index()


if __name__ == '__main__':
    out = Path(sys.argv[1] if len(sys.argv) > 1 else 'studies/results'); out.mkdir(parents=True, exist_ok=True)
    smoke = bool(os.environ.get('SMOKE'))
    seqs = [*SELECT, *REPORT] if not smoke else [0, 1, 100, 101]
    with mp.Pool(8) as pool:
        S = pool.map(R2.job10, seqs)
    pd.DataFrame([c for s in S for c in s]).to_csv(out / 'S10b_encounters.csv', index=False)
    arms = [('fixed_priority', 0.0), ('cost', 0.0), ('alternate', 0.0)] + [(r, lam) for r in ('credit', 'balance') for lam in LAMS[1:]]
    ev = pd.DataFrame([dict(seq=s[0]['seq'], rule=r, lam=lam, sigma=sg, **evaluate(s, r, lam, sg))
                       for s in S for r, lam in arms for sg in SIGMAS])
    ev.to_csv(out / 'S10b_eval.csv', index=False)
    sel, rep = table(ev, SELECT if not smoke else [0, 1]), table(ev, REPORT if not smoke else [100, 101])
    md = ['# Fairness credit: held-out λ and estimate error (WP4)', '', __doc__.split('\n\n', 2)[2].strip(), '']
    for rule in ('credit', 'balance'):
        s0 = sel[(sel.rule == rule) & (sel.sigma == 0.0) & (sel.jain >= J_TARGET)].sort_values('overhead')
        lam = float(s0.lam.iloc[0]) if len(s0) else max(LAMS)
        r = rep[(rep.rule == rule) & (rep.lam == lam)]
        md.append(f'**{rule}**: smallest-overhead λ with J ≥ {J_TARGET} on the selection set = {lam}; on the '
                  f'{len(REPORT)} fresh sequences:\n')
        md.append('| σ | overhead vs cost-optimal (σ=0) | Jain |\n|---|---|---|')
        md += [f'| {x.sigma} | {x.overhead:+.1f}% ± {x.overhead_ci:.1f} | {x.jain:.3f} ± {x.jain_ci:.3f} |' for x in r.itertuples()]
        md.append('')
    md.append(f'\n## All arms, fresh sequences ({len(REPORT)})\n')
    md.append('| rule | λ | σ | overhead | Jain |\n|---|---|---|---|---|')
    md += [f'| `{x.rule}` | {x.lam} | {x.sigma} | {x.overhead:+.1f}% ± {x.overhead_ci:.1f} | {x.jain:.3f} ± {x.jain_ci:.3f} |' for x in rep.itertuples()]
    rp = Path(__file__).parent / 'report_r2/fairness_credit.md'
    rp.write_text('\n'.join(md) + '\n'); print('\n'.join(md[:40]))
