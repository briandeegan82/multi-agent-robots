# Response to the referees — T-ASE, "Who Backs Up? Benchmarking Decentralized Multi-Robot Yield Negotiation in Narrow Corridors"

We thank the three referees for a careful, detailed and constructive review. We checked every comment against the PDF, the code and the per-episode data. We then reran every 2D study on one frozen code version, added the analyses and experiments the referees asked for, and rewrote the paper to 14 pages, with a supplement holding the extended results.

The revised manuscript is `amr_negotiation/paper_tase_rev/main.tex`, and the supplement is `supplement.tex` in the same folder. Section, table, figure and equation numbers below refer to the revised version; the supplement uses an "S" prefix.

The revision rests on four changes:

- **One code version.** Every 2D number comes from commit `dfc3d92` (`studies/results_raw/COMMIT`). The 122 Gazebo runs that used an earlier commit were rerun on the final code.
- **Per-episode data for every study.** This includes the five studies that previously released only aggregates. `studies/report/tase_numbers.csv` traces each number in the paper to its source file and row.
- **Eight revision studies (72,310 episodes).** They cover:
  - σ robustness in heterogeneous fleets and planner mis-specification (S7d, S7h, S7m);
  - correlated packet loss (S8d);
  - Clarke-pivot payments with private types (S9b);
  - fresh fairness sequences (S10b);
  - baseline strength checks (S11a, S11b).
- **Corrected statistics.** These include stratified and paired CIs, failure-charged delay, TOST for parity claims, Holm correction, and Wilson bounds.

Comments are cited by the IDs of the merged report: the consolidated issues #1–#13, then R1/R2/R3 with M (major) and m (minor) numbers.

> Notes for the authors (delete before submission): **[OPEN]** marks the items still to do before resubmission; **[AUTHORS]** marks a fact only the authors can confirm.

---

## Part A — Consolidated issues

### #1 σ thresholds applied to heterogeneous fleets (R1 M1, R3 M1, R1 m8). Accepted.
- **New noise studies.** We reran the bid-noise study with σ ∈ {0, 0.1, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.75, 1.0}, drawing noise independently for each robot. S7d uses the single-bay grid, and S7h uses the heterogeneous S2 grid, where urgency, payload, speed and bay position all vary.
- **Table IV** replaces the old crossover arrow. It gives the paired difference with a bootstrap CI at every σ:
  - **Single bay:** `cost_bid` is better than `rules_proximity` up to σ = 0.3, tied at 0.35–0.45, and worse from 0.5.
  - **Heterogeneous fleet:** it beats both rulebooks up to σ = 0.35, is tied at 0.4–0.5, and is worse from 0.75.
  - The original five-point S7 grid is now Fig. S1.
- **Systematic error (R1 M1.2).** S7m mis-specifies the planner's reverse-speed and turn-rate limits by ±10/20/30%, for robot B only or for both robots. This raised `cost_bid` excess delay by at most 0.2 s (Sec. V-A).
- **Mapping σ to a measurable quantity (R1 M1.4, Q3).** In 2D, the SD of log(predicted/realized) is 0.075 in S1 and 0.068 in S2. Predicted delay also has a common bias of −15%, which cancels when the two outcomes are compared. The measured error therefore lies well inside the range where bidding wins (Sec. V-A and Table VI).
  - **Gazebo estimate.** Every Gazebo decision already logs the planner's predicted plan. On the 72 nominal-communication, correct-map two-robot `cost_bid`/`clarke` runs, the SD of log(predicted/realized weighted delay) is 0.095 in Gazebo against 0.098 in 2D on the same runs (Sec. V-A; `studies/gazebo_bid_error.py`). Hardware error is still untested (Sec. VI).
- **Wording.** The abstract, Table VI and the Conclusion now give the new thresholds: σ = 0.3 in a single bay and 0.35 in heterogeneous fleets. They also say the crossovers should not be carried over to layouts with several bays.

### #2 Novelty overstated; missing prior work (R2 M1–M3, M6, m5, m6, m9; R2 Q1–Q5). Accepted.
- **Comparison table and novelty.** Table I compares the corridor and give-way testbeds: MARLIN, VMAS give_way, Alghamdi & Park, MAPF corridor work and VCG for MAPF. The novelty is now stated as the combination of features shown in the table, and gap 1 (Sec. I) no longer implies that prior work ignores bays.
- **Search protocol (R2 m9, Q5).** Sec. II states the databases, years and keywords searched, and the universal negative now reads "to our knowledge".
- **Mechanism design (R2 M2, Q3, Q4).**
  - Sec. II now covers Amir et al., Friedrich et al., SocialMAPF, OMCoRP (Das et al.), Gautier et al., CARMA and the Myerson–Satterthwaite impossibility result.
  - What is new relative to these works is the cost of reversing into a refuge and a lossy broadcast channel.
  - OMCoRP and CARMA are discussed rather than run as baselines. They address online multi-encounter prioritization, which our single-encounter VCG study does not attempt.
- **Rulebooks (R2 M3, Q2).** `rules_default` and `rules_proximity` are now presented as rulebooks in the sense of Censi et al. (2019). Their tiers follow the etiquette sources, while the thresholds and the ordering of the proximity variant are our own design (Sec. IV-B).
- **Decentralized AGV literature (R2 M6).** We added Čáp et al. (prioritized planning, now credited for `fixed_priority`), Draganjac et al., Digani et al. and Proia et al.
- **Wenzel et al. (R2 m6).** Added to Sec. II with the IV 2025 reference (doi:10.1109/IV64158.2025.11097760).

### #3 Statistics (R1 M6, R3 M5, R1 m3, m5). Accepted (Sec. IV-D, `studies/analyse_tase.py`, `report/tase_stats.md`).
- **Encounter distribution.** It is uniform over each study's grid cells, with B's start delay drawn from U[0, 8] s (U[0, 10] s in 10 m corridors), and seeds as replicates (Sec. IV-C).
- **CIs.** The ± values are pooled normal CIs over all draws, which corresponds to the uniform encounter distribution. Differences are paired per encounter.
  - Stratified bootstrap CIs, which resample seeds within cells, are in the released report. They are narrower than the pooled CIs; for example, S1 `rules_proximity` is ±0.53 s pooled against [2.99, 3.29] s stratified.
  - The original intervals were therefore conservative. The issue was what population they described, and the paper now says so.
- **Primary metric.** Each failed episode is now charged 180 s per robot, and success-only means are secondary and labelled as such.
  - "Conservative" is replaced by "optimistic for policies with failures".
  - Only `reactive` is affected: its S1 excess delay is 86.5 s with failures charged, against 70.5 s over successes. All negotiating policies complete every encounter, so their two values coincide.
- **Parity claims.** These now use TOST with a ±0.5 s margin, or are called inconclusive.
- **Multiplicity.** Holm–Bonferroni is applied over the 20 paired comparisons behind Table VI. Two claims changed as a result, and Table VI and Sec. V-A were reworded to match:
  - In S4, `rules_default` and `fixed_priority` are equivalent within ±0.5 s (paired +0.14 s, TOST p < 0.001), not different.
  - Single-bay σ parity is now a range in which bidding and the rulebook are tied.
- **Weighting (R1 m5).** Every excess delay is written Δ^u (unweighted) or Δ^w (urgency-weighted), with D numbered as Eq. (11).

### #4 Counting errors (R1 m1, R3 M4, m1, m11; R3 Q7, Q8). Accepted.
- **Totals and policy count.** The paper now gives 50,714 episodes for the 18 original studies and 72,310 for the 8 revision studies, 123,024 in total. It says "nine policies (eight negotiating plus reactive)" throughout.
- **S7.** Of its 3,150 rows, 1,470 are unique episodes. N now counts unique episodes, and a footnote to Table III explains the difference.
- **Table III.** The caption defines N as executed episodes, with two forced runs per reference draw. It also adds the eight revision studies.
- **366 shared-draw runs (R3 m11).** These are the 460 main runs minus 10 `reactive`, 12 noisy-bid, 36 convoy and 36 T-junction runs (Sec. V-D).

### #5 Fairness credit (R1 M3, R3 M2; R1 Q4). Accepted (`studies/fairness_credit.py`, `report_r2/fairness_credit.md`).
- **Two forms.** Eq. (10) now prints the rule the code implements, the credit form λ(D_o − D_other). The absolute-value balance form is evaluated alongside it (Sec. IV-B).
- **Selection and evaluation.** λ is selected on the 50 S10 sequences and reported on 100 fresh sequences (S10b):
  - The credit form gives λ = 0.1, with J = 0.992 ± 0.002 at +3.8 ± 0.6% delay.
  - The balance form gives λ = 0.25, with J = 0.994 at +3.0%.
- **Noisy estimates.** With noisy delay estimates, the overhead of the credit form is +7.1%, +11.5% and +15.7% at σ = 0.25, 0.5 and 1.0, with J ≥ 0.986 (Sec. V-B).
- **Table VI.** "Rulebook + credit" is removed, because a rulebook does not produce the delay estimates d(o). The credit is now paired with urgency-weighted `cost_bid` only.

### #6 Reproducibility (R1 M8, m14; R3 M7). Accepted.
- **2D code version.** The claim "all reported statistics reflect the final codebase" is replaced by the actual commit, `dfc3d92`, and a pointer to the reproduction table (Sec. IV-D). `studies/run_all_2d.sh` refuses to run on a modified tree.
- **Gazebo rerun.** The 122 `bf24bf4` runs were rerun on the final code ([PR #44](https://github.com/briandeegan82/multi-agent-robots/pull/44)). Every negotiating run chose the same first yielder as before, and makespans changed by at most 1.6 s (Sec. V-D).
  - The rerun used an ARM64 image; the other 338 runs used amd64.
  - Only the stochastic `reactive` runs changed: 4 of 10 now fail (1 collision, 3 deadlocks), against 1 of 10 before.
- **Supplement.** Sec. S-V lists the commit and the command behind every table and figure, and Tables S-I and S-II list the notation and parameters.
- **Number trace.** `report/tase_numbers.csv` maps each manuscript number to its file and row.
- **Release DOI. [OPEN]** Tag a release, archive it on Zenodo, and add the DOI to the data statement.

### #7 Clarke pivot has no private information (R1 M2; R1 Q1; R2 M2). Accepted (`studies/clarke_private.py`, `report_r2/clarke_private.md`).
- **Implementation check.** S9 computes types from shared snapshots, so the 0/108 result is now presented as an implementation check (Sec. V-B).
- **Private-information study.** S9b treats urgency u_i as private and unverifiable. The deviator either misreports u_i or scales b_i(A) and b_i(B) independently.
- **Result.** Over 10,080 deviating episodes, no deviation improved predicted utility. Realized gains above 0.01 s occurred in 89 episodes (0.9%); all came from execution departing from the plan, and the mean realized gain was negative in every arm.
- **Credit semantics.** Payments are delay credit paid into an operator-held ledger, and utility is urgency-weighted delay plus payment. Redistribution of the credit is outside the model and listed as future work (Sec. VI).
- **Surplus.** It is now reported against realized delay: 37% and 24%.

### #8 Gazebo transfer partly true by construction (R1 M8, R2 m10, R3 m10; R1 Q8). Accepted (`studies/analyse_gazebo_tase.py`, `report_r2/gazebo_tase.md`).
- **Per-condition comparison.** Table S-IV gives agreement and paired Gazebo − 2D delay CIs for every condition and policy, and Fig. S6 is the Bland–Altman plot of raw delays.
- **Agreement.** It is 394/406 = 97.0% of negotiating main-batch runs (Wilson CI 94.9–98.3%). The abstract, Sec. I and the Conclusion now say "Gazebo with ground-truth localization".
- **Delays.** The bias is −1.35 s, with limits of agreement −27.6 to +24.9 s. The T-junction gap persists on the final code, so Sec. V-D states that T-junction delays do not transfer.
- **Old-commit runs (Q8).** None of the 12 disagreements came from the 122 old-commit runs, which agree 112/112 both before and after the rerun.
- **Noise pairing.** The ROS agent now supports the episode keying of the revision studies (`noise_key: episode`, noise fixed per seed and robot). Rerunning the 12 Gazebo noisy-bid cases with it gave the same first yielder as 2D in 12/12 runs, against 7/12 with the original round(t, 1) keying (Sec. IV-B). The 460-run table keeps the original runs, so the 5 noisy-bid disagreements remain and are attributed to the time keying (Sec. V-D).

### #9 Zero collisions at 99% loss attributed to snapshots (R1 M7, R2 m10; R1 Q5, Q7). Accepted.
- **C6 reworded.** Collision-freedom is now attributed to the local Lidar stopping and timer layer (Secs. I, V-C and VII). The abstract says robots "often fall back to reactive yielding".
- **Fallback share (Q5).** At extreme loss, 62.8% of S8b/S8c episodes never reached a negotiated decision.
- **Correlated loss on new seeds (Q7).** S8d uses seeds 1000–1019 and loss levels not used during development. It covers Gilbert–Elliott bursts with a mean length of 5–100 messages and 10–40 s blackouts:

| Channel | Episodes | Success | Reached a negotiated decision | Collisions |
|---|---|---|---|---|
| i.i.d. (same mean rates) | 480 | 99.4% | 86.7% | 0 |
| Bursty | 1,440 | 99.8% | 71.9% | 0 |
| Blackout | 640 | 100% | 92.5% | 0 |

- **Development seeds.** Sec. V-C states that the post-fix S8b runs reused the development seeds.
- **Not done (M7.4, M7.5).** Lidar detection noise and dropout, and a time-to-resolution distribution for mutual yields, are listed as limitations (Sec. VI).

### #10 Convoy row of Table VI (R3 M3, R1 m11, m10; R3 Q1). Accepted.
- **Table VI.** Convoys now recommend `fixed_priority` with `make_room`.
- **Sec. V-D numbers.** It gives:
  - `rules_default` against `fixed_priority`: 40.0, 100.1 and 133.6 s against 33.7, 33.7 and 90.3 s.
  - Each paired difference separately (R1 m11): with equal robots, `group_bid` is +0.7 ± 1.4 s from both `fixed_priority` and `side_oracle`, which coincide.
  - With urgent B: `group_bid` trails `fixed_priority` by 14.4 ± 8.0 s and `side_oracle` by 19.0 ± 6.9 s, and `fixed_priority` trails `side_oracle` by 4.6 ± 2.6 s.
- **Definitions.** "Equal robots" is defined as u = 1 for all three robots, unloaded (Q1). The per-cell n is 72, pooled over 3 seeds and 0/50% loss (R1 m10).
- **Figure.** The convoy figure moved to Fig. S9.

### #11 Citations (R2 M4, M5, m1–m4, m7, m8). Accepted.
- **Attributions.** SocNavBench is now attributed to Biswas et al. 2022, Dresner & Stone is described as reservation-based, and `fixed_priority` is credited to Čáp et al.
- **Preprints and bibliographic details.** Preprints are marked as such, years and volumes are checked against Crossref, the dead link is replaced, and DOIs are added. Jain et al. cites the 1984 DEC-TR-301, with the arXiv repost noted (m3), and [15] carries an access date (m2).
- **News items and public trust.** The news items are kept only as anecdotes ("reported anecdotally"), and the public-trust sentence is removed (R3 m21).
- **Fig. 1 credits (m8).** The caption credits the photographer and the CC BY-SA 2.0 licence, and states that the Dematic image is used with permission. **[AUTHORS]** Confirm the Dematic permission before submission.
- **Self-citation (m7).** It is now pointed to the specific contrast: infrastructure-based prescriptive collaboration versus peer-to-peer negotiation.
- **Length.** To meet the length target, 19 peripheral references were dropped. None of them is cited by the referees or needed for a claim.

### #12 Baselines (R1 M4, M5; R2 m5; R3 m7; R1 Q2). Accepted.
- **Randomized exponential backoff (S11b).** It completes more encounters than `reactive` but is not faster (Sec. V-A):

| Study | Policy | Success | Δ^u (s) |
|---|---|---|---|
| S1 | `reactive` | 93.8% | 86.5 ± 7.3 |
| S1 | `backoff` | 96.7% | 92.3 ± 6.3 |
| S1 | `fixed_priority` | 100% | 6.5 ± 0.6 |
| S4 | `reactive` | 97.8% | 72.0 ± 6.2 |
| S4 | `backoff` | 100% | 59.1 ± 4.0 |
| S4 | `fixed_priority` | 100% | 1.1 ± 0.3 |

- **Communication claim.** It is scoped to "this reactive design" and randomized backoff. ORCA/CBF baselines were not added, and Sec. VI says so.
- **Threshold sensitivity (S11a).** On S1, S2 and S4, most thresholds change excess delay by less than 0.8 s. Two do not:
  - An urgency threshold of 2.5 raises S2 excess to 15.7 s for `rules_default` and 9.1 s for `rules_proximity`.
  - A 1.0 m closest-refuge tie margin moves `rules_proximity` toward `rules_default`.
- **Tuning (Q2).** All rulebook thresholds were fixed before any benchmark run, and no policy parameter was tuned on benchmark outcomes; the only selected parameter is λ (Sec. IV-B). **[AUTHORS]** Confirm that the same is true of the reactive patience interval U[2, 6] s.
- **Reservation with staging off the exit path.** We tried it, but parking 1.2 m or more deeper in the end room deadlocked every run under the current leave manoeuvre. It is reported as untested (Sec. V-A, Table VI).
- **Learned baseline.** It is renamed "tabular full-information outcome classifier", with its training and evaluation distributions stated (Sec. IV-B, Sec. S-II).
  - CIs are added, along with seen-key and unseen-key errors on the unseen layout: +13.6 ± 4.6 s and +10.5 ± 6.8 s, with 15% of encounters on unseen keys.
  - The learning curve over 50/200/800 training encounters is in Sec. S-II.
  - The generalization conclusion is now presented as an illustration only.

### #13 T-ASE format (R3 M6, m17). Partly done.
- **Length.** The paper is now 14 pages, references included; the supplement is 10 pages. We moved notation, parameters, the S8c table, explore/hold, the classifier, the T-junction and Lidar-lag figures, the protocol diagram, the S2 and convoy figures, and the Gazebo per-condition table to the supplement. We also rewrote Secs. I, II, IV and V and removed the repeated numbers from Sec. VI-A.
- **Abstract.** It is now 199 words.
- **Figure text.** Figs. 2, 3, 4 and 8 were regenerated at their printed width with 8 pt minimum text (`paper_tase_rev/figures/make_figures_tase.py`). The stale in-plot "Fig. 16" label in Fig. 8 now reads "Supp. Fig. S5".

---

## Part B — Footnote and appendix items

- **"113 s (4.2×)" not reproducible. Clarified.** It does reproduce: charging each of the 26 deadlocked S1 encounters 2 × 180 s gives a mean of 113.4 s, which is 4.22× the 26.8 s reference. The derivation is stated in Sec. V-A.
- **Lost superscripts (R1 m7). Clarified.** The PDF typesets 0.9⁵ and 2³ correctly; the missing superscripts are an artefact of extracting the PDF text.
- **Wilson vs Clopper–Pearson (R1 m2). Accepted.** Zero-count bounds are labelled Wilson, 3.84/(n + 3.84). The statistics report gives the Clopper–Pearson values alongside.
- **S8c freshness reasoning (R3 M5, Q3). Accepted.** STATE freshness is timed from receipt, so a robot holds a fresh message only 5–41% of the time, and that message describes the peer 2–8 s earlier. Sec. V-C now explains the ablation on this basis.
- **Two-agent Jain range (R1 m12, R3 m8). Accepted.** Sec. V-B states that J ∈ [0.5, 1] for two robots and that J is computed per sequence and then averaged. It also gives the cumulative gap |D_A − D_B|: 372 s for fixed priority, 128 s for cost-optimal selection and 47 s for alternating.
- **Fig. 7 reference lines (R3 m6). Accepted.** That figure is now Fig. S1, and its caption names the source study of each line.
- **Study numbering (R3 m15). Accepted.** S5 was retired before release. The labels are kept so that they match the released data files, and a note to Table III says so. The new studies use suffixes (S7d/h/m, S8d, S9b, S10b, S11a/b).
- **Policy names (R3 m23). Clarified.** We keep the code names, defined once in Table II, because they match the released data and scripts.
- **Missed by the referees: two-bay S4.** `rules_proximity` has the highest negotiating excess delay in S4: 5.6 s, against 1.1 s for `fixed_priority`. The abstract, NtP and Table VI now say that it is competitive only with a single bay.
- **Missed by the referees: proximity rulebook file.** `proximity_first.yaml` lacked the payload rule described in the text. It has been added, and all 2D studies were rerun with it.

## Part C — Reviewer 1, remaining items

- **m4. Accepted.** Eq. (12) now uses the "better forced-yielder reference". The text states that it fixes the refuge from the planner, assumes immediate execution, and can give Δ < 0.
- **m6. Accepted.** Under truthful bidding, A yields in 67% of encounters and B in 33%, so A has more to gain from inflating its bid (Sec. V-B).
- **m9. Accepted.** The round(t, 1) seeding assumption is stated in Sec. IV-B, and the revision studies also key noise per episode.
- **m10. Accepted.** n per cell is given for the convoy and T-junction studies.
- **m13. Accepted.** Table VI gives the collusion range: +4.94 s at k = 0.5 and +7.42 s at k = 0.25.
- **Q6. Clarified.** No negotiating encounter is dropped from S1, S2 or S4. `reactive` loses 26, 60 and 8 encounters there, which are now charged at the cap.

## Part D — Reviewer 2, remaining items

- **m10.** Each abstract claim is now scoped; see #1, #8 and #9.
- **Q6 (AGV deadlock evidence). [OPEN]** We have found no peer-reviewed incident data, so the news items stay as anecdotes.
- **Q7.** Published versions are used where they exist.

## Part E — Reviewer 3, remaining items

- **m2. Accepted.** The NtP now says that rules match bidding once delay estimates are off by about 35% or more. It also says that all results come from simulation with exact localization.
- **m3. Accepted.** The Table VI row now reads "σ ≥ 0.35", with "tied at 0.35–0.45, ahead from 0.5".
- **m5 (Q6). Accepted.** Asymmetric-map runs with `commit` off show 109/420 disagreements and 7 deadlocks without map sharing, and none with `share_map`. Sec. V-C now concludes that `commit` is needed only without map sharing, which is consistent with Lesson 1.
- **m9.** Sec. S-IV now gives the denominators: 24 `hold_for_map` runs (6 seeds × 2 policies × R_det ∈ {3.5, 6.0} m); A sensed both bays in 24/24 runs and B in 20/24 (5/6 in each cell).
- **m12. Accepted.** Sec. IV-D defines a collision as SAT overlap of the rectangular footprints, or a robot centre within 0.50 m of a blocked-bay obstacle. Wall contacts are logged separately.
- **m13. Accepted.** D is numbered as Eq. (11), and every delay names its weighting.
- **m14, m16. Accepted.** The roadmap is fixed, and Sec. IV-C says "six scenarios over five geometries".
- **m18–m20. Accepted.** The wording was rewritten in Secs. V-A, V-B and V-D.
- **m22.** Table III's footnote now gives the corridor length per study: 10 m for the two-bay family (S4, asymmetric maps, blocked bays, explore & hold, convoy), 8 m otherwise, plus a 2 m stem at the T-junction.
- **Practitioner value: message budget.** The median is 664–720 messages per episode across loss levels, mostly 5 Hz STATE beacons (Sec. V-C).
- **Practitioner value: more than two robots.** This is limited to the two topologies tested (Sec. VI).
- **Practitioner value: using the VCG surplus.** The surplus stays in the operator's ledger; redistribution is future work (Sec. VI).
