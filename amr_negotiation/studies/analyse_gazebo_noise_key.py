"""Gazebo S7 noisy-bid runs with episode-keyed noise vs their 2D pairs (T-ASE revision, R1 m9 / noise pairing).

    python studies/analyse_gazebo_noise_key.py   # results_raw/gazebo_noise_episode.jsonl.gz (studies/gazebo/noisekey_run.sh)
Each run uses cost_bid with bid_sigma 0.5 or 1.0 and noise_key="episode" (noise fixed per (seed, robot), so it no
longer depends on the snapshot time stamp). The 2D pair runs the same scenario, seed and policy in sim2d. The
time-keyed rows come from the S7 conditions of report_r2/gazebo_tase_runs.csv.gz for comparison.
"""
import gzip
import json
from pathlib import Path

import pandas as pd

from amr_negotiation import sim2d
from amr_negotiation.geometry import load_scenario

HERE = Path(__file__).resolve().parent


def first_yielder(res):
    return next((e["agent"] for e in res["events"] if e["event"] == "yield_start"), None)


def main():
    rows = []
    for line in gzip.open(HERE / "results_raw" / "gazebo_noise_episode.jsonl.gz", "rt"):
        g = json.loads(line)
        seed = int(g["scenario"].rsplit("_s", 1)[1])
        sigma = 0.5 if "s05" in g["policy_label"] else 1.0
        pol = {"name": "cost_bid", "bid_sigma": sigma, "noise_key": "episode", "noise_seed": seed}
        d = sim2d.run_episode(load_scenario(HERE / "gazebo" / "scen_all" / f"{g['scenario']}.yaml"), pol, seed=seed)
        bids = {k: [x["bids"] for x in g["decisions"] if x["agent"] == k][:1] for k in ("A", "B")}
        rows.append({"sigma": sigma, "seed": seed, "gz_success": g["success"], "gz_yielder": first_yielder(g),
                     "d2_yielder": first_yielder(d), "bids_match": bids["A"] == bids["B"] and bids["A"] != []})
    df = pd.DataFrame(rows).sort_values(["sigma", "seed"])
    df["agree"] = df.gz_yielder == df.d2_yielder
    old = pd.read_csv(HERE / "report_r2" / "gazebo_tase_runs.csv.gz")
    old = old[old.group == "S7"]
    print("| noise keying | sigma | runs | Gazebo success | robots saw identical bids | same first yielder as 2D |")
    print("|---|---|---|---|---|---|")
    for s, h in old.groupby(old.policy.str.extract(r"sigma([\d.]+)")[0].astype(float)):
        print(f"| time (round(t, 1)) | {s} | {len(h)} | {h.gz_success.sum()}/{len(h)} | n/a | {h.agree.sum()}/{len(h)} |")
    for s, h in df.groupby("sigma"):
        print(f"| episode | {s} | {len(h)} | {h.gz_success.sum()}/{len(h)} | {h.bids_match.sum()}/{len(h)} | "
              f"{h.agree.sum()}/{len(h)} |")
    print()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
