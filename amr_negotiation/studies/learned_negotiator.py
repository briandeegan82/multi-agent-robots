"""Learned negotiator baseline: tabular contextual-bandit yield policy trained in the 2D sim.

For each random training encounter we record the shared observation (`learned_features`) at decision time,
run both forced outcomes (a yields / b yields) and accumulate the urgency-weighted delay of each. Execution is
decentralised: each robot looks the observation up in the same table. Run from amr_negotiation/:
python studies/learned_negotiator.py  ->  report/learned_negotiator.md, report/learned_table.json,
results_raw/learned_eval.csv.gz (weighted delay per evaluation episode; failures charged FAIL s)"""
import json
import multiprocessing as mp
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from amr_negotiation import sim2d
from amr_negotiation import sweep as SW

ROOT = Path(__file__).resolve().parents[1]
FAIL = 300.0  # cost of a failed episode, s


def config(seed, layout):
    g = np.random.default_rng(seed)
    ov = {"agents.0.start_delay": float(g.uniform(0, 4)), "agents.1.start_delay": float(g.uniform(0, 8)),
          "agents.0.urgency": float(g.choice([1.0, 1.0, 3.0])), "agents.1.urgency": float(g.choice([1.0, 1.0, 3.0])),
          "agents.0.loaded": str(g.random() < 0.3).lower(), "agents.1.loaded": str(g.random() < 0.3).lower()}
    if layout == "two_bays":
        ov |= {"bays.0.x": float(g.uniform(1.5, 4.5)), "bays.1.x": float(g.uniform(5.5, 8.5))}
        name = "corridor_two_bays.yaml"
    else:
        ov |= {"bays.0.x": float(g.uniform(1.5, 8.5))}
        name = "corridor_single_bay.yaml"
    return SW.apply_overrides(SW.load_scenario(ROOT / "scenarios" / name), SW._overrides(ov))


def wdelay(r, sc):
    if not r["success"]:
        return FAIL
    u = {a.id: a.urgency for a in sc.agents}
    return sum(u[i] * r["agents"][i]["delay"] for i in u)


def train_one(seed):
    sc = config(seed, "two_bays")
    r = sim2d.run_episode(sc, {"name": "learned", "table": {}}, seed=seed)
    if not r["decisions"]:
        return None
    d = r["decisions"][0]
    ids = sorted(a.id for a in sc.agents)
    cost = {role: wdelay(sim2d.run_episode(sc, {"name": "forced", "yielder": i}, seed=seed), sc)
            for role, i in zip("ab", ids)}
    return d["features"], cost


def evaluate(args):
    seed, layout, table = args
    sc = config(seed, layout)
    rb = str(ROOT / "rulebooks/default.yaml")
    pols = {"fixed_priority": {"name": "fixed_priority"}, "rules_default": {"name": "rule_based", "rulebook": rb},
            "cost_bid": {"name": "cost_bid"}, "learned": {"name": "learned", "table": table}}
    out = {k: wdelay(sim2d.run_episode(sc, p, seed=seed), sc) for k, p in pols.items()}
    out["oracle_w"] = min(wdelay(sim2d.run_episode(sc, {"name": "forced", "yielder": a.id}, seed=seed), sc)
                          for a in sc.agents)
    r = sim2d.run_episode(sc, pols["learned"], seed=seed)
    out["fallback"] = float(any(d["rule"] == "learned:fallback" for d in r["decisions"]))
    return out


def build(samples):
    t = defaultdict(lambda: {"a": [0.0, 0], "b": [0.0, 0]})
    for s in samples:
        if s is None:
            continue
        key, cost = s
        for role in "ab":
            t[key][role][0] += cost[role]
            t[key][role][1] += 1
    return dict(t)


if __name__ == "__main__":
    out = ROOT / "studies" / "report"
    with mp.Pool(8) as pool:
        samples = pool.map(train_one, range(800))
        rows = []
        md = ["| train encounters | eval layout | policy | mean weighted delay (s) | regret vs oracle_w (s) | failures | fallback rate |",
              "|---|---|---|---|---|---|---|"]
        for n in (50, 200, 800):
            table = build(samples[:n])
            for layout in ("two_bays", "single_bay"):
                res = pool.map(evaluate, [(10_000 + s, layout, table) for s in range(150)])
                rows += [{"n_train": n, "layout": layout, "seed": 10_000 + s, **r} for s, r in enumerate(res)]
                orc = np.array([r["oracle_w"] for r in res])
                for k in ("fixed_priority", "rules_default", "cost_bid", "learned", "oracle_w"):
                    if n != 800 and k != "learned":
                        continue
                    v = np.array([r[k] for r in res])
                    fb = f"{np.mean([r['fallback'] for r in res]):.0%}" if k == "learned" else ""
                    md.append(f"| {n} | {layout} | {k} | {v.mean():.1f} ± {1.96 * v.std(ddof=1) / len(v) ** 0.5:.1f} | "
                              f"{(v - orc).mean():+.1f} | {int((v >= FAIL).sum())} | {fb} |")
        pd.DataFrame(rows).to_csv(ROOT / "studies/results_raw/learned_eval.csv.gz", index=False)
        (out / "learned_table.json").write_text(json.dumps(build(samples), indent=1, sort_keys=True))
    md.append(f"\nTable states: {len(build(samples))}; training samples with a decision: {sum(s is not None for s in samples)}/800")
    (out / "learned_negotiator.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
