# T-ASE statistics (WP2)

Data: `results_raw/` produced at commit `dfc3d92
# simulation code; analysis re-run at 966ce34 (analyse_helpers key-column fix only)`.


- Excess delay Δπ is computed per draw (grid cell × seed) against the best forced yielder on the same draw
  (`oracle`, or `oracle_w` for urgency-weighted delay).
- Primary metric: failed episodes are charged n_robots × t_max (180 s each), so deadlocks count against a policy.
  Secondary: success-only means (the convention of analyse.py).
- CIs: 95% percentile bootstrap (2,000 resamples) that resamples seeds within each grid cell (stratified), and the
  normal-approximation CI over all draws (pooled), shown side by side.
- Parity: two one-sided tests (TOST) against ±0.5 s on the paired per-draw differences; "equivalent" if both
  one-sided p < 0.05, otherwise "inconclusive" unless the paired difference is significant.
- Holm–Bonferroni over the family of paired comparisons that back Table VII.
- Rates: Wilson 95% intervals, and the exact Clopper–Pearson upper bound for zero counts.
- S7: `rules_proximity` and `oracle` do not depend on σ, so their rows are deduplicated before counting N.

## S1 single bay: excess delay vs best forced yielder [s]

| policy | N | Δπ imputed, mean | pooled ±CI | stratified bootstrap 95% CI | Δπ success-only | success [Wilson 95%] |
|---|---|---|---|---|---|---|
| `reactive` | 420 | 86.52 | ±7.29 | [79.78, 93.58] | 70.54 ± 4.48 | 93.8% [91.1, 95.7] |
| `fixed_priority` | 420 | 6.45 | ±0.64 | [6.21, 6.67] | 6.45 ± 0.64 | 100.0% [99.1, 100.0] |
| `rules_default` | 420 | 6.45 | ±0.64 | [6.22, 6.68] | 6.45 ± 0.64 | 100.0% [99.1, 100.0] |
| `rules_proximity` | 420 | 3.14 | ±0.53 | [2.99, 3.29] | 3.14 ± 0.53 | 100.0% [99.1, 100.0] |
| `cost_bid` | 420 | 0.00 | ±0.00 | [0.00, 0.00] | 0.00 ± 0.00 | 100.0% [99.1, 100.0] |

Reactive deadlocks: 26/420 (6.2%). Negotiating policies: 0 failures; Clopper–Pearson 97.5% upper bound 0.87% (Wilson 0.91%).
Reactive / fixed-priority mean total delay: 2.92× (successes), 3.41× (deadlocks charged 2 × 180 s; reactive mean 113.4 s).

## S2 heterogeneous robots: urgency-weighted excess delay [s]

| policy | N | Δπ imputed, mean | pooled ±CI | stratified bootstrap 95% CI | Δπ success-only | success [Wilson 95%] |
|---|---|---|---|---|---|---|
| `reactive` | 720 | 110.84 | ±7.18 | [104.13, 117.42] | 91.88 ± 6.01 | 91.7% [89.4, 93.5] |
| `fixed_priority` | 720 | 27.08 | ±2.60 | [26.43, 27.78] | 27.08 ± 2.60 | 100.0% [99.5, 100.0] |
| `rules_default` | 720 | 3.53 | ±0.41 | [3.39, 3.66] | 3.53 ± 0.41 | 100.0% [99.5, 100.0] |
| `rules_proximity` | 720 | 3.56 | ±0.42 | [3.41, 3.71] | 3.56 ± 0.42 | 100.0% [99.5, 100.0] |
| `cost_bid` | 720 | 0.04 | ±0.02 | [0.02, 0.06] | 0.04 ± 0.02 | 100.0% [99.5, 100.0] |

## S4 two bays: excess delay [s]

| policy | N | Δπ imputed, mean | pooled ±CI | stratified bootstrap 95% CI | Δπ success-only | success [Wilson 95%] |
|---|---|---|---|---|---|---|
| `reactive` | 360 | 72.00 | ±6.23 | [66.33, 78.41] | 66.11 ± 4.84 | 97.8% [95.7, 98.9] |
| `fixed_priority` | 360 | 1.10 | ±0.30 | [0.90, 1.31] | 1.10 ± 0.30 | 100.0% [98.9, 100.0] |
| `rules_default` | 360 | 1.24 | ±0.32 | [1.00, 1.48] | 1.24 ± 0.32 | 100.0% [98.9, 100.0] |
| `rules_proximity` | 360 | 5.61 | ±0.52 | [5.31, 5.95] | 5.61 ± 0.52 | 100.0% [98.9, 100.0] |
| `cost_bid` | 360 | 0.00 | ±0.00 | [0.00, 0.00] | 0.00 ± 0.00 | 100.0% [98.9, 100.0] |

## S7 bid noise (single bay)

Rows: 3150 stored, 1470 unique (σ-independent `rules_proximity`/`oracle` rows deduplicated).

| σ | cost_bid Δπ | stratified 95% CI | cost_bid − rules_proximity (paired) | 95% CI | p | TOST ±0.5 s p |
|---|---|---|---|---|---|---|
| 0.0 | 0.00 | [0.00, 0.00] | -3.15 | [-3.36, -2.93] | 0.000 | 1.000 |
| 0.1 | 0.15 | [0.03, 0.31] | -3.00 | [-3.26, -2.72] | 0.000 | 1.000 |
| 0.25 | 1.45 | [0.93, 2.06] | -1.70 | [-2.26, -1.08] | 0.001 | 0.993 |
| 0.5 | 3.30 | [2.50, 4.16] | +0.15 | [-0.65, +1.03] | 0.802 | 0.277 |
| 1.0 | 4.48 | [3.60, 5.40] | +1.33 | [+0.43, +2.21] | 0.032 | 0.910 |

## Paired comparisons behind Table VII (Holm over 20 tests)

| study | A − B | N | mean | stratified 95% CI | p | Holm p | TOST p | verdict |
|---|---|---|---|---|---|---|---|---|
| S1_baseline | `cost_bid` − `fixed_priority` | 420 | -6.45 | [-6.67, -6.21] | 1.71e-62 | 2.56e-61 | 1 | different |
| S1_baseline | `reactive` − `fixed_priority` | 420 | +80.07 | [+73.22, +87.36] | 1.07e-68 | 1.82e-67 | 1 | different |
| S1_baseline | `rules_default` − `fixed_priority` | 420 | +0.00 | [+0.00, +0.00] | nan | 1 | 0 | equivalent (±0.5 s) |
| S1_baseline | `rules_proximity` − `cost_bid` | 420 | +3.14 | [+2.99, +3.29] | 4.15e-27 | 3.74e-26 | 1 | different |
| S1_baseline | `rules_proximity` − `fixed_priority` | 420 | -3.30 | [-3.51, -3.12] | 3.21e-27 | 3.21e-26 | 1 | different |
| S2_asymmetry | `cost_bid` − `fixed_priority` | 720 | -27.05 | [-27.73, -26.37] | 3.09e-73 | 5.86e-72 | 1 | different |
| S2_asymmetry | `reactive` − `fixed_priority` | 720 | +83.76 | [+77.23, +90.48] | 5.98e-90 | 1.2e-88 | 1 | different |
| S2_asymmetry | `rules_default` − `fixed_priority` | 720 | -23.56 | [-24.22, -22.92] | 2.37e-52 | 3.32e-51 | 1 | different |
| S2_asymmetry | `rules_proximity` − `cost_bid` | 720 | +3.52 | [+3.37, +3.67] | 1.4e-51 | 1.68e-50 | 1 | different |
| S2_asymmetry | `rules_proximity` − `fixed_priority` | 720 | -23.53 | [-24.21, -22.89] | 1.16e-51 | 1.51e-50 | 1 | different |
| S4_two_bays | `cost_bid` − `fixed_priority` | 360 | -1.10 | [-1.32, -0.89] | 3.46e-12 | 2.07e-11 | 1 | different |
| S4_two_bays | `reactive` − `fixed_priority` | 360 | +70.90 | [+65.27, +76.98] | 5.66e-70 | 1.02e-68 | 1 | different |
| S4_two_bays | `rules_default` − `fixed_priority` | 360 | +0.14 | [+0.03, +0.28] | 0.0333 | 0.128 | 3.19e-08 | equivalent (±0.5 s) |
| S4_two_bays | `rules_proximity` − `cost_bid` | 360 | +5.61 | [+5.29, +5.94] | 1.26e-65 | 2.02e-64 | 1 | different |
| S4_two_bays | `rules_proximity` − `fixed_priority` | 360 | +4.51 | [+4.20, +4.81] | 3.51e-46 | 3.86e-45 | 1 | different |
| S7 σ=0.0 | `cost_bid` − `rules_proximity` | 210 | -3.15 | [-3.36, -2.93] | 2.85e-14 | 2.28e-13 | 1 | different |
| S7 σ=0.1 | `cost_bid` − `rules_proximity` | 210 | -3.00 | [-3.26, -2.72] | 1.51e-12 | 1.06e-11 | 1 | different |
| S7 σ=0.25 | `cost_bid` − `rules_proximity` | 210 | -1.70 | [-2.26, -1.08] | 0.000599 | 0.003 | 0.993 | different |
| S7 σ=0.5 | `cost_bid` − `rules_proximity` | 210 | +0.15 | [-0.65, +1.03] | 0.802 | 1 | 0.277 | inconclusive |
| S7 σ=1.0 | `cost_bid` − `rules_proximity` | 210 | +1.33 | [+0.43, +2.21] | 0.032 | 0.128 | 0.91 | inconclusive |

## Episode counts

| file | rows |
|---|---|
| `S10_encounters.csv.gz` | 1000 |
| `S10_repeated.csv.gz` | 350 |
| `S1_baseline.csv.gz` | 2940 |
| `S2_asymmetry.csv.gz` | 5040 |
| `S3_comms.csv.gz` | 3600 |
| `S4_two_bays.csv.gz` | 2520 |
| `S6_misreport.csv.gz` | 1080 |
| `S7_noisy_bids.csv.gz` | 3150 |
| `S8_comms_stress.csv.gz` | 4320 |
| `S8b_comms_extreme.csv.gz` | 1440 |
| `S8c_protocol_ablation.csv.gz` | 5760 |
| `S9_payments.csv.gz` | 10080 |
| `asym_map.csv.gz` | 1680 |
| `convoy_group.csv.gz` | 1080 |
| `explore_map.csv.gz` | 1800 |
| `learned_eval.csv.gz` | 900 |
| `reservation.csv.gz` | 1260 |
| `tjunction_goal.csv.gz` | 768 |
| `wrong_map.csv.gz` | 320 |
| **total** | 49088 |
