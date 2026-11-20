"""Robustness of cost bidding to estimate error (T-ASE revision WP3).

    python studies/sigma_robustness.py [OUT_DIR]        # -> OUT_DIR/{S7h,S7d,S7m}.csv, then
    python studies/analyse_sigma.py [OUT_DIR]           # -> studies/report_r2/sigma_robustness.md

S7h  heterogeneous robots (S2 design: B urgency 1|3, loaded, v_max 0.26|0.13; bay x ∈ {2,4,6}; 30 seeds),
     σ ∈ SIGMAS, weighted objective; the crossover against the rulebooks is what gates Table VII.
S7d  single bay (S1/S7 design; bay x ∈ 1…7; 30 seeds), densified σ around the S7 crossover.
S7m  planner mis-specification at σ = 0: the bid planner assumes reverse speed and turn rate scaled by (1+e),
     e ∈ ±{10, 20, 30}%, for both robots (`planner_side` both: a wrong fleet model) or for B only (B: one robot's
     spec is wrong), on both the S1 and S2 grids.

Noise models (`noise` column):
  episode  log-normal factor drawn once per (seed, robot): a persistent, independent mis-estimate per robot;
  time     the S7 model of run_studies_r2.py, redrawn per (seed, robot, snapshot time to 0.1 s).
Both robots evaluate both bids from shared snapshots, so either model keeps the two decisions consistent.
"""
import math
import multiprocessing as mp
import os
import sys
import zlib
from dataclasses import replace
from pathlib import Path

import numpy as np
import run_studies as RS

from amr_negotiation import policies as POL

SIGMAS = [0.0, 0.1, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.75, 1.0]
DENSE = [0.3, 0.35, 0.4, 0.45]
MIS = [-0.3, -0.2, -0.1, 0.1, 0.2, 0.3]
CFG = {'sigma': 0.0, 'seed': 0, 'noise': 'episode', 'mis': 0.0, 'side': 'both'}
_bid = POL.yield_bid


def _bid_with_error(Y, P, sc, objective='total_delay'):
    if CFG['mis']:
        f = 1 + CFG['mis']
        Y, P = (replace(s, v_rev_max=s.v_rev_max * f, w_max=s.w_max * f) if CFG['side'] in ('both', s.id) else s
                for s in (Y, P))
    b = _bid(Y, P, sc, objective)
    if CFG['sigma'] <= 0 or not math.isfinite(b):
        return b
    key = f"{CFG['seed']}|{Y.id}" if CFG['noise'] == 'episode' else f"{CFG['seed']}|{Y.id}|{round(Y.t, 1)}"
    return b * math.exp(CFG['sigma'] * np.random.default_rng(zlib.crc32(key.encode())).standard_normal())


POL.yield_bid = _bid_with_error
EXTRA = ('bid_sigma', 'noise', 'planner_error', 'planner_side')
REFS = [p for p in RS.ALL if p['name'] != 'cost_bid' and p['name'] != 'reactive']
COST = {'name': 'cost_bid'}
S2G = {'agents.1.urgency': [1.0, 3.0], 'agents.1.loaded': ['false', 'true'], 'agents.1.v_max': [0.26, 0.13],
       'bays.0.x': [2.0, 4.0, 6.0]}
S1G = {'bays.0.x': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]}
RND = {'agents.1.start_delay': [0.0, 8.0]}


def job(args):
    study, scen, pol, assign, seed = args
    cost = pol['name'] == 'cost_bid'
    CFG.update(sigma=float(assign.get('bid_sigma', 0.0)) if cost else 0.0, seed=seed,
               noise=assign.get('noise', 'episode'), mis=float(assign.get('planner_error', 0.0)) if cost else 0.0,
               side=assign.get('planner_side', 'both'))
    row = RS.job((study, scen, pol, {k: v for k, v in assign.items() if k not in EXTRA}, seed))
    row.update(assign)
    return row


def jobs(study, grid, extra_grid, pols, seeds):
    return RS.build(study, {'scenario': RS.S, 'seeds': seeds, 'policies': pols, 'grid': {**extra_grid, **grid}, 'random': RND})


def all_jobs(seeds):
    j = []
    j += jobs('S7h', S2G, {'bid_sigma': SIGMAS, 'noise': ['episode']}, [COST], seeds)
    j += jobs('S7h', S2G, {'bid_sigma': DENSE + [0.5], 'noise': ['time']}, [COST], seeds)
    j += jobs('S7h', S2G, {'bid_sigma': [0.0], 'noise': ['-']}, REFS, seeds)
    j += jobs('S7d', S1G, {'bid_sigma': SIGMAS, 'noise': ['episode']}, [COST], seeds)
    j += jobs('S7d', S1G, {'bid_sigma': DENSE, 'noise': ['time']}, [COST], seeds)
    j += jobs('S7d', S1G, {'bid_sigma': [0.0], 'noise': ['-']}, REFS, seeds)
    for name, g in (('S7m_S1', S1G), ('S7m_S2', S2G)):
        j += jobs(name, g, {'planner_error': MIS, 'planner_side': ['both', 'B']}, [COST], seeds)
        j += jobs(name, g, {'planner_error': [0.0]}, REFS + [COST], seeds)
    return j


if __name__ == '__main__':
    out = Path(sys.argv[1] if len(sys.argv) > 1 else 'studies/results'); out.mkdir(parents=True, exist_ok=True)
    J = all_jobs(1 if os.environ.get('SMOKE') else 30)
    with mp.Pool(8) as pool:
        rows = pool.map(job, J, chunksize=4)
    import pandas as pd
    df = pd.DataFrame(rows)
    for st, g in df.groupby('study'):
        g.dropna(axis=1, how='all').to_csv(out / f'{st}.csv', index=False)
        print(st, len(g), 'episodes', flush=True)
