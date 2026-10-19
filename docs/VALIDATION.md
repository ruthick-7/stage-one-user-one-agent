# How my project was validated

These are the automated checks and recorded results from development with Codex. I keep my own completed Windows checks separate in [my review notes](OWNER_REVIEW.md). To reproduce the validation, I run these commands from the repository root:

```bash
python -m unittest discover -s tests -v
python run.py --pack data_pack --out practice_run
python audit_run.py --pack data_pack --run practice_run
python load_test.py --pack data_pack --out load_run --requests 1000 --workers 4
```

## Recorded core results

- 29 tests passed, including genuine SQL read/write failures, interrupted release, durable recovery across reopening, late-delivered plays, local page revocation/rebuilding, missing-outcome bounds, baseline freezing and rule-correction integration.
- 2,679 unique decisions from 2,769 triggers, with 90 duplicates; 917 pages and 1,762 abstentions.
- Supplied simulator generated 31,481 events for 1,746 viewers and reported 0 policy problems. Every published page was accepted.
- 1,370 adaptive goal instances judged: {'failed': 1265, 'succeeded': 105}. These are attempts, not unique randomized viewers.
- Local replay maximum entry-to-durable-release latency: 48.40 ms; 0 decisions over 60 seconds. Timing includes final release completion; publication timestamps mark release requests.
- Independent artifact audit passed holdout, duplicate, availability/withdrawal, genre/row/slug, budget, latency and 5,000-user cohort-denominator checks.
- Burst benchmark: 1,000 requests queued together, 4 viewer shards, 2.67s total, p95 end-to-end 2366.32 ms, maximum 2461.98 ms, 0 deadline misses. This is a local mock-provider benchmark with separate SQLite per shard.

## Measurement

For measurement, I keep baseline goals fixed before intervention and retain every randomized user in their assigned arm. Missing follow-up is inconclusive. The primary report supplies goal-success identification bounds and sampling envelopes; it does not claim an identified population point estimate. Read sample_run/impact_report.md for all denominators and the secondary completion metric.

The pilot randomized comparison is treatment 349/1,912 versus holdout 387/1,979 (-1.30 percentage points), while the biased served comparison gives +22.43 points. I would not use the biased comparison to justify rollout.

## Limits

The supplied simulator remains unchanged. Local revocation is tested directly because the simulator does not model pure revocation. Hosted models, external platform delivery, shared-database production load and unseen replay days are not validated. I ran the earlier version on Windows. The revised version was checked in the Linux development environment with Codex. A Windows/Linux GitHub Actions matrix is configured, but a workflow run is not claimed until observed.

## Clean-checkout / second-seed check

A clean local Git clone of implementation commit `cb23e67` ran all 29 tests, then the full replay with seed `evaluation-check`, using the provided pack as an external read-only input. The simulator generated 31,951 events, reported 0 policy problems, and the independent artifact audit passed. The generated viewer walkthrough was present. No decision exceeded 60 seconds. See `sample_run/clean_checkout_validation.json` for the exact evidence. I use this as evidence that the source can be reproduced from a clean checkout. It does not establish unseen replay-day behavior or validation of a remote cloud snapshot.

## Website addition

My project now has 40 unit/HTTP tests, with additional Chromium desktop/mobile and full replay checks recorded during development. See [WEBSITE_VALIDATION.md](WEBSITE_VALIDATION.md) for website-specific evidence and scope. The earlier 29-test results above refer to the core release.
