# Validation performed

Commands executed from the repository root:

```bash
python -m unittest discover -s tests -v
python run.py --pack data_pack --out sample_run
```

- 16 behavioral tests passed.
- Complete final replay processed 2,769 input triggers into 2,679 unique decisions; 90 duplicate triggers reused the original decisions.
- Published 1,013 home pages and recorded 1,666 abstentions.
- Supplied simulator generated 31,506 events for 1,746 triggered viewers; accepted all 1,013 pages; reported zero policy problems.
- Judged 1,370 goal instances: 108 succeeded, 1,262 failed. These are goal attempts, not unique viewer-level experimental outcomes.
- Every local decision completed within the 60-second budget. Read the current latency JSON for exact measurements and mock fault timing assumptions.
- An independent artifact audit checked all actions for randomized agent membership, unique trigger IDs, title availability including withdrawals, dialect, content-slug uniqueness, row limits, and decision budgets. SQLite held no open goals after follow-up judging and contained all 1,370 outcome judgments.
- The data audit measured 2,176 duplicate historical event rows, 30 extra profile versions and 514 extra catalogue language variants. Two descriptions were heuristically flagged; descriptions never become executable instructions regardless of that heuristic.

Primary fixed-endpoint recorded-completion difference: -0.12 percentage points, 95% interval [-2.10, 1.86]. Triggered-viewer subset: +1.10 points, interval [-3.54, 5.73]. Neither establishes clear positive uplift. Read the coverage caveat in the impact report; untriggered actual viewing is unobserved.

Pilot randomized comparison: treatment 349/1,912 versus holdout 387/1,979; difference -1.30 points. The biased served comparison produces +22.43 points. The latter must not justify rollout.

No production concurrency, real provider, external publication API, live-page revocation, or fresh remote clone restoration was tested. The repository was initially empty; these are newly created, uncommitted source files. No commit, push or deployment was performed.
