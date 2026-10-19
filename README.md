# One User, One Agent — STAGE assessment

A local Python implementation of the supplied assignment: each viewer owns one measurable goal, a safe home-page plan, an evidence ledger, and attributable outcome judgments. It includes replay faults, an independent verifier, SQLite memory, and randomized-arm measurement. No API key, web server, or paid service is needed.

Start with [the step-by-step guide](docs/STEP_BY_STEP.md), then [technical discussion notes](docs/TECHNICAL_DISCUSSION.md). Read [limitations](KNOWN_LIMITATIONS.md) before describing this as a complete production system.

## Run

Python 3.10+ (validated with 3.12). There are **no third-party runtime dependencies**. From this repository:

```bash
python -m unittest discover -s tests -v
python run.py --pack data_pack --out sample_run
```

The second command loads the data, replays all triggers and control events, runs the **unchanged supplied simulator**, judges goals, and writes reports. It needs roughly 300 MB of disk space. Use a different output directory for each run; existing results are preserved.

The assignment pack has already been extracted into `data_pack/` in this workspace. For a separate checkout, obtain the supplied ZIP privately, extract it, and pass the directory containing `config/`, `data/`, `replay/`, `pilot/`, and `simulator/` as `--pack`. The archive's enclosing directory is named `one_user_one_agent_pack`. The pack and full personal-data outputs are ignored by Git; code and documents do not require uploading them anywhere.

To change evaluator seed or budgets:

```bash
python run.py --pack data_pack --out sample_run_seed2 --seed alternate --max-model-calls 8 --max-tool-calls 20
```

`run.py` adds `src/` to the Python import path, so installation is optional. For editor integration, an editable install is also supported: `python -m pip install -e .`.

## Files

```text
run.py                       zero-install CLI entry point
pyproject.toml               package metadata, Python version, no runtime dependencies
src/stage_agent/
  common.py                  UTC/IST, file I/O, buffered-trigger age
  data.py                    pack schema, profile selection, title availability
  store.py                   durable events, goals, decisions, actions, audits
  facts.py                   fact precedence, provenance, freshness, conflicts
  goals.py                   eligibility, priority, deadlines, outcome predicates
  provider.py                bounded mock provider and call budgets
  planner.py                 conservative home-page candidate
  verifier.py                independent model and publication gates
  engine.py                  one active viewer plan, replanning, idempotent decisions
  reports.py                 goal judgments, ITT, intervals, pilot correction
  cli.py                     chronological replay and simulator orchestration
 tests/test_agent.py         behavioral tests with small fixtures
 docs/                       learning guide and interview preparation
 sample_run/                 generated locally, ignored by Git
```

## Outputs

- `decisions.jsonl`: unique-trigger decisions, explicit abstentions, fact sources/ages, assumptions, conflicts, checks, budgets and timings.
- `actions.jsonl`: simulator-compatible home-page publications.
- `state.sqlite3`: durable raw evidence and atomic initial decision/action ledger, goal history, audits and outcome judgments.
- `viewer_state/<user>.json`: follow-up facts, goal history, decision/action references, outcome evidence and learning.
- `audit.jsonl`: affected goal instances, withdrawals, dependency faults and billing replans.
- `outcomes.jsonl`: goal judgments; raw behavioral events are in `sim/outcome_events.jsonl`.
- `latency_report.json`, `data_quality.json`, `impact_report.md`, `impact_metrics.json`, `final_report.md`.
- `sim/simulator_report.json`: independent supplied simulator's acceptance and policy checks.

Read the impact report's denominator and coverage discussion. Recorded goal success does not prove an individual action caused it. This implementation chooses home pages or abstention; push and WhatsApp generation are deliberately out of scope.
