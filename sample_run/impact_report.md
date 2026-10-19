# Impact report

## Primary: baseline-goal success by randomized arm

Measurement goals were frozen for every randomized user before the first intervention, using only already-arrived facts. They are separate from adaptive treatment goals. All assigned users, including abstentions, remain in their arm. No eligible goal, missing simulator follow-up, and incomplete goal windows are **inconclusive**, not failed. Unknown outcomes prevent an identified full-population point estimate.

- All randomized users: agent: n=2513, succeeded=52, failed=747, inconclusive=1714; holdout: n=2487, succeeded=50, failed=782, inconclusive=1655. Success difference bounds [-66.49, 68.26] pp; 95% sampling envelope [-68.35, 70.08] pp.
- Pre-intervention eligible-goal cohort: agent: n=2379, succeeded=52, failed=747, inconclusive=1580; holdout: n=2357, succeeded=50, failed=782, inconclusive=1525. Success difference bounds [-64.64, 66.48] pp; 95% sampling envelope [-66.58, 68.38] pp.

### Baseline goal breakdown

- G01: agent: n=56, succeeded=5, failed=10, inconclusive=41; holdout: n=42, succeeded=2, failed=10, inconclusive=30. Success difference bounds [-67.26, 77.38] pp; 95% sampling envelope [-78.76, 85.96] pp.
- G02: agent: n=819, succeeded=22, failed=157, inconclusive=640; holdout: n=800, succeeded=14, failed=154, inconclusive=632. Success difference bounds [-78.06, 79.08] pp; 95% sampling envelope [-80.80, 81.73] pp.
- G03: agent: n=11, succeeded=1, failed=2, inconclusive=8; holdout: n=9, succeeded=1, failed=3, inconclusive=5. Success difference bounds [-57.58, 70.71] pp; 95% sampling envelope [-80.12, 86.63] pp.
- G04: agent: n=1, succeeded=0, failed=1, inconclusive=0; holdout: n=0, succeeded=0, failed=0, inconclusive=0. Difference unavailable (empty arm).
- G05: agent: n=205, succeeded=3, failed=50, inconclusive=152; holdout: n=202, succeeded=5, failed=53, inconclusive=144. Success difference bounds [-72.30, 73.13] pp; 95% sampling envelope [-77.96, 78.69] pp.
- G06: agent: n=20, succeeded=1, failed=9, inconclusive=10; holdout: n=13, succeeded=1, failed=7, inconclusive=5. Success difference bounds [-41.15, 47.31] pp; 95% sampling envelope [-66.20, 67.50] pp.
- G07: agent: n=1194, succeeded=10, failed=482, inconclusive=702; holdout: n=1205, succeeded=15, failed=512, inconclusive=678. Success difference bounds [-56.67, 58.39] pp; 95% sampling envelope [-59.46, 61.18] pp.
- G08: agent: n=54, succeeded=8, failed=28, inconclusive=18; holdout: n=61, succeeded=11, failed=36, inconclusive=14. Success difference bounds [-26.17, 30.12] pp; 95% sampling envelope [-40.56, 45.20] pp.
- G09: agent: n=17, succeeded=2, failed=8, inconclusive=7; holdout: n=20, succeeded=1, failed=7, inconclusive=12. Success difference bounds [-53.24, 47.94] pp; 95% sampling envelope [-72.12, 69.24] pp.
- G12: agent: n=2, succeeded=0, failed=0, inconclusive=2; holdout: n=5, succeeded=0, failed=0, inconclusive=5. Success difference bounds [-100.00, 100.00] pp; 95% sampling envelope [-100.00, 100.00] pp.

Bounds assign every unknown outcome both possible values. The sampling envelope adds Newcombe/Wilson uncertainty at those extremes. It is not a missing-data correction or evidence of rollout benefit. No served-only selection is used. See cohort_outcomes.jsonl for each denominator.

## Secondary: seven-day recorded completion

Endpoint fixed before analysis: at least one **recorded episode completion** in the seven days from replay start. Every randomized user stays in their assigned arm, including abstentions. This endpoint does not depend on the goal or whether an action was served.

- All randomized users: recorded-completion ITT: agent: 373/2513 (14.84%); holdout: 374/2487 (15.04%). Difference -0.20 pp; 95% CI [-2.17, 1.78] pp.
- Triggered-user subset (includes all abstentions): agent: 373/863 (43.22%); holdout: 374/883 (42.36%). Difference 0.87 pp; 95% CI [-3.77, 5.50] pp.

Coverage: 1746 triggered / 5000 randomized; 3254 users are not simulated. Their endpoint is zero **recorded** completions, not evidence they did not watch. The full-assignment estimate measures this simulator observation process; it must not be presented as population watch uplift in production. The triggered subset is selected before the first action but does not estimate impact on untriggered users. No causal claim beyond this synthetic experiment.

## Initial goal outcomes (descriptive, by baseline goal)

First-decision goals are frozen per viewer before their first intervention. No later goal is substituted. Inconclusive outcomes remain in the denominator and are separately counted; these are recorded-success contrasts, not an estimate of success for censored goals. Goal groups are small; no multiple-testing correction.

- G01: agent: 18/58 (31.03%); holdout: 14/50 (28.00%). Difference 3.03 pp; 95% CI [-14.15, 19.58] pp.
  Outcome counts: {'failed': 76, 'succeeded': 32}.
- G02: agent: 20/136 (14.71%); holdout: 10/128 (7.81%). Difference 6.89 pp; 95% CI [-0.88, 14.65] pp.
  Outcome counts: {'failed': 234, 'succeeded': 30}.
- G03: agent: 0/1 (0.00%); holdout: 1/2 (50.00%). Difference -50.00 pp; 95% CI [-90.55, 39.10] pp.
  Outcome counts: {'failed': 2, 'succeeded': 1}.
- G04: agent: n=0; holdout: 0/1 (0.00%). Difference unavailable.
  Outcome counts: {'failed': 1}.
- G05: agent: 1/13 (7.69%); holdout: 2/15 (13.33%). Difference -5.64 pp; 95% CI [-30.99, 21.72] pp.
  Outcome counts: {'succeeded': 3, 'failed': 25}.
- G06: agent: 0/4 (0.00%); holdout: 1/3 (33.33%). Difference -33.33 pp; 95% CI [-79.23, 22.69] pp.
  Outcome counts: {'succeeded': 1, 'failed': 6}.
- G07: agent: 9/429 (2.10%); holdout: 13/413 (3.15%). Difference -1.05 pp; 95% CI [-3.43, 1.20] pp.
  Outcome counts: {'failed': 820, 'succeeded': 22}.
- G08: agent: 3/6 (50.00%); holdout: 2/12 (16.67%). Difference 33.33 pp; 95% CI [-8.71, 66.79] pp.
  Outcome counts: {'succeeded': 5, 'failed': 13}.
- G09: agent: 0/4 (0.00%); holdout: 1/3 (33.33%). Difference -33.33 pp; 95% CI [-79.23, 22.69] pp.
  Outcome counts: {'failed': 6, 'succeeded': 1}.
- G12: agent: n=0; holdout: 0/1 (0.00%). Difference unavailable.
  Outcome counts: {'failed': 1}.

Confidence intervals use Newcombe differences of Wilson limits, independent viewers. One simulation seed is not a production experiment; intervals omit simulator/model uncertainty.

## Pilot re-analysis

- Randomized assignment (ITT): treatment: 349/1912 (18.25%); holdout: 387/1979 (19.56%). Difference -1.30 pp; 95% CI [-3.76, 1.16] pp.
- Served vs all others (biased): agent: 87/217 (40.09%); holdout: 649/3674 (17.66%). Difference 22.43 pp; 95% CI [16.01, 29.17] pp.

Serving is a post-assignment selection: active, reachable viewers are more likely to be served. Randomized treatment includes unserved viewers; excluding them destroys the randomized comparison.
