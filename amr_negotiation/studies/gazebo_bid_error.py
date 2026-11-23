"""Planner prediction error in Gazebo vs 2D on the same seed-paired runs (T-ASE revision, R1 M1.4/Q3).

    python studies/gazebo_bid_error.py [GZ_JSONL] [RUNS_CSV]
        # defaults: results_raw/gazebo_tase.jsonl.gz (else gazebo_current.jsonl.gz), report_r2/gazebo_tase_runs.csv.gz
Error = log(predicted / realized) of the decided plan's urgency-weighted total delay, i.e. the quantity a cost_bid
bid estimates. Predicted: the first logged decision's `predicted.weighted_delay`. Realized: `gz_wdelay` / `d2_wdelay`
from analyse_gazebo_tase.py (same 2D free-flow reference). Two-robot conditions under cost_bid / clarke only, both
runs successful, same first yielder; bid-noise (S7) and map-discovery (explore_*) conditions are excluded.
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "results_raw"
EXCL = ("S7", "convoy", "convoy_B_urgent", "tj", "tjgoal")
STRESS = ("S8b", "S8c_all_off", "asym_own", "wrong_map")  # extreme comms or wrong/partial maps


def main():
    gz = Path(sys.argv[1]) if len(sys.argv) > 1 else next(p for p in (RAW / "gazebo_tase.jsonl.gz",
                                                                       RAW / "gazebo_current.jsonl.gz") if p.exists())
    runs = pd.read_csv(sys.argv[2] if len(sys.argv) > 2 else HERE / "report_r2" / "gazebo_tase_runs.csv.gz")
    pred = {}
    for line in gzip.open(gz, "rt"):
        r = json.loads(line)
        dec = [d for d in r.get("decisions", []) if d.get("predicted")]
        if dec:
            pred[(r["scenario"], r["policy_label"])] = dec[0]["predicted"]["weighted_delay"]
    df = runs[runs.policy.str.startswith(("cost_bid", "clarke")) & ~runs.group.isin(EXCL)
              & ~runs.group.str.startswith("explore") & runs.gz_success & runs.d2_success
              & (runs.gz_yielder == runs.d2_yielder)].copy()
    df["pred"] = [pred.get((s, p), np.nan) for s, p in zip(df.scenario, df.policy)]
    df = df.dropna(subset=["pred"])
    df = df[(df.pred > 0) & (df.gz_wdelay > 0) & (df.d2_wdelay > 0)]
    print(f"# Planner prediction error, Gazebo vs 2D ({gz.name}, n = {len(df)} paired runs)\n")
    print("| simulator | n | SD of log(pred/realized) | median bias pred/realized − 1 |")
    print("|---|---|---|---|")
    for subset, h in (("all", df), ("nominal comms, correct maps", df[~df.group.isin(STRESS)])):
        for name, col in (("Gazebo", "gz_wdelay"), ("2D (same runs)", "d2_wdelay")):
            e = np.log(h.pred / h[col])
            print(f"| {name}, {subset} | {len(e)} | {e.std(ddof=1):.3f} | {np.exp(e.median()) - 1:+.3f} |")
    print("\nPer group (Gazebo SD):", {g: round(float(np.log(h.pred / h.gz_wdelay).std(ddof=1)), 3)
                                     for g, h in df.groupby("group") if len(h) > 2})


if __name__ == "__main__":
    main()
