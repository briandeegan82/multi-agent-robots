# Gazebo (ground-truth localization) vs 2D (WP8)

#   fig/gazebo_bland_altman.png
Every Gazebo run is paired with a 2D rerun of the same scenario file, policy and seed on the current checkout.
Delay = Σ urgency × (arrival − 2D free-flow arrival); the same free-flow reference is used for both simulators.
Agreement = same success flag and same first yielder (None == None counts as agreement), over negotiating
policies (reactive and forced references excluded).
Default input: the 338 `all@2ba4c6d` runs plus the 122 original main cases rerun on `a276da6` (arm64 image,
`main@a276da6`). The superseded `main@bf24bf4` runs stay in `gazebo_current.jsonl.gz`; see `compare_gazebo_rerun.py`.

460 of 460 Gazebo runs paired.

## All runs

Negotiating runs: agreement 394/406 = 97.0% (Wilson 95% [94.9, 98.3]); collisions 0/406. Bland–Altman over 456 runs successful in both: bias -1.35 s, limits of agreement [-27.57, +24.87] s.

| group | policy | n | Gazebo success | 2D success | agree | delay Gazebo − 2D, mean [95% CI] (s) |
|---|---|---|---|---|---|---|
| S1 | `clarke` | 10 | 10 | 10 | 10/10 | -0.31 [-0.37, -0.26] |
| S1 | `forced_A` | 10 | 10 | 10 | 10/10 | -0.36 [-0.44, -0.27] |
| S1 | `forced_B` | 10 | 10 | 10 | 10/10 | -0.44 [-0.55, -0.33] |
| S1 | `learned` | 10 | 10 | 10 | 10/10 | -0.40 [-0.51, -0.29] |
| S1 | `reservation` | 10 | 10 | 10 | 10/10 | -0.35 [-0.36, -0.35] |
| S2_slow | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.03 [-0.46, +0.47] |
| S2_slow | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.70 [-0.80, -0.59] |
| S2_slow | `forced_A` | 6 | 6 | 6 | 6/6 | +0.40 [-0.16, +0.94] |
| S2_slow | `forced_B` | 6 | 6 | 6 | 6/6 | -0.56 [-0.67, -0.42] |
| S2_slow | `rules_default` | 6 | 6 | 6 | 6/6 | -0.56 [-0.71, -0.43] |
| S2_urgent | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.47 [-0.85, -0.14] |
| S2_urgent | `fixed_priority` | 6 | 6 | 6 | 6/6 | -1.43 [-1.73, -1.16] |
| S2_urgent | `forced_A` | 6 | 6 | 6 | 6/6 | -0.39 [-0.58, -0.25] |
| S2_urgent | `forced_B` | 6 | 6 | 6 | 6/6 | -1.50 [-1.72, -1.29] |
| S2_urgent | `rules_default` | 6 | 6 | 6 | 6/6 | -0.41 [-0.67, -0.16] |
| S4 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.21 [-0.25, -0.16] |
| S4 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.16 [-0.22, -0.09] |
| S4 | `rules_default` | 6 | 6 | 6 | 6/6 | -0.17 [-0.26, -0.09] |
| S4_same_side | `cost_bid` | 4 | 4 | 4 | 4/4 | -0.18 [-0.30, -0.07] |
| S4_same_side | `fixed_priority` | 4 | 4 | 4 | 4/4 | -0.12 [-0.15, -0.10] |
| S4_same_side | `rules_default` | 4 | 4 | 4 | 4/4 | -0.26 [-0.37, -0.15] |
| S7 | `cost_bid_sigma0.5` | 6 | 6 | 6 | 4/6 | +1.28 [-1.33, +5.57] |
| S7 | `cost_bid_sigma1.0` | 6 | 6 | 6 | 3/6 | +3.17 [-0.97, +7.43] |
| S8b | `cost_bid` | 6 | 6 | 6 | 4/6 | -2.95 [-39.27, +26.84] |
| S8b | `fixed_priority` | 6 | 6 | 6 | 5/6 | +8.89 [-1.05, +26.32] |
| S8c_all_off | `cost_bid` | 6 | 6 | 6 | 5/6 | +11.28 [-0.19, +28.34] |
| S8c_all_off | `fixed_priority` | 6 | 6 | 6 | 4/6 | +2.15 [-15.02, +24.09] |
| S9 | `clarke_ABx0.5` | 6 | 6 | 6 | 6/6 | -0.39 [-0.55, -0.27] |
| S9 | `clarke_Ax0.5` | 6 | 6 | 6 | 6/6 | -0.36 [-0.53, -0.24] |
| S9 | `clarke_Bx0.5` | 6 | 6 | 6 | 6/6 | -0.30 [-0.36, -0.25] |
| asym_own | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.39 [-0.42, -0.36] |
| asym_own | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.46 [-0.50, -0.41] |
| asym_share | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.22 [-0.24, -0.18] |
| asym_share | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.22 [-0.28, -0.17] |
| comms | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.49 [-1.52, +0.37] |
| comms | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.49 [-1.80, +0.79] |
| comms | `rules_default` | 6 | 6 | 6 | 6/6 | -0.50 [-1.77, +0.77] |
| convoy | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.23 [-0.27, -0.19] |
| convoy | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.24 [-0.27, -0.21] |
| convoy | `group_bid` | 6 | 6 | 6 | 6/6 | -0.28 [-0.34, -0.23] |
| convoy | `rules_default` | 6 | 6 | 6 | 6/6 | -0.23 [-0.27, -0.19] |
| convoy_B_urgent | `fixed_priority` | 6 | 6 | 6 | 6/6 | -1.17 [-1.30, -1.03] |
| convoy_B_urgent | `group_bid` | 6 | 6 | 6 | 6/6 | -1.13 [-1.17, -1.07] |
| corridor | `cost_bid` | 10 | 10 | 10 | 10/10 | -0.27 [-0.33, -0.21] |
| corridor | `fixed_priority` | 10 | 10 | 10 | 10/10 | -0.35 [-0.43, -0.27] |
| corridor | `reactive` | 10 | 6 | 10 | 3/10 | -6.62 [-65.22, +39.98] |
| corridor | `rules_default` | 10 | 10 | 10 | 10/10 | -0.36 [-0.44, -0.28] |
| corridor | `rules_proximity` | 10 | 10 | 10 | 10/10 | -0.35 [-0.44, -0.27] |
| explore_all_3.5 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.16 [-0.25, -0.07] |
| explore_all_3.5 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.18 [-0.22, -0.14] |
| explore_all_6.0 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.20 [-0.26, -0.12] |
| explore_all_6.0 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.15 [-0.20, -0.11] |
| explore_det_3.5 | `cost_bid` | 6 | 6 | 6 | 5/6 | +0.08 [-0.19, +0.51] |
| explore_det_3.5 | `fixed_priority` | 6 | 6 | 6 | 6/6 | +6.79 [-0.19, +20.68] |
| explore_det_6.0 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.31 [-0.40, -0.23] |
| explore_det_6.0 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.45 [-0.50, -0.41] |
| explore_full_3.5 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.24 [-0.27, -0.21] |
| explore_full_3.5 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.21 [-0.27, -0.15] |
| explore_none_3.5 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.24 [-0.32, -0.17] |
| explore_none_3.5 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.66 [-1.31, -0.27] |
| explore_none_6.0 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.37 [-0.41, -0.32] |
| explore_none_6.0 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.41 [-0.46, -0.38] |
| tj | `cost_bid` | 6 | 6 | 6 | 6/6 | -44.15 [-86.50, -22.81] |
| tj | `fixed_priority` | 6 | 6 | 6 | 6/6 | +2.97 [+0.65, +5.18] |
| tj | `rules_default` | 6 | 6 | 6 | 6/6 | -1.76 [-11.07, +4.17] |
| tjgoal | `cost_bid` | 6 | 6 | 6 | 6/6 | -11.13 [-11.38, -10.92] |
| tjgoal | `fixed_priority` | 6 | 6 | 6 | 6/6 | -23.02 [-27.50, -17.32] |
| tjgoal | `rules_default` | 6 | 6 | 6 | 6/6 | -23.41 [-27.49, -18.09] |
| wrong_map | `cost_bid` | 6 | 6 | 6 | 6/6 | -1.14 [-1.26, -1.05] |
| wrong_map | `fixed_priority` | 6 | 6 | 6 | 6/6 | -1.21 [-1.31, -1.11] |
| wrong_map | `rules_default` | 6 | 6 | 6 | 6/6 | -1.26 [-1.36, -1.14] |

## Batch `all@2ba4c6d`

Negotiating runs: agreement 282/294 = 95.9% (Wilson 95% [93.0, 97.6]); collisions 0/294. Bland–Altman over 338 runs successful in both: bias +0.16 s, limits of agreement [-15.43, +15.74] s.

| group | policy | n | Gazebo success | 2D success | agree | delay Gazebo − 2D, mean [95% CI] (s) |
|---|---|---|---|---|---|---|
| S1 | `clarke` | 10 | 10 | 10 | 10/10 | -0.31 [-0.37, -0.26] |
| S1 | `forced_A` | 10 | 10 | 10 | 10/10 | -0.36 [-0.44, -0.27] |
| S1 | `forced_B` | 10 | 10 | 10 | 10/10 | -0.44 [-0.55, -0.33] |
| S1 | `learned` | 10 | 10 | 10 | 10/10 | -0.40 [-0.51, -0.29] |
| S1 | `reservation` | 10 | 10 | 10 | 10/10 | -0.35 [-0.36, -0.35] |
| S2_slow | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.03 [-0.46, +0.47] |
| S2_slow | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.70 [-0.80, -0.59] |
| S2_slow | `forced_A` | 6 | 6 | 6 | 6/6 | +0.40 [-0.16, +0.94] |
| S2_slow | `forced_B` | 6 | 6 | 6 | 6/6 | -0.56 [-0.67, -0.42] |
| S2_slow | `rules_default` | 6 | 6 | 6 | 6/6 | -0.56 [-0.71, -0.43] |
| S2_urgent | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.47 [-0.85, -0.14] |
| S2_urgent | `fixed_priority` | 6 | 6 | 6 | 6/6 | -1.43 [-1.73, -1.16] |
| S2_urgent | `forced_A` | 6 | 6 | 6 | 6/6 | -0.39 [-0.58, -0.25] |
| S2_urgent | `forced_B` | 6 | 6 | 6 | 6/6 | -1.50 [-1.72, -1.29] |
| S2_urgent | `rules_default` | 6 | 6 | 6 | 6/6 | -0.41 [-0.67, -0.16] |
| S4 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.21 [-0.25, -0.16] |
| S4 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.16 [-0.22, -0.09] |
| S4 | `rules_default` | 6 | 6 | 6 | 6/6 | -0.17 [-0.26, -0.09] |
| S4_same_side | `cost_bid` | 4 | 4 | 4 | 4/4 | -0.18 [-0.30, -0.07] |
| S4_same_side | `fixed_priority` | 4 | 4 | 4 | 4/4 | -0.12 [-0.15, -0.10] |
| S4_same_side | `rules_default` | 4 | 4 | 4 | 4/4 | -0.26 [-0.37, -0.15] |
| S7 | `cost_bid_sigma0.5` | 6 | 6 | 6 | 4/6 | +1.28 [-1.33, +5.57] |
| S7 | `cost_bid_sigma1.0` | 6 | 6 | 6 | 3/6 | +3.17 [-0.97, +7.43] |
| S8b | `cost_bid` | 6 | 6 | 6 | 4/6 | -2.95 [-39.27, +26.84] |
| S8b | `fixed_priority` | 6 | 6 | 6 | 5/6 | +8.89 [-1.05, +26.32] |
| S8c_all_off | `cost_bid` | 6 | 6 | 6 | 5/6 | +11.28 [-0.19, +28.34] |
| S8c_all_off | `fixed_priority` | 6 | 6 | 6 | 4/6 | +2.15 [-15.02, +24.09] |
| S9 | `clarke_ABx0.5` | 6 | 6 | 6 | 6/6 | -0.39 [-0.55, -0.27] |
| S9 | `clarke_Ax0.5` | 6 | 6 | 6 | 6/6 | -0.36 [-0.53, -0.24] |
| S9 | `clarke_Bx0.5` | 6 | 6 | 6 | 6/6 | -0.30 [-0.36, -0.25] |
| asym_own | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.39 [-0.42, -0.36] |
| asym_own | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.46 [-0.50, -0.41] |
| asym_share | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.22 [-0.24, -0.18] |
| asym_share | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.22 [-0.28, -0.17] |
| convoy | `group_bid` | 6 | 6 | 6 | 6/6 | -0.28 [-0.34, -0.23] |
| convoy_B_urgent | `fixed_priority` | 6 | 6 | 6 | 6/6 | -1.17 [-1.30, -1.03] |
| convoy_B_urgent | `group_bid` | 6 | 6 | 6 | 6/6 | -1.13 [-1.17, -1.07] |
| explore_all_3.5 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.16 [-0.25, -0.07] |
| explore_all_3.5 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.18 [-0.22, -0.14] |
| explore_all_6.0 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.20 [-0.26, -0.12] |
| explore_all_6.0 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.15 [-0.20, -0.11] |
| explore_det_3.5 | `cost_bid` | 6 | 6 | 6 | 5/6 | +0.08 [-0.19, +0.51] |
| explore_det_3.5 | `fixed_priority` | 6 | 6 | 6 | 6/6 | +6.79 [-0.19, +20.68] |
| explore_det_6.0 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.31 [-0.40, -0.23] |
| explore_det_6.0 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.45 [-0.50, -0.41] |
| explore_full_3.5 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.24 [-0.27, -0.21] |
| explore_full_3.5 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.21 [-0.27, -0.15] |
| explore_none_3.5 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.24 [-0.32, -0.17] |
| explore_none_3.5 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.66 [-1.31, -0.27] |
| explore_none_6.0 | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.37 [-0.41, -0.32] |
| explore_none_6.0 | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.41 [-0.46, -0.38] |
| wrong_map | `cost_bid` | 6 | 6 | 6 | 6/6 | -1.14 [-1.26, -1.05] |
| wrong_map | `fixed_priority` | 6 | 6 | 6 | 6/6 | -1.21 [-1.31, -1.11] |
| wrong_map | `rules_default` | 6 | 6 | 6 | 6/6 | -1.26 [-1.36, -1.14] |

## Batch `main@a276da6`

Negotiating runs: agreement 112/112 = 100.0% (Wilson 95% [96.7, 100.0]); collisions 0/112. Bland–Altman over 118 runs successful in both: bias -5.67 s, limits of agreement [-48.98, +37.64] s.

| group | policy | n | Gazebo success | 2D success | agree | delay Gazebo − 2D, mean [95% CI] (s) |
|---|---|---|---|---|---|---|
| comms | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.49 [-1.52, +0.37] |
| comms | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.49 [-1.80, +0.79] |
| comms | `rules_default` | 6 | 6 | 6 | 6/6 | -0.50 [-1.77, +0.77] |
| convoy | `cost_bid` | 6 | 6 | 6 | 6/6 | -0.23 [-0.27, -0.19] |
| convoy | `fixed_priority` | 6 | 6 | 6 | 6/6 | -0.24 [-0.27, -0.21] |
| convoy | `rules_default` | 6 | 6 | 6 | 6/6 | -0.23 [-0.27, -0.19] |
| corridor | `cost_bid` | 10 | 10 | 10 | 10/10 | -0.27 [-0.33, -0.21] |
| corridor | `fixed_priority` | 10 | 10 | 10 | 10/10 | -0.35 [-0.43, -0.27] |
| corridor | `reactive` | 10 | 6 | 10 | 3/10 | -6.62 [-65.22, +39.98] |
| corridor | `rules_default` | 10 | 10 | 10 | 10/10 | -0.36 [-0.44, -0.28] |
| corridor | `rules_proximity` | 10 | 10 | 10 | 10/10 | -0.35 [-0.44, -0.27] |
| tj | `cost_bid` | 6 | 6 | 6 | 6/6 | -44.15 [-86.50, -22.81] |
| tj | `fixed_priority` | 6 | 6 | 6 | 6/6 | +2.97 [+0.65, +5.18] |
| tj | `rules_default` | 6 | 6 | 6 | 6/6 | -1.76 [-11.07, +4.17] |
| tjgoal | `cost_bid` | 6 | 6 | 6 | 6/6 | -11.13 [-11.38, -10.92] |
| tjgoal | `fixed_priority` | 6 | 6 | 6 | 6/6 | -23.02 [-27.50, -17.32] |
| tjgoal | `rules_default` | 6 | 6 | 6 | 6/6 | -23.41 [-27.49, -18.09] |
