"""Old-commit vs rerun Gazebo results for the 122 original main cases (T-ASE revision WP8).

    python studies/compare_gazebo_rerun.py  # -> report_r2/gazebo_rerun_compare.md
Pairs each `main@bf24bf4` run in results_raw/gazebo_current.jsonl.gz with its rerun in
results_raw/gazebo_main_rerun.jsonl.gz (same scenario, policy label and seed).
"""
import gzip
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "results_raw"


def first_yielder(r):
    return next((e["agent"] for e in r["events"] if e["event"] == "yield_start"), None)


def load(path, prefix):
    rows = {}
    for line in gzip.open(path, "rt"):
        r = json.loads(line)
        if r["batch"].startswith(prefix):
            rows[(r["scenario"], r["policy_label"])] = r
    return rows


if __name__ == "__main__":
    old, new = load(RAW / "gazebo_current.jsonl.gz", "main@bf24bf4"), load(RAW / "gazebo_main_rerun.jsonl.gz", "main@")
    recs = []
    for k in sorted(old.keys() | new.keys()):
        o, n = old.get(k), new.get(k)
        recs.append({"scenario": k[0], "policy": k[1], "kind": "corridor" if k[0].startswith("gz_s") else k[0].split("_")[1],
                     "old_success": o and o["success"], "new_success": n and n["success"],
                     "old_yielder": o and first_yielder(o), "new_yielder": n and first_yielder(n),
                     "old_makespan": o["makespan"] if o and o["success"] else None,
                     "new_makespan": n["makespan"] if n and n["success"] else None})
    df = pd.DataFrame(recs)
    df["same_yielder"] = df.old_yielder.fillna("-") == df.new_yielder.fillna("-")
    df["d_makespan"] = df.new_makespan - df.old_makespan
    md = ["# Gazebo: 122 original main cases, `bf24bf4` vs rerun on merged main", "",
          f"{len(df)} cases; old present {df.old_success.notna().sum()}, rerun present {df.new_success.notna().sum()}.", "",
          "| kind | n | success old | success rerun | same first yielder | makespan rerun − old, mean (min, max) [s] |",
          "|---|---|---|---|---|---|"]
    for kind, h in df.groupby("kind"):
        d = h.d_makespan.dropna()
        md.append(f"| {kind} | {len(h)} | {int(h.old_success.fillna(False).sum())} | {int(h.new_success.fillna(False).sum())} | "
                  f"{int(h.same_yielder.sum())}/{len(h)} | {d.mean():+.2f} ({d.min():+.2f}, {d.max():+.2f}) |")
    ch = df[~df.same_yielder | (df.d_makespan.abs() > 2)]
    md += ["", f"Cases with a different first yielder or |Δ makespan| > 2 s: {len(ch)}", "",
           ch[["scenario", "policy", "old_yielder", "new_yielder", "old_makespan", "new_makespan"]].to_markdown(index=False, floatfmt=".2f")]
    (HERE / "report_r2/gazebo_rerun_compare.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
