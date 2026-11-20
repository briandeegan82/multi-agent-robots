"""T-junction with the stem as A's destination: success/deadlock grid (48 runs per policy x loss x goal_wait cell).

`goal_wait` toggles only the destination-refuge logic (`AgentParams.goal_wait`), so the two arms are a one-variable
before/after comparison on the same draws.

usage: python studies/tjunction_goal.py [out.txt]   (per-episode rows: results_raw/tjunction_goal.csv.gz)
"""
import collections
import multiprocessing as mp
import sys
from pathlib import Path

import pandas as pd

from amr_negotiation import sim2d
from amr_negotiation import sweep as SW

ROOT = Path(__file__).resolve().parents[1]
POLS = ['reactive', 'fixed_priority', 'rules_default', 'cost_bid']
COLS = ('policy', 'sd_A', 'sd_B', 'sd_S', 'S_goal_x', 'loss', 'seed', 'goal_wait')


def run(a):
    pol, sd_a, sd_b, sd_s, s_goal, loss, seed, gw = a
    sc = SW.apply_overrides(SW.load_scenario(str(ROOT / 'scenarios/corridor_tjunction_goal.yaml')), SW._overrides({
        'agents.0.start_delay': sd_a, 'agents.1.start_delay': sd_b, 'agents.2.start_delay': sd_s,
        'agents.2.goal_x': s_goal, 'comms.loss': loss}))
    p = {'name': pol} if pol != 'rules_default' else {'name': 'rule_based', 'rulebook': str(ROOT / 'rulebooks/default.yaml')}
    p['agent_params'] = {'goal_wait': gw}
    r = sim2d.run_episode(sc, p, seed=seed)
    return (pol, loss, gw), a, r['success'], r['deadlock'], r['collision'], r.get('total_delay')


if __name__ == '__main__':
    jobs = [(p, a, b, s, g, ls, k, gw) for p in POLS for a in (0.0, 4.0) for b in (0.0, 4.0, 8.0) for s in (0.0, 6.0)
            for g in (10.0, -1.5) for ls in (0.0, 0.5) for k in range(2) for gw in (True, False)]
    with mp.Pool(8) as pool:
        res = pool.map(run, jobs)
    pd.DataFrame([{**dict(zip(COLS, a)), 'success': s, 'deadlock': d, 'collision': c, 'total_delay': td}
                  for _, a, s, d, c, td in res]).to_csv(ROOT / 'studies/results_raw/tjunction_goal.csv.gz', index=False)
    agg = collections.defaultdict(list)
    fails = []
    for key, a, s, d, c, td in res:
        agg[key].append((s, d, c, td))
        if not s and key[0] != 'reactive' and key[2]:
            fails.append(a[:-1])
    lines = ['| policy | loss | goal_wait | n | success | deadlock | collision | mean total delay (s, successes) |',
             '|---|---|---|---|---|---|---|---|']
    for (pol, loss, gw), v in sorted(agg.items(), key=lambda kv: (not kv[0][2], POLS.index(kv[0][0]), kv[0][1])):
        ok = [x[3] for x in v if x[0]]
        md = f'{sum(ok) / len(ok):.1f}' if ok else '-'
        lines.append(f'| {pol} | {loss:.0%} | {"on" if gw else "off"} | {len(v)} | {sum(x[0] for x in v)} | '
                     f'{sum(x[1] for x in v)} | {sum(x[2] for x in v)} | {md} |')
    lines.append(f'\nnon-reactive failures with goal_wait on (pol, sdA, sdB, sdS, S goal_x, loss, seed): {fails}')
    txt = '\n'.join(lines)
    print(txt)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(txt + '\n')
