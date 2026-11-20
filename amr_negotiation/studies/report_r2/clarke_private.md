# Clarke pivot with private types (WP5)

python studies/clarke_private.py [OUT_DIR]   # -> OUT_DIR/S9b_clarke_private.csv, studies/report_r2/clarke_private.md

Successful deviating episodes: 10080 of 10080. Gain > 0 means the deviation paid off; "profitable" counts gains above 0.01 s.

| arm | deviator | u_B | N | predicted gain: mean | max | profitable | realized gain: mean ± 95% CI | profitable | outcome changed |
|---|---|---|---|---|---|---|---|---|---|
| scale2 | A | 1 | 2160 | -1.373 | +0.000 | 0 | -1.04 ± 0.14 | 68 | 15% |
| scale2 | A | 3 | 2160 | -0.008 | +0.000 | 0 | -0.01 ± 0.01 | 0 | 0% |
| scale2 | B | 1 | 2160 | -1.642 | +0.000 | 0 | -1.80 ± 0.19 | 0 | 17% |
| scale2 | B | 3 | 2160 | -1.608 | +0.000 | 0 | -1.23 ± 0.17 | 0 | 16% |
| urgency | A | 1 | 360 | -2.986 | +0.000 | 0 | -2.26 ± 0.48 | 21 | 31% |
| urgency | A | 3 | 360 | -5.359 | +0.000 | 0 | -5.18 ± 2.13 | 0 | 8% |
| urgency | B | 1 | 360 | -0.894 | +0.000 | 0 | -1.11 ± 0.41 | 0 | 9% |
| urgency | B | 3 | 360 | -6.400 | +0.000 | 0 | -7.05 ± 2.58 | 0 | 9% |
