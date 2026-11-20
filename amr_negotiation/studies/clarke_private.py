"""Clarke-pivot payments with private types and per-outcome misreports (T-ASE revision WP5).

    python studies/clarke_private.py [OUT_DIR]   # -> OUT_DIR/S9b_clarke_private.csv, studies/report_r2/clarke_private.md

S9 scaled a robot's whole cost vector by one factor k, with types computed from shared snapshots, so 0/108
profitable misreports is an implementation check of the Clarke rule. This study adds two deviations:
  scale2   robot i reports k_A·c_i(A) and k_B·c_i(B), with (k_A, k_B) ∈ K², k_A ≠ k_B or both ≠ 1;
  urgency  robot i reports a false private urgency û_i; its reports are recomputed by the planner from the
           altered snapshot (the planner's choice of refuge depends on urgency), while its true type keeps u_i.
Gain = deviator's truthful utility minus deviating utility, utility = −(u_i·d_i + p_i), using predicted costs
(the mechanism's guarantee) and realized delays (what the robot experiences). Payments go to a bank.
"""
import math
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import run_studies as RS

from amr_negotiation import sim2d
from amr_negotiation.mechanism import clarke

S = RS.S
K = (0.5, 0.8, 1.0, 1.25, 2.0)
UREP = (0.5, 1.0, 2.0, 3.0, 5.0)
X = (2.0, 4.0, 6.0)


def job(a):
    arm, who, dev, u_b, x, seed = a
    sd = round(float(np.random.default_rng(10_000 + seed).uniform(0, 8)), 3)
    sc = RS.SW.apply_overrides(RS.SW.load_scenario(str(RS.ROOT / S)), RS.SW._overrides(
        {'bays.0.x': x, 'agents.1.start_delay': sd, 'agents.1.urgency': u_b}))
    pol = {'name': 'clarke'}
    if arm == 'scale2':
        pol['report_scale'] = {who: {'A': dev[0], 'B': dev[1]}}
    elif arm == 'urgency':
        pol['report_urgency'] = {who: dev}
    r = sim2d.run_episode(sc, pol, seed=seed)
    d = next((d for d in r['decisions'] if 'payments' in d), {})
    row = {'arm': arm, 'who': who, 'dev': str(dev), 'u_B': u_b, 'x': x, 'seed': seed, 'success': r['success'],
           'collision': r.get('collision'), 'yielder': d.get('yielder'), 'total_delay': r.get('total_delay'),
           'delay_A': r['agents']['A'].get('delay'), 'delay_B': r['agents']['B'].get('delay')}
    row.update({f'pay_{i}': p for i, p in (d.get('payments') or {}).items()})
    t = d.get('types')
    if t and who in 'AB':
        y_t, p_t = clarke(t)
        row.update(truthful_yielder=y_t, pred_cost=t[d['yielder']][who] + d['payments'][who],
                   pred_cost_truthful=t[y_t][who] + p_t[who], pay=d['payments'][who])
    return row


def jobs(seeds):
    j = []
    for u, x, s in ((u, x, s) for u in (1.0, 3.0) for x in X for s in range(seeds)):
        j.append(('truthful', '-', '-', u, x, s))
        j += [('scale2', w, (ka, kb), u, x, s) for w in 'AB' for ka in K for kb in K if (ka, kb) != (1.0, 1.0)]
        true_u = {'A': 1.0, 'B': u}
        j += [('urgency', w, ur, u, x, s) for w in 'AB' for ur in UREP if ur != true_u[w]]
    return j


def report(df):
    ok = df[df.success.astype(bool)]
    base = ok[ok.arm == 'truthful'].set_index(['u_B', 'x', 'seed'])
    dv = ok[ok.arm != 'truthful'].copy()
    b = base.reindex(list(zip(dv.u_B, dv.x, dv.seed)))
    isA = (dv.who == 'A').values
    w = np.where(isA, 1.0, dv.u_B)
    dv['gain_pred'] = dv.pred_cost_truthful - dv.pred_cost
    dv['gain_real'] = (np.where(isA, b.delay_A, b.delay_B) * w + np.where(isA, b.pay_A, b.pay_B)
                       - (np.where(isA, dv.delay_A, dv.delay_B) * w + dv.pay))
    md = ['# Clarke pivot with private types (WP5)', '', __doc__.split('\n\n', 2)[1].strip(), '',
          f'Successful deviating episodes: {len(dv)} of {int((df.arm != "truthful").sum())}. '
          'Gain > 0 means the deviation paid off; "profitable" counts gains above 0.01 s.', '',
          '| arm | deviator | u_B | N | predicted gain: mean | max | profitable | realized gain: mean ± 95% CI | profitable | outcome changed |',
          '|---|---|---|---|---|---|---|---|---|---|']
    for (arm, who, ub), g in dv.groupby(['arm', 'who', 'u_B']):
        r = g.gain_real.dropna(); h = 1.96 * r.std(ddof=1) / math.sqrt(len(r)) if len(r) > 1 else float('nan')
        md.append(f'| {arm} | {who} | {ub:g} | {len(g)} | {g.gain_pred.mean():+.3f} | {g.gain_pred.max():+.3f} | '
                  f'{int((g.gain_pred > 0.01).sum())} | {r.mean():+.2f} ± {h:.2f} | {int((r > 0.01).sum())} | '
                  f'{100 * (g.yielder != g.truthful_yielder).mean():.0f}% |')
    return md


if __name__ == '__main__':
    out = Path(sys.argv[1] if len(sys.argv) > 1 else 'studies/results'); out.mkdir(parents=True, exist_ok=True)
    with mp.Pool(8) as pool:
        rows = pool.map(job, jobs(1 if os.environ.get('SMOKE') else 30), chunksize=4)
    df = pd.DataFrame(rows)
    df.to_csv(out / 'S9b_clarke_private.csv', index=False)
    md = report(df)
    (Path(__file__).parent / 'report_r2/clarke_private.md').write_text('\n'.join(md) + '\n'); print('\n'.join(md))
