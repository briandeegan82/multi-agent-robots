# Response to the referees — T-ASE, "Who Backs Up? Benchmarking Decentralized Multi-Robot Yield Negotiation in Narrow Corridors"

We thank the three referees for a careful, detailed and constructive review. We checked every comment against the PDF, the code and the per-episode data before responding. We then reran every 2D study on one frozen code version and added the analyses and experiments the referees asked for. The revision rests on the following changes:

- **One code version.** Every 2D number now comes from commit `dfc3d92` (`studies/results_raw/COMMIT`). The 122 Gazebo runs that used an earlier commit were rerun on the final code.
- **Per-episode data for every study.** This now includes the five studies that previously released only aggregates: convoy, T-junction, classifier, asymmetric maps and blocked bays.
- **Number trace.** `studies/report/tase_numbers.csv` traces each number in the manuscript to its source file.
- **New experiments.** These cover the σ robustness of heterogeneous fleets, the fairness credit with held-out λ, Clarke-pivot payments with private types, a randomized-backoff baseline with rulebook-threshold sensitivity, bursty and blackout loss, and Gazebo per-condition confidence intervals.

Referee comments are quoted by the IDs of the merged report: the consolidated issues #1–#13, then R1/R2/R3 with M (major) and m (minor) numbers. Each reply begins with **Accepted**, **Partly accepted** or **Clarified**. Each change is followed by where it lives: the manuscript section, or the repository report under `amr_negotiation/studies/`.

> Status markers for the authors (delete before submission): **[TODO-MS]** = analysis done, manuscript text still to add; **[OPEN]** = not yet done; **[check]** = believed done in the source, not yet re-verified line by line; **[AUTHORS TO CONFIRM]** = a fact only the authors know.

---

## Part A — Consolidated issues

### #1 σ thresholds applied to heterogeneous fleets (R1 M1, R3 M1, R1 m8). Accepted.
We ran the bid-noise study on the heterogeneous S2 design: urgency, payload, maximum speed and bay position all vary. We also densified σ to {0, 0.1, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.75, 1.0} and drew noise independently for each robot.

- **Crossover.** In the heterogeneous fleet, `cost_bid` beats both rulebooks up to σ = 0.35. It is statistically tied with them at σ = 0.4–0.5 (paired stratified-bootstrap CIs) and is worse from σ = 0.75. Fig. 7 now shows the paired difference with its CI at every grid point, instead of an arrow at "σ ≈ 0.5".
- **Systematic planner error (R1 M1.2).** We mis-specified the reverse-speed and turn-rate limits in the planner by ±10/20/30%, both for both robots and for robot B only. This changed excess delay by at most 0.02 s.
- **Manuscript changes.** The abstract, Table VII and the Conclusion now say "σ ≈ 0.5 in a single bay, σ ≈ 0.45 in heterogeneous fleets", with σ ≤ 0.35 as the range where bidding is clearly better (`report_r2/sigma_robustness.md`).
- **Mapping σ to something measurable (R1 M1.4, R1 Q3, R3 practitioner value).** The rerun now logs every predicted bid next to the realized delay, which makes the empirical SD of log(predicted/realized) computable. **[OPEN]** Compute it for sim2d and Gazebo and add one sentence to Sec. VI.

### #2 Novelty overstated; missing prior work (R2 M1, M2, M3, M6, m5, m6, m9; R2 Q1–Q5). Accepted.
- **Comparison table and novelty.** Sec. II has a new table comparing corridor and give-way testbeds: MARLIN, VMAS give_way, Alghamdi & Park 2025 and others. Its columns are refuge/bay model, nonholonomic reversing, asymmetric reverse speed, communication model, strategic agents, policy families and 3D/hardware validation. The novelty is now stated as the combination of features that the table shows is unique. Gap 1 no longer implies that prior work ignores discrete bays.
- **Mechanism design (R2 M2, Q3).** Sec. II now covers VCG for MAPF: Amir et al. 2015, Friedrich et al. 2024 and SocialMAPF. Gautier et al. is now described as combinatorial VCG, and we state what is new relative to it: realized nonholonomic costs and a lossy broadcast channel. **[OPEN]** Add Das et al. 2021 (OMCoRP) and CARMA as related online and karma mechanisms (R2 Q4). We do not add them as baselines, and the revision says why.
- **Rulebooks (R2 M3, Q2).** `rules_default` is now credited to the rulebooks formalism of Censi et al. (ICRA 2019). Sec. IV-B says which tiers follow documented etiquette and which are our own design.
- **Decentralized AGV literature (R2 M6).** Added Čáp et al., Draganjac et al., Digani et al. and Proia et al. Fixed priority is now credited to Čáp et al.
- **Search protocol (R2 m9, Q5). [check]** The universal negative is softened to "to our knowledge", and one sentence gives the databases, years and keywords searched.
- **Bimodal ordering (R2 m6).** **[OPEN]** Add Wenzel et al. (IV 2025).

### #3 Statistics (R1 M6, R3 M5, R1 m3, m5). Accepted; the reanalysis is done (`report/tase_stats.md`, `studies/analyse_tase.py`).
- **Encounter distribution.** It is uniform over the bay grid of each study, with robot B's start delay drawn from U[0, 8] s. The seeds within a grid cell are the replicates.
- **Confidence intervals.**
  - We now report stratified bootstrap CIs (resampling seeds within cells) and paired-difference CIs for every comparison that supports a claim.
  - The pooled CIs in the original submission were *wider*, not narrower, than the stratified CIs. For example, S1 `rules_proximity` was ±0.53 s pooled against [2.99, 3.29] s stratified. The concern was therefore about which population the CI refers to, not about optimistic uncertainty, and the text now names the population.
- **Primary metric.** Δπ now charges each failed episode 180 s per robot, with success-only means as the secondary metric. This matters only for `reactive`: in S1 its excess delay is 86.5 s with failures charged against 70.5 s over successes only. All negotiating policies complete every encounter, so their two values coincide.
  - **[TODO-MS]** Replace "conservative" in Sec. IV-D with "optimistic for policies with failures; primary metric charges failures at the cap".
- **Parity claims.** These now use TOST with a ±0.5 s margin, or are reported as "inconclusive". Example: in S4, `rules_default` − `fixed_priority` is +0.14 s, which is equivalent within ±0.5 s.
- **Multiplicity.** Holm–Bonferroni is applied over the 20 paired comparisons behind Table VII (`report/tase_stats.md`). The S1 and S2 orderings stay significant after correction. Two claims weaken: in S4, `rules_default` − `fixed_priority` is equivalent within ±0.5 s rather than different (Holm p = 0.128), and at S7 σ = 0.5 and 1.0, `cost_bid` vs `rules_proximity` is inconclusive. **[TODO-MS]** Reword these Table VII cells to match.
- **Weighting (R1 m5).** Every Δπ is now marked as unweighted (Δπ^u) or urgency-weighted (Δπ^w).
- **[TODO-MS]** Add a short Statistics paragraph to Sec. IV-D (stratified bootstrap, TOST, Holm, failure imputation) and use these CIs in Tables V–VII.

### #4 Counting errors (R1 m1, R3 M4, m1, m11; R3 Q8). Accepted.
- **Totals and policy count.** The total is now 50,714 episodes everywhere; 50,374 was an arithmetic slip. The abstract and Sec. IV say "nine policies (eight negotiating plus reactive)".
- **S7.** It stored 3,150 rows, of which 1,470 are unique; the σ-independent `rules_proximity` and reference rows were duplicated. N now counts unique episodes.
- **N column.** Table IV gets an "episodes executed" formula column, and forced-reference runs are counted once per draw. **[TODO-MS]** Fill in the formula column for S6, S9, the classifier and convoy.
- **366 shared-draw runs (R3 m11, Q7).** **[TODO-MS]** List the Gazebo groups that make up the 366 runs in the Fig. 15 caption; the per-run table is in `report_r2/gazebo_tase_runs.csv.gz`.

### #5 Fairness credit (R1 M3, R3 M2; R1 Q4). Accepted.
The code did not implement Eq. (10) as printed. Both forms are now implemented and reported (`studies/fairness_credit.py`, `report_r2/fairness_credit.md`):

- **Credit (the code's rule, now printed as Eq. (10)).** It chooses o to minimize d_A(o) + d_B(o) + λ(D_o − D_other). λ is chosen on held-out sequences, which gives λ = 0.1. On fresh sequences, J = 0.992 ± 0.002 at +3.8 ± 0.6% delay with exact delays.
- **Balance (the literal absolute-value form).** The held-out choice is λ = 0.25, giving J = 0.994 at +3.0% delay.
- **Closed loop with noisy delay estimates.** At σ = 0.25, 0.5 and 1.0, the overhead of the credit rule rises to +7.1%, +11.5% and +15.7%. Fig. 10 shows CIs for every λ.
- **Table VII.** "Rulebook + credit" is removed, because a rulebook cannot evaluate d(o). The credit is now paired only with policies that produce delay estimates.
- **[TODO-MS]** Remove the leftover "λ = 0.1 credit where delay estimates exist" from the rulebook row of Table VII, or reword it.

### #6 Reproducibility (R1 M8, m14; R3 M7). Accepted.
- **2D.** Every 2D study was rerun on `dfc3d92` (`studies/run_all_2d.sh` refuses to run on a dirty tree and writes `results_raw/COMMIT`). Every study now releases per-episode data.
- **Gazebo.** The 122 `bf24bf4` runs were rerun on the final code ([PR #44](https://github.com/briandeegan82/multi-agent-robots/pull/44), not yet merged). All 112 negotiating runs chose the same first yielder as before, and makespans changed by at most 1.6 s (`report_r2/gazebo_rerun_compare.md`). Only the stochastic `reactive` runs changed: 4 of 10 failed (1 collision, 3 deadlocks) against 1 of 10 before.
  - The rerun used an ARM64 image built on `ros:jazzy`, because `osrf/ros:jazzy-desktop` is amd64-only. The other 338 runs used amd64. A smoke case reproduced the earlier run exactly.
- **Number trace.** `report/tase_numbers.csv` maps each manuscript number to its file and row.
- **[TODO-MS]** Replace "All reported statistics reflect the final codebase" in Sec. IV-D with the commit hash and a pointer to the README.
- **[OPEN]** Tag a release, archive it on Zenodo, put the DOI in the data statement, and add a parameter/seed appendix with "reproduce Table X" commands (R3 M7).

### #7 Clarke pivot has no private information (R1 M2; R1 Q1; R2 M2). Accepted.
- **Private-information model.** Each robot's urgency u_i is now private and unverifiable, and bids can be misreported per outcome, with b_i(A) and b_i(B) scaled independently (`studies/clarke_private.py`, `report_r2/clarke_private.md`).
- **Result.** In 10,080 episodes, no deviation had a positive gain under the predicted costs. In 89 episodes (0.9%), realized gains exceeded 0.01 s; each came from execution differing from the predicted plan, and the mean realized gain was negative in every arm.
- **Framing.** The 0/108 result is now presented as an implementation check of the VCG property, and the new finding is stated precisely as above.
- **Credit semantics.** Payments are an internal delay-credit ledger settled by the operator, as stated in Secs. V-B and VI.
- **Surplus.** It is now reported against realized delay: 37% and 24% (previously 44% and 29% against predicted cost). The participation loss is 9.3 s.

### #8 Gazebo transfer partly true by construction (R1 M8, R2 m10, R3 m10; R1 Q8). Accepted.
- **Per-condition CIs and Bland–Altman.** We now report agreement and Gazebo − 2D delay with paired CIs for every condition, and a Bland–Altman plot of raw delays (`studies/analyse_gazebo_tase.py`, `report_r2/gazebo_tase.md`).
- **Agreement.** It is 394/406 = 97.0% of negotiating main-batch runs (Wilson 95% CI 94.9–98.3%). The original text counted 393.
- **Delay discrepancies.** The Bland–Altman bias is −1.35 s, with limits of agreement −27.6 to +24.9 s. The wide limits come from the T-junction runs; their bias persists after the rerun on the final code, so it is a real difference between the simulators, not a code-version artefact. Sec. V-D says so and no longer generalizes the "within 1.0 s" result beyond the single-bay and S2 runs it covers.
- **Old-commit disagreements (Q8).** None of the 12 yielder disagreements came from the 122 old-commit runs; that batch agrees 112/112.
- **Wording.** The abstract and conclusion now say "negotiating Gazebo runs with ground-truth localization".
- **Paired noise.** sim2d can now key noise per decision rather than on round(t,1). **[OPEN]** Port this to the ROS agent, so that noisy Gazebo runs pair with 2D. Until then, the text attributes the 5 noisy-bid disagreements to this keying.
- **[TODO-MS]** Add the Bland–Altman figure, or move it to the supplement.

### #9 Zero collisions at 99% loss attributed to snapshots (R1 M7, R2 m10; R1 Q5, Q7). Accepted.
- **C6 reworded.** Collision-freedom comes from the local Lidar stopping and timer layer, as S8c shows.
- **Fallback rate.** At extreme loss, 62.8% of S8b/S8c episodes never reached a negotiated decision and fell back to reactive yielding. The abstract now says robots "often fall back to reactive yielding".
- **New channel models on fresh seeds and unseen parameters** (Gilbert–Elliott bursts and a blackout window; `studies/burst_loss.py`, `report_r2/burst_loss.md`):

| Channel | Episodes | Success | Reached a negotiated decision | Collisions |
|---|---|---|---|---|
| i.i.d. | 480 | 99.4% | 86.7% | 0 |
| Bursty | 1,440 | 99.8% | 71.9% | 0 |
| Blackout | 640 | 100% | 92.5% | 0 |

- **Q7.** The original post-fix S8b runs reused the development seeds. The new runs above use fresh seeds.
- **Not done.** Lidar detection noise and dropout in sim2d (M7.4), and the time-to-resolution distribution of mutual yields (M7.5). We list both as limitations in Sec. VI. **[OPEN]** Time-to-resolution can be computed from the released per-episode events if the editor wants it.

### #10 Convoy row of Table VII (R3 M3, R1 m11; R3 Q1). Accepted.
The Table VII convoy row now recommends `fixed_priority` with `make_room`. The urgency rulebook is the worst policy for an urgent or loaded B, and `fixed_priority` beats `group_bid` when B is urgent. **[TODO-MS]** Tabulate the Fig. 13 values, including `rules_default` (133.6 s urgent, 100.1 s loaded). Give each paired difference separately (R1 m11), and name the B-configuration used for "equal robots" (R3 Q1).

### #11 Citations (R2 M4, M5, m1–m4, m7, m8). Accepted.
- **SocNavBench.** Now attributed to Biswas et al. 2022.
- **Mechanism-design sources.** Myerson–Satterthwaite, Vickrey and Groves are added.
- **Dresner & Stone.** Now described as reservation-based.
- **Robotaxi news items [14]–[17].** Retained only as anecdotes, and the "public trust" sentence is softened (R3 m21).
- **Over-cited and preprint sources.** References cited too broadly (MAPPO, BARN, [10]) now support only the specific sentences they back. The arXiv-only sources are marked as preprints, and published versions are used where they exist.
- **Bibliographic details.** Years and volumes are corrected against Crossref, and the dead link [4] is replaced. Every scholarly entry now carries a DOI, and the Jain report cites its 1984 DEC-TR-301 origin.
- **[OPEN]**
  - Credit the photographer and CC BY-SA 2.0 licence in the Fig. 1 caption, and confirm reuse permission for the Dematic image (R2 m8).
  - Justify the self-citation [28] with a specific pointer (R2 m7).

### #12 Baselines (R1 M4, M5; R2 m5; R3 m7; R1 Q2). Accepted.
- **Randomized exponential backoff (`backoff`).** It is a stronger communication-free baseline: patience is drawn from U[0, base·2^min(k,5)]. It completes more encounters than `reactive` but is not faster:

| Study | Policy | Success | Excess delay (s) |
|---|---|---|---|
| S1 | `reactive` | 93.8% | 86.5 ± 7.3 |
| S1 | `backoff` | 96.7% | 92.3 ± 6.3 |
| S1 | `fixed_priority` | 100% | 6.5 ± 0.6 |
| S4 | `reactive` | 97.8% | 72.0 ± 6.2 |
| S4 | `backoff` | 100% | 59.1 ± 4.0 |
| S4 | `fixed_priority` | 100% | 1.1 ± 0.3 |

  The conclusion that communication is needed is now scoped to "this reactive design and randomized backoff". We did not add ORCA/CBF, and Sec. VI says why.
- **Rulebook thresholds.** One-at-a-time sensitivity on S1, S2 and S4 (`report_r2/baselines_r3.md`) shows that only the urgency threshold matters. At a threshold of 2.5, S2 excess delay rises to 15.7 s for `rules_default` and 9.1 s for `rules_proximity`.
  - **Q2. [AUTHORS TO CONFIRM]** State whether the thresholds and the reactive patience interval were set before the benchmark runs, and the tuning effort for each family. **[TODO-MS]** Add this to Sec. IV-B.
- **Reservation off the exit path.** We tried it, but moving the end-room parking spot 1.2 m or more into the room made every episode deadlock: the parked robot cannot leave under the current leave manoeuvre. Testing this fairly needs a different leave manoeuvre, so we report it as a limitation rather than a result.
- **Learned baseline.** Renamed "tabular full-information outcome classifier" throughout. We dropped the generalization conclusion and keep it as an illustration.
  - **[TODO-MS]** Add CIs, the error on seen versus unseen keys, and the training/evaluation distributions (R1 M5.2–3). Drop the "≥ 200 encounters" plateau claim, or add the learning curve to the supplement (R3 m7).

### #13 T-ASE format (R3 M6, m17). Partly done.
- **Abstract.** Rewritten to 198 words, ending with a full stop.
- **[OPEN]** The manuscript is 21 pages. Move S8/S8b, explore/hold and the classifier details to a supplement, remove repeated numbers, and enlarge the figure text to at least 8 pt (Figs. 2b, 3a, 4; R3 m17).

---

## Part B — Issues raised in the review's footnote and appendices

- **"113 s (4.2×)" not reproducible (R1 Q2 / R3 A7). Clarified.** It reproduces: charging each of the 26 deadlocked S1 encounters 2 × 180 s gives a mean reactive total delay of 113.4 s, which is 4.22× the 26.8 s reference. It is not makespan. The derivation is stated in Sec. V-A. The frozen rerun gives 3.41× against `fixed_priority` (`report/tase_stats.md`).
- **Lost superscripts (R1 m7). Clarified.** The PDF typesets 0.9⁵ and 2³ correctly; the missing superscripts are an artefact of extracting the PDF text.
- **Wilson vs Clopper–Pearson (R1 m2, R3 M5). Accepted.** The zero-event bounds are now labelled Wilson (1.06% for n = 360, 0.85% for n = 450), with Clopper–Pearson given alongside in the statistics report.
- **S8c freshness reasoning (R3 M5, R3 Q3). Accepted. [TODO-MS]** Make the Sec. V-C explanation consistent with how the code times STATE freshness (from receipt or from sending), and replace "conservative" (see #3).
- **Two-agent Jain range (R1 m12, R3 m8). Accepted. [TODO-MS]** State J ∈ [0.5, 1] for two robots and that J is computed per sequence and then averaged. Also report the cumulative-delay gap |D_A − D_B| in seconds.
- **Fig. 7 reference lines (R3 m6). Accepted. [TODO-MS]** Label each line with its source study.
- **Study numbering (R3 m15). [TODO-MS]** Number all studies consecutively (the new robustness studies are S11a/S11b, and S5 is currently missing).
- **Policy names (R3 m23). [TODO-MS]** Use one plain name per policy, with the code name given once in Table II.
- **Missed by the referees: two-bay S4.** `rules_proximity` has the highest excess delay of the negotiating policies in S4: 5.61 s, against 1.10 s for `fixed_priority` and 0.00 s for `cost_bid`. The abstract, NtP and Table VII now say that the closest-refuge rulebook is competitive only with a single bay.
- **Missed by the referees: proximity rulebook file.** `proximity_first.yaml` lacked the payload rule that the text describes. It has been added, and all 2D studies were rerun with it.

---

## Part C — Reviewer 1, items not covered above

- **m4 (hindsight reference is not an optimum). Accepted. [TODO-MS]** In Eq. (11), call it the "better forced-yielder reference". State that it fixes r* from the planner and that negative Δ is possible.
- **m6 (S6 vs S9 asymmetry). Accepted. [TODO-MS]** Add one sentence explaining it by role, bay position and u_B (B gains about 1 s from inflating its bid in S6, while A gains 4.74 s in S9).
- **m9 (noise seeded by round(t,1)). Accepted. [TODO-MS]** State the assumption. See #1 for the per-robot noise used in the new σ study.
- **m10 (convoy and T-junction seeds). Accepted. [TODO-MS]** Report n per cell and note that the CIs pool the designed cells.
- **m13 (collusion incentive figure). Accepted. [TODO-MS]** Quote the range in Table VII, as Sec. V-B already does: +4.94 s at k = 0.5 and +7.42 s at k = 0.25.
- **Q6 (dropped encounters). Clarified.** Every negotiating policy completes every encounter in S1, S2 and S4, so no negotiating encounter is dropped from Δπ. `reactive` loses 26 encounters in S1, 60 in S2 and 8 in S4; these are now charged at the cap.

## Part D — Reviewer 2, items not covered above

- **m2 ([15] title).** We keep the corrected title and add the access date.
- **m3 ([64] Jain).** Cited as DEC-TR-301 (1984), with the 1998 arXiv version noted as a repost.
- **m10 (abstract vs results).** Each claim in the abstract is now scoped; see #1, #8 and #9.
- **Q6 (AGV deadlock evidence). [OPEN]** We have not found peer-reviewed incident data. The news items are kept as anecdotes, as noted in #11.
- **Q7 (published versions of [38] and [40]).** Updated where a published version exists.

## Part E — Reviewer 3, items not covered above

- **m2 (NtP equal-priority sentence). Accepted. [TODO-MS, check]** Make sure it says that rules match bidding only once bid error reaches σ ≈ 0.5. Also say in the NtP that all results come from simulation with ground-truth pose.
- **m3 (Table VII σ header). Accepted. [TODO-MS, check]** Make it read "σ ≥ 0.5: parity; σ = 1.0: rulebook better".
- **m4 (+4.9 s ambiguity).** See R1 m13.
- **m5 (`commit` optional vs asymmetric maps). Accepted.** We added an asymmetric-map arm with `commit` off (R3 Q6). **[TODO-MS]** Report its result in Sec. V-C and reconcile it with Lesson 1.
- **m9 (Gazebo denominators). [TODO-MS]** Give n for each fraction.
- **m10 (96.8% scope). Accepted.** The figure is now 97.0% of 406 negotiating main-batch runs, in the abstract and the conclusion.
- **m12 (collision definition). [TODO-MS]** Define the collision as Waffle footprint-rectangle overlap. State that the 0.50 m Lidar stop margin is a controller threshold, not part of the collision metric.
- **m13 (D equation and metric names). [TODO-MS]** Number the D equation and use one name per quantity in the figure axes.
- **m14 (roadmap). [TODO-MS]** Fix the section roadmap in Sec. I.
- **m16 (topologies). Accepted. [TODO-MS]** Say "five geometries, six scenarios".
- **m18–m20 (wording). Accepted. [TODO-MS, check]** Write "lose up to 3.3 ± 1.0 s", explain the two `fixed_priority` values by their different draws, and make the T-junction sentence compare policies rather than implying a before/after change.
- **m22 (10 m corridor). [TODO-MS]** Map the corridor length to each study in Table IV.
- **Practitioner value: message budget. [OPEN]** Report the median message count per episode, which the released data logs as `msgs`.
- **Practitioner value: more than two robots.** Out of scope beyond the two topologies tested, as stated in Sec. VI.
- **Practitioner value: using the VCG surplus.** Sec. VI now says that the surplus stays in the operator's ledger, and lists redistribution as future work.
