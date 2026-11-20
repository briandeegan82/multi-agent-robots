"""2D-sim studies for the open questions in docs/literature_review.md (see studies/REPORT.md).

    python studies/run_studies.py studies/results [S1_baseline S2_asymmetry ...]
    python studies/analyse.py studies/results      # -> results.md + fig/

Writes one per-episode CSV per study. Unlike `amrneg-sweep`, rows carry per-robot delays,
urgency-weighted delay, a Jain fairness index, and an urgency-weighted oracle (`oracle_w`).
S6 studies cost-bid misreporting by scaling one robot's bid (wrapper around `policies.yield_bid`).
"""
import csv
import math
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np

from amr_negotiation import policies as POL
from amr_negotiation import sim2d
from amr_negotiation import sweep as SW

ROOT = Path(__file__).resolve().parents[1]
RB = {'rules_default': str(ROOT / 'rulebooks/default.yaml'), 'rules_proximity': str(ROOT / 'rulebooks/proximity_first.yaml')}
ALL = [{'name': 'reactive'}, {'name': 'fixed_priority'},
       {'name': 'rule_based', 'rulebook': RB['rules_default'], 'label': 'rules_default'},
       {'name': 'rule_based', 'rulebook': RB['rules_proximity'], 'label': 'rules_proximity'},
       {'name': 'cost_bid'}, {'name': 'oracle'}, {'name': 'oracle_w', 'label': 'oracle_w'}]
NEG = [p for p in ALL if p['name'] in ('fixed_priority', 'rule_based', 'cost_bid')]
S = 'scenarios/corridor_single_bay.yaml'
STUDIES = {
 'S1_baseline': {'scenario': S, 'seeds': 60, 'policies': ALL, 'grid': {'bays.0.x': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]}, 'random': {'agents.1.start_delay': [0.0, 8.0]}},
 'S2_asymmetry': {'scenario': S, 'seeds': 30, 'policies': ALL, 'grid': {'agents.1.urgency': [1.0, 3.0], 'agents.1.loaded': ['false', 'true'], 'agents.1.v_max': [0.26, 0.13], 'bays.0.x': [2.0, 4.0, 6.0]}, 'random': {'agents.1.start_delay': [0.0, 8.0]}},
 'S3_comms': {'scenario': S, 'seeds': 30, 'policies': NEG, 'grid': {'comms.loss': [0.0, 0.1, 0.3, 0.5, 0.7, 0.9], 'comms.latency': [0.05, 0.25, 0.5, 1.0, 2.0]}, 'random': {'agents.1.start_delay': [0.0, 8.0]}},
 'S4_two_bays': {'scenario': 'scenarios/corridor_two_bays.yaml', 'seeds': 20, 'policies': ALL, 'grid': {'bays.0.x': [2.0, 3.0, 4.0], 'bays.1.x': [6.0, 7.0, 8.0], 'bays.1.side': [1, -1]}, 'random': {'agents.1.start_delay': [0.0, 10.0]}},
 'S6_misreport': {'scenario': S, 'seeds': 60, 'policies': [{'name': 'cost_bid', 'label': f'cost_bid_Bx{k}', 'bid_scale': {'B': k}} for k in (1, 1.5, 2, 4, 10)] + [{'name': 'oracle'}], 'grid': {'bays.0.x': [2.0, 4.0, 6.0]}, 'random': {'agents.1.start_delay': [0.0, 8.0]}},
}
_orig_bid = POL.yield_bid
SCALE = {}
def _scaled_bid(Y, P, sc, objective='total_delay'):
    return _orig_bid(Y, P, sc, objective) * SCALE.get(Y.id, 1.0)
POL.yield_bid = _scaled_bid

def wdelay(res, sc):
    if not res.get('total_delay') and res.get('total_delay') != 0: return None
    u = {a.id: a.urgency for a in sc.agents}
    return sum(u[i] * r['delay'] for i, r in res['agents'].items())

def job(args):
    study, scen, pol, assign, seed = args
    sc = SW.apply_overrides(SW.load_scenario(scen), SW._overrides(assign))
    pol = dict(pol); label = pol.pop('label', pol['name'])
    SCALE.clear(); SCALE.update(pol.pop('bid_scale', {}))
    if pol['name'] in ('oracle', 'oracle_w'):
        best = None
        for a in sc.agents:
            r = sim2d.run_episode(sc, {'name': 'forced', 'yielder': a.id}, seed=seed)
            key = (r['total_delay'] if pol['name'] == 'oracle' else wdelay(r, sc)) if r['success'] else math.inf
            if best is None or key < best[0]: best = (key, r)
        res = best[1]
    else:
        res = sim2d.run_episode(sc, pol, seed=seed)
    ag = res['agents']; ids = sorted(ag)
    d = {i: ag[i].get('delay') for i in ids}
    jain = None
    if all(v is not None for v in d.values()):
        x = [max(0.0, d[i]) for i in ids]; s2 = sum(v * v for v in x)
        jain = 1.0 if s2 == 0 else sum(x) ** 2 / (len(x) * s2)
    yielders = sorted({e['agent'] for e in res['events'] if e['event'] == 'yield_start'})
    row = {'study': study, 'label': label, 'seed': seed, 'success': res['success'], 'deadlock': res['deadlock'], 'collision': res['collision'],
               'makespan': res.get('makespan'), 'total_delay': res.get('total_delay'), 'max_delay': res.get('max_delay'), 'wdelay': wdelay(res, sc),
               'jain': jain, 'reverse_dist': sum(a['reverse_dist'] for a in ag.values()), 'yielder': res.get('yielder'), 'n_yielders': len(yielders),
               'refuge': res.get('refuge'), 'rule': res.get('rule'), 'msgs': res['msgs'], 'msgs_dropped': res['msgs_dropped'],
               'time_to_decide': res.get('time_to_decide'), 'agreement': res.get('agreement'), 'n_yields': res.get('n_yields'),
               'min_clearance': res.get('min_clearance'), 'wall_hits': res.get('wall_hits')}
    for i in ids:
        row[f'delay_{i}'] = d[i]; row[f'reverse_{i}'] = ag[i]['reverse_dist']
    dec = res['decisions']
    row['n_decisions'] = len(dec)
    first = dec[0] if dec else {}
    for i, b in (first.get('bids') or {}).items():
        row[f'bid_{i}'] = b
    plan = first.get('predicted')
    if plan:
        row['pred_yielder_delay'], row['pred_proceeder_delay'] = plan['yielder_delay'], plan['proceeder_delay']
    row.update(assign)
    return row

def build(study, spec):
    jobs = []; keys = list(spec['grid'])
    import itertools
    for combo in itertools.product(*[spec['grid'][k] for k in keys]):
        for seed in range(spec['seeds']):
            rng = np.random.default_rng(10_000 + seed)
            assign = dict(zip(keys, combo))
            assign.update({k: round(float(rng.uniform(*v)), 3) for k, v in spec['random'].items()})
            for p in spec['policies']:
                jobs.append((study, str(ROOT / spec['scenario']), p, assign, seed))
    return jobs

if __name__ == '__main__':
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    names = sys.argv[2:] or list(STUDIES)
    smoke = os.environ.get('SMOKE')
    for n in names:
        spec = dict(STUDIES[n])
        if smoke: spec['seeds'] = 1
        jobs = build(n, spec)
        with mp.Pool(8) as pool: rows = pool.map(job, jobs, chunksize=4)
        cols = list(dict.fromkeys(k for r in rows for k in r))
        with open(out / f'{n}.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
        print(n, len(rows), 'episodes', flush=True)
