"""Gazebo vs 2D agreement with per-condition paired CIs and a Bland–Altman plot (T-ASE revision WP8).

    python studies/analyse_gazebo_tase.py [GZ_JSONL] [REPORT_DIR]
        # default results_raw/gazebo_current.jsonl.gz, report_r2/ -> gazebo_tase.md, gazebo_tase_runs.csv.gz,
        #   fig/gazebo_bland_altman.png
Every Gazebo run is paired with a 2D rerun of the same scenario file, policy and seed on the current checkout.
Delay = Σ urgency × (arrival − 2D free-flow arrival); the same free-flow reference is used for both simulators.
Agreement = same success flag and same first yielder (None == None counts as agreement), over negotiating
policies (reactive and forced references excluded).
The `main@bf24bf4` batch (122 runs, older code) is reported separately from `all@2ba4c6d`.
"""
import gzip
import json
import math
import multiprocessing as mp
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from amr_negotiation import sim2d
from amr_negotiation.geometry import load_scenario

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
R = str(HERE.parent)
GZ = HERE / "gazebo"


REFS = ("reactive", "forced_A", "forced_B")  # excluded from agreement: reactive is stochastic, forced has no decision


def kind(scn):
    return "corridor" if scn.startswith("gz_s") else scn.split("_")[1]


def case_table():
    """(label, scenario) -> (scenario yaml, policy dict, group) for both batches."""
    t = {}
    for fname, sub in (("runs.txt", "scen"), ("runs_r2.txt", "scen_r2")):
        for line in (GZ / fname).read_text().split("\n"):
            if line.strip():
                k, pol, rb, label, *scn = line.split()
                scn = scn[0] if scn else f"gz_s{k}"
                p = {"name": pol, **({"rulebook": rb.replace("/amr_negotiation", R)} if rb != "-" else {})}
                t[("main", label, scn)] = (GZ / sub / f"{scn}.yaml", p, kind(scn))
    for line in (GZ / "runs_all.txt").read_text().split("\n"):
        if line.strip():
            k, label, scn, pf, grp = line.split()
            p = json.loads((GZ / "scen_all" / "pol" / pf).read_text().replace("/amr_negotiation", R))
            t[("all", label, scn)] = (GZ / "scen_all" / f"{scn}.yaml", p, grp)
    return t


def first_yielder(res):
    for e in res["events"]:
        if e["event"] == "yield_start":
            return e["agent"]
    return None


def pair(args):
    g, path, policy, grp = args
    seed = int(g["scenario"].rsplit("_s", 1)[1])
    sc = load_scenario(path)
    d = sim2d.run_episode(sc, policy, seed=seed)
    u = {a.id: a.urgency for a in sc.agents}
    free = {i: a["arrival"] - a["delay"] for i, a in d["agents"].items() if a.get("arrival") is not None}
    gz = (sum(u[i] * (g["agents"][i]["arrival"] - free[i]) for i in u)
          if g["success"] and len(free) == len(u) else None)
    d2 = sum(u[i] * d["agents"][i]["delay"] for i in u) if d["success"] else None
    return {"batch": g["batch"], "group": grp, "scenario": g["scenario"], "policy": g["policy_label"], "seed": seed,
            "gz_success": bool(g["success"]), "d2_success": bool(d["success"]), "gz_collision": bool(g["collision"]),
            "gz_yielder": first_yielder(g), "d2_yielder": first_yielder(d), "gz_wdelay": gz, "d2_wdelay": d2,
            "gz_makespan": g["makespan"] if g["success"] else None, "d2_makespan": d["makespan"] if d["success"] else None}


def boot_ci(x, n=2000, seed=0):
    x = np.asarray(x, float)
    if len(x) < 2:
        return (math.nan, math.nan)
    b = np.random.default_rng(seed).choice(x, (n, len(x))).mean(1)
    return tuple(np.percentile(b, [2.5, 97.5]))


def wilson(k, n, z=1.96):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n; c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (100 * (c - h), 100 * (c + h))


def summary(df, title):
    neg = df[~df.policy.isin(REFS)]
    k = int(neg.agree.sum()); n = len(neg); lo, hi = wilson(k, n)
    both = df.dropna(subset=["gz_wdelay", "d2_wdelay"])
    dd = both.gz_wdelay - both.d2_wdelay
    md = [f"\n## {title}\n", f"Negotiating runs: agreement {k}/{n} = {100 * k / n:.1f}% (Wilson 95% [{lo:.1f}, {hi:.1f}]); "
          f"collisions {int(neg.gz_collision.sum())}/{n}. Bland–Altman over {len(both)} runs successful in both: "
          f"bias {dd.mean():+.2f} s, limits of agreement [{dd.mean() - 1.96 * dd.std():+.2f}, {dd.mean() + 1.96 * dd.std():+.2f}] s.\n",
          "| group | policy | n | Gazebo success | 2D success | agree | delay Gazebo − 2D, mean [95% CI] (s) |",
          "|---|---|---|---|---|---|---|"]
    for (grp, pol), h in df.groupby(["group", "policy"]):
        b = h.dropna(subset=["gz_wdelay", "d2_wdelay"]); x = b.gz_wdelay - b.d2_wdelay
        ci = boot_ci(x)
        d = f"{x.mean():+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}]" if len(x) > 1 else (f"{x.mean():+.2f}" if len(x) else "–")
        md.append(f"| {grp} | `{pol}` | {len(h)} | {int(h.gz_success.sum())} | {int(h.d2_success.sum())} | "
                  f"{int(h.agree.sum())}/{len(h)} | {d} |")
    return md


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results_raw/gazebo_current.jsonl.gz"
    rep = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "report_r2"
    (rep / "fig").mkdir(parents=True, exist_ok=True)
    t = case_table()
    gz = [json.loads(line) for line in gzip.open(src, "rt")]
    jobs, missing = [], []
    for g in gz:
        key = (g["batch"].split("@")[0], g["policy_label"], g["scenario"])
        (jobs.append((g, *t[key])) if key in t else missing.append(key))
    with mp.Pool(8) as pool:
        df = pd.DataFrame(pool.map(pair, jobs, chunksize=4))
    df["agree"] = (df.gz_success == df.d2_success) & (df.gz_yielder.fillna("-") == df.d2_yielder.fillna("-"))
    df.to_csv(rep / "gazebo_tase_runs.csv.gz", index=False)
    md = ["# Gazebo (ground-truth localization) vs 2D (WP8)", "", __doc__.split("\n", 4)[4].strip(),
          f"\n{len(df)} of {len(gz)} Gazebo runs paired" + (f"; unmatched: {missing}" if missing else ".")]
    md += summary(df, "All runs")
    for b, h in df.groupby("batch"):
        md += summary(h, f"Batch `{b}`")
    both = df.dropna(subset=["gz_wdelay", "d2_wdelay"])
    m, dd = (both.gz_wdelay + both.d2_wdelay) / 2, both.gz_wdelay - both.d2_wdelay
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    for b, h in both.groupby("batch"):
        ax.scatter(m[h.index], dd[h.index], s=6, label=b)
    for y, ls in ((dd.mean(), "-"), (dd.mean() - 1.96 * dd.std(), "--"), (dd.mean() + 1.96 * dd.std(), "--")):
        ax.axhline(y, color="k", lw=0.8, ls=ls)
    ax.set_xlabel("mean of Gazebo and 2D delay [s]", fontsize=8); ax.set_ylabel("Gazebo − 2D [s]", fontsize=8)
    ax.tick_params(labelsize=8); ax.legend(fontsize=7); fig.tight_layout()
    fig.savefig(rep / "fig/gazebo_bland_altman.png", dpi=300)
    (rep / "gazebo_tase.md").write_text("\n".join(md) + "\n"); print("\n".join(md[:12]))
