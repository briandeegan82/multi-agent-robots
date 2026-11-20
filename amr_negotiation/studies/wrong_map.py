"""Wrong maps: a bay that is on every robot's map but physically blocked (corridor_two_bays).

Run from amr_negotiation/: python studies/wrong_map.py  (per-episode rows: results_raw/wrong_map.csv.gz)"""
import collections
import multiprocessing as mp
from pathlib import Path

import numpy as np
import pandas as pd

from amr_negotiation import sim2d
from amr_negotiation import sweep as SW

ROOT = Path(__file__).resolve().parents[1]
BLOCK = {"none": [], "bay0": ["bay0"], "bay1": ["bay1"], "both": ["bay0", "bay1"]}


def run(a):
    blk, pol, loss, seed = a
    ov = {"comms.loss": loss, "agents.1.start_delay": float(np.random.default_rng(seed).uniform(0, 8))}
    sc = SW.apply_overrides(SW.load_scenario(ROOT / "scenarios/corridor_two_bays.yaml"), SW._overrides(ov))
    sc.blocked_bays = BLOCK[blk]
    p = {"name": pol} if pol != "rules_default" else {"name": "rule_based", "rulebook": str(ROOT / "rulebooks/default.yaml")}
    r = sim2d.run_episode(sc, p, seed=seed, record=True)
    ev = collections.Counter(e["event"] for e in r["events"])
    return a, r["success"], r["deadlock"], r["collision"], r.get("total_delay"), ev["decision"]


if __name__ == "__main__":
    pols = ["reactive", "fixed_priority", "rules_default", "cost_bid"]
    jobs = [(b, p, lo, s) for b in BLOCK for p in pols for lo in (0.0, 0.5) for s in range(10)]
    with mp.Pool(8) as pool:
        res = pool.map(run, jobs)
    pd.DataFrame([{'blocked': a[0], 'policy': a[1], 'loss': a[2], 'seed': a[3], 'success': su, 'deadlock': d,
                   'collision': c, 'total_delay': td, 'n_decisions': nd} for a, su, d, c, td, nd in res]
                 ).to_csv(ROOT / 'studies/results_raw/wrong_map.csv.gz', index=False)
    base = {(a[1], a[2], a[3]): td for a, _, _, _, td, _ in res if a[0] == "none"}
    agg = collections.defaultdict(list)
    for a, s, d, c, td, nd in res:
        extra = td - base[(a[1], a[2], a[3])] if s and td is not None and base[(a[1], a[2], a[3])] is not None else np.nan
        agg[(a[0], a[1], a[2])].append((s, d, c, td if s else np.nan, extra, nd))
    print("| blocked | policy | loss | success | deadlock | collision | mean delay (s) | extra vs none (s) | decisions/run |")
    print("|---|---|---|---|---|---|---|---|---|")
    for (b, p, lo), v in agg.items():
        z = np.array(v, dtype=float)
        print(f"| {b} | {p} | {lo:.0%} | {int(z[:, 0].sum())}/{len(z)} | {int(z[:, 1].sum())} | {int(z[:, 2].sum())} | "
              f"{np.nanmean(z[:, 3]):.1f} | {np.nanmean(z[:, 4]):+.1f} | {z[:, 5].mean():.1f} |")
