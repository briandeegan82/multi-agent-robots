# Baseline strength checks (WP6)

S11a  one-at-a-time threshold sensitivity of both rulebooks on the S1 (single bay, 30 seeds), S2 (heterogeneous,
      15 seeds) and S4 (two bays, 20 seeds) grids: urgency threshold, first_in_corridor min_gap,
      refuge_behind_within distance (default rulebook) and closest_refuge tie (proximity rulebook).
S11b  zero-communication baselines: `reactive` (patience U[2, 6] s) and `backoff` (randomized exponential
      backoff, patience U[0, 6·2^k] s after k earlier reactive yields), S1 and S4 grids, 60 | 20 seeds.
Excess delay is per draw against the best forced yielder (`oracle`; `oracle_w` for S2); failures count 180 s/robot.


## S11a_S1

| policy | N | success | collisions | excess delay [s] |
|---|---|---|---|---|
| `rules_default|base` | 210 | 100.0% [98–100] | 0 | 6.39 ± 0.89 |
| `rules_default|urgency.threshold=0.25` | 210 | 100.0% [98–100] | 0 | 6.39 ± 0.89 |
| `rules_default|urgency.threshold=1.0` | 210 | 100.0% [98–100] | 0 | 6.39 ± 0.89 |
| `rules_default|urgency.threshold=2.5` | 210 | 100.0% [98–100] | 0 | 6.39 ± 0.89 |
| `rules_default|first_in_corridor.min_gap=0.5` | 210 | 100.0% [98–100] | 0 | 6.39 ± 0.89 |
| `rules_default|first_in_corridor.min_gap=2.0` | 210 | 100.0% [98–100] | 0 | 6.39 ± 0.89 |
| `rules_default|first_in_corridor.min_gap=4.0` | 210 | 100.0% [98–100] | 0 | 6.39 ± 0.89 |
| `rules_default|refuge_behind_within.distance=1.0` | 210 | 100.0% [98–100] | 0 | 6.04 ± 0.88 |
| `rules_default|refuge_behind_within.distance=3.0` | 210 | 100.0% [98–100] | 0 | 6.39 ± 0.89 |
| `rules_default|refuge_behind_within.distance=4.0` | 210 | 100.0% [98–100] | 0 | 6.39 ± 0.89 |
| `rules_proximity|base` | 210 | 100.0% [98–100] | 0 | 3.15 ± 0.76 |
| `rules_proximity|urgency.threshold=0.25` | 210 | 100.0% [98–100] | 0 | 3.15 ± 0.76 |
| `rules_proximity|urgency.threshold=1.0` | 210 | 100.0% [98–100] | 0 | 3.15 ± 0.76 |
| `rules_proximity|urgency.threshold=2.5` | 210 | 100.0% [98–100] | 0 | 3.15 ± 0.76 |
| `rules_proximity|closest_refuge.tie=0.05` | 210 | 100.0% [98–100] | 0 | 3.15 ± 0.76 |
| `rules_proximity|closest_refuge.tie=0.5` | 210 | 100.0% [98–100] | 0 | 3.37 ± 0.75 |
| `rules_proximity|closest_refuge.tie=1.0` | 210 | 100.0% [98–100] | 0 | 5.62 ± 0.88 |
| `rules_proximity|first_in_corridor.min_gap=0.5` | 210 | 100.0% [98–100] | 0 | 3.15 ± 0.76 |
| `rules_proximity|first_in_corridor.min_gap=2.0` | 210 | 100.0% [98–100] | 0 | 3.15 ± 0.76 |
| `rules_proximity|first_in_corridor.min_gap=4.0` | 210 | 100.0% [98–100] | 0 | 3.15 ± 0.76 |

## S11a_S2

| policy | N | success | collisions | excess delay [s] |
|---|---|---|---|---|
| `rules_default|base` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_default|urgency.threshold=0.25` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_default|urgency.threshold=1.0` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_default|urgency.threshold=2.5` | 360 | 100.0% [99–100] | 0 | 15.67 ± 2.93 |
| `rules_default|first_in_corridor.min_gap=0.5` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_default|first_in_corridor.min_gap=2.0` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_default|first_in_corridor.min_gap=4.0` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_default|refuge_behind_within.distance=1.0` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_default|refuge_behind_within.distance=3.0` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_default|refuge_behind_within.distance=4.0` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_proximity|base` | 360 | 100.0% [99–100] | 0 | 3.59 ± 0.60 |
| `rules_proximity|urgency.threshold=0.25` | 360 | 100.0% [99–100] | 0 | 3.59 ± 0.60 |
| `rules_proximity|urgency.threshold=1.0` | 360 | 100.0% [99–100] | 0 | 3.59 ± 0.60 |
| `rules_proximity|urgency.threshold=2.5` | 360 | 100.0% [99–100] | 0 | 9.09 ± 2.07 |
| `rules_proximity|closest_refuge.tie=0.05` | 360 | 100.0% [99–100] | 0 | 3.59 ± 0.60 |
| `rules_proximity|closest_refuge.tie=0.5` | 360 | 100.0% [99–100] | 0 | 3.31 ± 0.57 |
| `rules_proximity|closest_refuge.tie=1.0` | 360 | 100.0% [99–100] | 0 | 3.50 ± 0.58 |
| `rules_proximity|first_in_corridor.min_gap=0.5` | 360 | 100.0% [99–100] | 0 | 3.59 ± 0.60 |
| `rules_proximity|first_in_corridor.min_gap=2.0` | 360 | 100.0% [99–100] | 0 | 3.59 ± 0.60 |
| `rules_proximity|first_in_corridor.min_gap=4.0` | 360 | 100.0% [99–100] | 0 | 3.59 ± 0.60 |

## S11a_S4

| policy | N | success | collisions | excess delay [s] |
|---|---|---|---|---|
| `rules_default|base` | 360 | 100.0% [99–100] | 0 | 1.24 ± 0.32 |
| `rules_default|urgency.threshold=0.25` | 360 | 100.0% [99–100] | 0 | 1.24 ± 0.32 |
| `rules_default|urgency.threshold=1.0` | 360 | 100.0% [99–100] | 0 | 1.24 ± 0.32 |
| `rules_default|urgency.threshold=2.5` | 360 | 100.0% [99–100] | 0 | 1.24 ± 0.32 |
| `rules_default|first_in_corridor.min_gap=0.5` | 360 | 100.0% [99–100] | 0 | 1.10 ± 0.30 |
| `rules_default|first_in_corridor.min_gap=2.0` | 360 | 100.0% [99–100] | 0 | 1.81 ± 0.39 |
| `rules_default|first_in_corridor.min_gap=4.0` | 360 | 100.0% [99–100] | 0 | 1.96 ± 0.40 |
| `rules_default|refuge_behind_within.distance=1.0` | 360 | 100.0% [99–100] | 0 | 1.24 ± 0.32 |
| `rules_default|refuge_behind_within.distance=3.0` | 360 | 100.0% [99–100] | 0 | 1.10 ± 0.30 |
| `rules_default|refuge_behind_within.distance=4.0` | 360 | 100.0% [99–100] | 0 | 1.10 ± 0.30 |
| `rules_proximity|base` | 360 | 100.0% [99–100] | 0 | 5.61 ± 0.52 |
| `rules_proximity|urgency.threshold=0.25` | 360 | 100.0% [99–100] | 0 | 5.61 ± 0.52 |
| `rules_proximity|urgency.threshold=1.0` | 360 | 100.0% [99–100] | 0 | 5.61 ± 0.52 |
| `rules_proximity|urgency.threshold=2.5` | 360 | 100.0% [99–100] | 0 | 5.61 ± 0.52 |
| `rules_proximity|closest_refuge.tie=0.05` | 360 | 100.0% [99–100] | 0 | 5.61 ± 0.52 |
| `rules_proximity|closest_refuge.tie=0.5` | 360 | 100.0% [99–100] | 0 | 5.22 ± 0.53 |
| `rules_proximity|closest_refuge.tie=1.0` | 360 | 100.0% [99–100] | 0 | 3.21 ± 0.48 |
| `rules_proximity|first_in_corridor.min_gap=0.5` | 360 | 100.0% [99–100] | 0 | 5.61 ± 0.52 |
| `rules_proximity|first_in_corridor.min_gap=2.0` | 360 | 100.0% [99–100] | 0 | 5.61 ± 0.52 |
| `rules_proximity|first_in_corridor.min_gap=4.0` | 360 | 100.0% [99–100] | 0 | 5.61 ± 0.52 |

## S11b_S1

| policy | N | success | collisions | excess delay [s] |
|---|---|---|---|---|
| `reactive` | 420 | 93.8% [91–96] | 0 | 86.52 ± 7.29 |
| `backoff` | 420 | 96.7% [94–98] | 0 | 92.33 ± 6.25 |
| `fixed_priority` | 420 | 100.0% [99–100] | 0 | 6.45 ± 0.64 |

## S11b_S4

| policy | N | success | collisions | excess delay [s] |
|---|---|---|---|---|
| `reactive` | 360 | 97.8% [96–99] | 0 | 72.00 ± 6.23 |
| `backoff` | 360 | 100.0% [99–100] | 0 | 59.08 ± 4.03 |
| `fixed_priority` | 360 | 100.0% [99–100] | 0 | 1.10 ± 0.30 |
