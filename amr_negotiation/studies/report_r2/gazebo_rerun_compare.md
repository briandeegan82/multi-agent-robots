# Gazebo: 122 original main cases, `bf24bf4` vs rerun on merged main

122 cases; old present 122, rerun present 122.

| kind | n | success old | success rerun | same first yielder | makespan rerun − old, mean (min, max) [s] |
|---|---|---|---|---|---|
| comms | 18 | 18 | 18 | 18/18 | +0.21 (-0.15, +1.45) |
| convoy | 18 | 18 | 18 | 18/18 | +0.02 (-0.10, +0.10) |
| corridor | 50 | 49 | 46 | 50/50 | -0.54 (-27.56, +0.35) |
| tj | 18 | 18 | 18 | 18/18 | +0.08 (-0.25, +1.55) |
| tjgoal | 18 | 18 | 18 | 18/18 | -0.01 (-0.35, +0.25) |

Cases with a different first yielder or |Δ makespan| > 2 s: 1

| scenario   | policy   | old_yielder   | new_yielder   |   old_makespan |   new_makespan |
|:-----------|:---------|:--------------|:--------------|---------------:|---------------:|
| gz_s9      | reactive | B             | B             |         135.96 |         108.40 |
