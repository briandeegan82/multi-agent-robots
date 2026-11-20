1800 episodes -> /home/ubuntu/repos/multi-agent-robots/amr_negotiation/studies/results_raw/explore_map.csv.gz

| map | policy | loss | detect range [m] | success | deadlock | collision | mean delay [s] | extra vs full, mean ± 95% CI [s] | map shared before decision | time to decision [s] | hold timeouts |
|---|---|---|---|---|---|---|---|---|---|---|---|
| full | fixed_priority | 0% | 6.0 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | – | 0.1 | 0 |
| full | fixed_priority | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | – | 0.1 | 0 |
| full | fixed_priority | 50% | 6.0 | 30/30 | 0 | 0 | 23.6 | +0.0 ± 0.0 | – | 0.3 | 0 |
| full | fixed_priority | 50% | 3.5 | 30/30 | 0 | 0 | 23.3 | +0.0 ± 0.0 | – | 0.2 | 0 |
| full | rules_default | 0% | 6.0 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | – | 0.1 | 0 |
| full | rules_default | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | – | 0.1 | 0 |
| full | rules_default | 50% | 6.0 | 30/30 | 0 | 0 | 23.6 | +0.0 ± 0.0 | – | 0.3 | 0 |
| full | rules_default | 50% | 3.5 | 30/30 | 0 | 0 | 23.3 | +0.0 ± 0.0 | – | 0.2 | 0 |
| full | cost_bid | 0% | 6.0 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | – | 0.1 | 0 |
| full | cost_bid | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | – | 0.1 | 0 |
| full | cost_bid | 50% | 6.0 | 30/30 | 0 | 0 | 23.6 | +0.0 ± 0.0 | – | 0.3 | 0 |
| full | cost_bid | 50% | 3.5 | 30/30 | 0 | 0 | 23.3 | +0.0 ± 0.0 | – | 0.2 | 0 |
| explore_no_share | fixed_priority | 0% | 6.0 | 30/30 | 0 | 0 | 51.3 | +29.2 ± 1.8 | – | 0.1 | 0 |
| explore_no_share | fixed_priority | 0% | 3.5 | 30/30 | 0 | 0 | 27.9 | +5.8 ± 5.4 | – | 0.1 | 0 |
| explore_no_share | fixed_priority | 50% | 6.0 | 30/30 | 0 | 0 | 52.6 | +29.0 ± 1.9 | – | 0.3 | 0 |
| explore_no_share | fixed_priority | 50% | 3.5 | 30/30 | 0 | 0 | 27.8 | +4.5 ± 4.9 | – | 0.2 | 0 |
| explore_no_share | rules_default | 0% | 6.0 | 30/30 | 0 | 0 | 51.3 | +29.2 ± 1.8 | – | 0.1 | 0 |
| explore_no_share | rules_default | 0% | 3.5 | 30/30 | 0 | 0 | 25.1 | +3.0 ± 3.9 | – | 0.1 | 0 |
| explore_no_share | rules_default | 50% | 6.0 | 30/30 | 0 | 0 | 52.6 | +29.0 ± 1.9 | – | 0.3 | 0 |
| explore_no_share | rules_default | 50% | 3.5 | 30/30 | 0 | 0 | 25.0 | +1.7 ± 3.0 | – | 0.2 | 0 |
| explore_no_share | cost_bid | 0% | 6.0 | 30/30 | 0 | 0 | 30.9 | +8.8 ± 1.6 | – | 0.1 | 0 |
| explore_no_share | cost_bid | 0% | 3.5 | 30/30 | 0 | 0 | 22.3 | +0.2 ± 0.2 | – | 0.1 | 0 |
| explore_no_share | cost_bid | 50% | 6.0 | 30/30 | 0 | 0 | 32.3 | +8.7 ± 1.7 | – | 0.3 | 0 |
| explore_no_share | cost_bid | 50% | 3.5 | 30/30 | 0 | 0 | 23.6 | +0.3 ± 0.4 | – | 0.2 | 0 |
| explore_share_always | fixed_priority | 0% | 6.0 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_always | fixed_priority | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_always | fixed_priority | 50% | 6.0 | 30/30 | 0 | 0 | 23.6 | +0.0 ± 0.0 | 30/30 | 0.3 | 0 |
| explore_share_always | fixed_priority | 50% | 3.5 | 30/30 | 0 | 0 | 23.3 | +0.0 ± 0.0 | 24/30 | 0.2 | 0 |
| explore_share_always | rules_default | 0% | 6.0 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_always | rules_default | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_always | rules_default | 50% | 6.0 | 30/30 | 0 | 0 | 23.6 | +0.0 ± 0.0 | 30/30 | 0.3 | 0 |
| explore_share_always | rules_default | 50% | 3.5 | 30/30 | 0 | 0 | 23.3 | +0.0 ± 0.0 | 24/30 | 0.2 | 0 |
| explore_share_always | cost_bid | 0% | 6.0 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_always | cost_bid | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_always | cost_bid | 50% | 6.0 | 30/30 | 0 | 0 | 23.6 | +0.0 ± 0.0 | 30/30 | 0.3 | 0 |
| explore_share_always | cost_bid | 50% | 3.5 | 30/30 | 0 | 0 | 23.3 | +0.0 ± 0.0 | 24/30 | 0.2 | 0 |
| explore_share_on_detect | fixed_priority | 0% | 6.0 | 30/30 | 0 | 0 | 51.3 | +29.2 ± 1.8 | 0/30 | 0.1 | 0 |
| explore_share_on_detect | fixed_priority | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_on_detect | fixed_priority | 50% | 6.0 | 30/30 | 0 | 0 | 52.6 | +29.0 ± 1.9 | 0/30 | 0.3 | 0 |
| explore_share_on_detect | fixed_priority | 50% | 3.5 | 30/30 | 0 | 0 | 25.0 | +1.7 ± 3.2 | 24/30 | 0.2 | 0 |
| explore_share_on_detect | rules_default | 0% | 6.0 | 30/30 | 0 | 0 | 51.3 | +29.2 ± 1.8 | 0/30 | 0.1 | 0 |
| explore_share_on_detect | rules_default | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_on_detect | rules_default | 50% | 6.0 | 30/30 | 0 | 0 | 52.6 | +29.0 ± 1.9 | 0/30 | 0.3 | 0 |
| explore_share_on_detect | rules_default | 50% | 3.5 | 30/30 | 0 | 0 | 25.0 | +1.7 ± 3.2 | 24/30 | 0.2 | 0 |
| explore_share_on_detect | cost_bid | 0% | 6.0 | 30/30 | 0 | 0 | 30.9 | +8.8 ± 1.6 | 0/30 | 0.1 | 0 |
| explore_share_on_detect | cost_bid | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_on_detect | cost_bid | 50% | 6.0 | 30/30 | 0 | 0 | 32.3 | +8.7 ± 1.7 | 0/30 | 0.3 | 0 |
| explore_share_on_detect | cost_bid | 50% | 3.5 | 30/30 | 0 | 0 | 23.6 | +0.3 ± 0.6 | 24/30 | 0.2 | 0 |
| explore_share_on_detect_hold | fixed_priority | 0% | 6.0 | 30/30 | 0 | 0 | 21.7 | -0.4 ± 0.0 | 30/30 | 4.9 | 0 |
| explore_share_on_detect_hold | fixed_priority | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_on_detect_hold | fixed_priority | 50% | 6.0 | 30/30 | 0 | 0 | 23.1 | -0.5 ± 0.5 | 19/30 | 5.5 | 0 |
| explore_share_on_detect_hold | fixed_priority | 50% | 3.5 | 30/30 | 0 | 0 | 23.5 | +0.1 ± 0.4 | 24/30 | 0.2 | 0 |
| explore_share_on_detect_hold | rules_default | 0% | 6.0 | 30/30 | 0 | 0 | 21.7 | -0.4 ± 0.0 | 30/30 | 4.9 | 0 |
| explore_share_on_detect_hold | rules_default | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_on_detect_hold | rules_default | 50% | 6.0 | 30/30 | 0 | 0 | 23.1 | -0.4 ± 0.5 | 19/30 | 5.5 | 0 |
| explore_share_on_detect_hold | rules_default | 50% | 3.5 | 30/30 | 0 | 0 | 23.5 | +0.1 ± 0.4 | 24/30 | 0.2 | 0 |
| explore_share_on_detect_hold | cost_bid | 0% | 6.0 | 30/30 | 0 | 0 | 21.7 | -0.4 ± 0.0 | 30/30 | 4.9 | 0 |
| explore_share_on_detect_hold | cost_bid | 0% | 3.5 | 30/30 | 0 | 0 | 22.1 | +0.0 ± 0.0 | 30/30 | 0.1 | 0 |
| explore_share_on_detect_hold | cost_bid | 50% | 6.0 | 30/30 | 0 | 0 | 23.1 | -0.5 ± 0.5 | 19/30 | 5.5 | 0 |
| explore_share_on_detect_hold | cost_bid | 50% | 3.5 | 30/30 | 0 | 0 | 23.5 | +0.1 ± 0.4 | 24/30 | 0.2 | 0 |

collisions per map: {'full': 0, 'explore_no_share': 0, 'explore_share_always': 0, 'explore_share_on_detect': 0, 'explore_share_on_detect_hold': 0}
