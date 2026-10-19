# STAGE — One User, One Agent

A local, evidence-driven lifecycle agent for the supplied STAGE assessment. Each viewer has one active goal, an auditable decision, and an attributable outcome. The project includes a chronological replay, SQLite state, an independent verifier, a mock provider, randomized measurement and a checked-in sample run.

The implementation chooses **a home page or explicit abstention**. No unsolicited messaging or hosted model is enabled. Read [known limitations](KNOWN_LIMITATIONS.md) before making deployment claims.

## Run on Windows, macOS or Linux

Python 3.10+; no third-party runtime dependencies or API keys.

1. Download/clone this repository.
2. Extract the assignment ZIP privately. Rename its inner `one_user_one_agent_pack` directory to `data_pack` and put it beside `run.py`.
3. Verify that `data_pack/data/catalogue.csv` exists. There must not be another enclosing pack directory between `data_pack/` and `data/`.
4. Run from the repository root:

```bash
python -m unittest discover -s tests -v
python run.py --pack data_pack --out practice_run
python audit_run.py --pack data_pack --run practice_run
```

The second command is the full pipeline: evidence ingestion → replay → unchanged supplied simulator → goal judgments → impact and latency reports. Use a new output directory for each run. The committed `sample_run/` is evidence from a completed run, not a directory to overwrite.

For a different seed:

```bash
python run.py --pack data_pack --out practice_run_seed2 --seed alternate
```

For a 1,000-request burst benchmark with four process shards:

```bash
python load_test.py --pack data_pack --out load_run --requests 1000 --workers 4
```

All benchmark requests are queued together. Reported end-to-end time includes process startup, pack loading, history ingestion, queue wait and durable release. Viewer hashing preserves one owner per viewer. This uses local SQLite per shard and a mock provider; it is not a production shared-database benchmark.

## How to learn the code

- [Step-by-step guide](docs/STEP_BY_STEP.md): files, behavior, implementation choices and practice questions.
- [Architecture](ARCHITECTURE.md): ownership, trust boundaries, failure recovery and measurement.
- [Technical discussion notes](docs/TECHNICAL_DISCUSSION.md): defensible answers and a real viewer trace.
- [Review exercises](docs/OWNER_REVIEW.md): changes and checks you can perform yourself.
- [Validation](docs/VALIDATION.md): commands, evidence and limits.
- [AI collaboration](AI_COLLABORATION.md): actual assistance and review history.

```text
run.py / audit_run.py / load_test.py
src/stage_agent/
  common.py       time and file helpers
  data.py         pack loading, profile versions and catalogue availability
  facts.py        source-specific precedence, freshness and conflicts
  goals.py        eligibility, deadlines, rule corrections and outcome predicates
  planner.py      goal-relevant hero and catalogue-backed genre rows
  verifier.py     independent evidence and publication gates
  provider.py     mock faults and configurable call budgets
  store.py        SQLite ledger and pending/ready publication states
  recovery.py     independent durable abstention journal
  engine.py       viewer lifecycle, safe failures, revocation and rebuilding
  cohort.py       pre-intervention measurement goals and missing-outcome bounds
  reports.py      judgments, randomized comparisons and pilot correction
  cli.py          full pipeline orchestration
 tests/           behavioral and regression tests
 sample_run/      decisions, actions, states, judgments, audits and reports
```

## Measurement contracts

The primary report compares **baseline-goal success by randomized arm**. Measurement goals are frozen before the first intervention and kept separate from adaptive treatment goals. All randomized users remain visible. Missing follow-up and undefined/unavailable goals are inconclusive; they are not silently counted as failures. Full-population goal-success point estimates are not identified from this pack, so the report supplies bounds and a sampling envelope, plus goal-specific results. A seven-day recorded-completion endpoint remains a secondary metric with its observation limitations stated.

A successful individual goal does not establish that an intervention caused it. The pilot re-analysis demonstrates why served-versus-unserved comparisons are biased.

## Important output files

`decisions.jsonl`, `actions.jsonl`, `viewer_state/`, `outcomes.jsonl`, `cohort_outcomes.jsonl`, `revocations.jsonl`, `audit.jsonl`, `latency_report.json`, `latency_observations.jsonl`, `impact_report.md`, `impact_metrics.json`, `artifact_audit.json`, `final_report.md`, and `sim/`.

SQLite and emergency journal files are generated locally and excluded from Git. Source data remains excluded; the evaluator needs the supplied ZIP. The sample run's simulator events allow checking outcome evidence without a database file.
