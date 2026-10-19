# Build and understand the project, step by step

Read this in order with the linked source file open. Each stage names the files, explains the implementation, and gives a question to practice. You do not need to memorize code. You should be able to explain the inputs, decision, safety check, and output of each function.

## Step 1 — Establish the project boundary

**Files:** [`../run.py`](../run.py), [`../pyproject.toml`](../pyproject.toml), [`../.gitignore`](../.gitignore), [`../README.md`](../README.md).

The assignment needs a runnable lifecycle loop, not a web UI. A CLI makes time ordering and evaluator reproduction easier. Python's standard library supplies JSON, CSV, SQLite, subprocesses and statistics, so no framework is required. `run.py` adds `src/` to the import path and calls `cli.main()`.

```bash
python run.py --pack data_pack --out my_run
```

`data_pack/` is read-only input. `my_run/` is output. We preserve old runs rather than silently overwrite them. The provided pack and databases are ignored by Git; a verified sample run is included in the submission. Application code and synthetic unit-test fixtures are shareable separately.

**Practice:** Why no FastAPI or LangChain? Because this problem's hard parts are lifecycle correctness, evidence, replay ordering and measurement. A framework would not establish those invariants. A real service interface can wrap the engine later.

## Step 2 — Load the evidence and normalize time

**Folder:** `src/stage_agent/`.

**Files:** [`common.py`](../src/stage_agent/common.py), [`data.py`](../src/stage_agent/data.py).

`Pack` loads catalogue, episodes, profiles, goals, interventions, randomized arms and model-fault fixtures. It indexes catalogue by title ID, episodes by content slug, and profile versions by user ID. `Pack.profile(user, at)` excludes future snapshots and chooses the latest valid version deterministically. The line reference lets a reviewer find the exact source row.

`Pack.available(title_id, at, dialect)` checks catalogue existence, dialect, start/end windows and operational withdrawals. A catalogue description remains an inert string. The application never evaluates it, follows it, or sends it to a model as instructions.

Time helpers return timezone-aware values. UTC is used for event ordering; IST is used for daily policy and return/habit goals.

```python
buffered = max(0, sent_at - occurred_at)
queue_delay = max(0, deliver_at - received_at)
event_age = buffered + queue_delay
```

That is pseudocode for `trigger_age`; actual implementation converts differences to seconds. Subtracting two device times cancels a fixed clock offset. Comparing a wrong device clock directly with server time would incorrectly classify some live visits as stale.

**Practice:** Does `received_at` tell you when the user actually watched? It tells you when the server learned about it. Buffering can mean the behavior predates the goal; the outcome predicate explicitly excludes that case when the available timestamps demonstrate it.

## Step 3 — Make state durable and actions idempotent

**File:** [`store.py`](../src/stage_agent/store.py).

SQLite tables separate raw evidence, goal instances, decisions, actions, audits and outcome judgments. Raw event IDs and trigger IDs have unique keys. Replayed duplicates cannot create additional actions.

Important database invariant:

```sql
CREATE UNIQUE INDEX one_open_goal
ON goals(user_id) WHERE status='open';
```

The engine also checks the invariant in memory. Database enforcement protects against mistakes in the application layer. A goal is a particular attempt, with its own `instance_id`, start time, deadline, rule version and eventual status. The goal ID such as G04 identifies a goal type, not an individual attempt.

Before processing a trigger, the engine asks `Store.decision(event_id)`. If already present, it returns the original result. The restart test closes and reopens SQLite and verifies that only one action exists.

**Practice:** Is this exactly-once delivery? No. It is durable idempotent decision creation in one local process. The local outbox stages pending entries and exposes only ready ones. An interrupted pending publication becomes an abstention. An external receiving service still needs its own idempotency and delivery contract.

## Step 4 — Resolve facts with provenance

**File:** [`facts.py`](../src/stage_agent/facts.py).

`resolve()` does not return only `dialect='d2'`. It returns:

```json
{"value": "d2", "source": "app_setting:event:<id>", "at": "<UTC timestamp>", "age_s": 4.2}
```

This is the schema, not a claim about a particular viewer. Actual values are in decisions and viewer-state files.

Each fact has its own precedence rule. New billing evidence can override an old subscription profile. An explicit opt-out overrides positive profile consent. An arrived app setting decides the dialect the app will request. A campaign link may disagree but cannot change that setting. Previous conflicting values remain visible instead of disappearing.

`value(state, key)` is a small convenience helper; the full source/age record remains in `state['facts']`.

**Practice:** Why not let the newest source always win? Because sources have different authority for different facts. A new campaign link is less authoritative about the current app dialect than an actual app-setting event.

## Step 5 — Select one measurable goal

**File:** [`goals.py`](../src/stage_agent/goals.py).

`eligibility()` returns three things: whether evidence supports eligibility, optional goal context, and evidence references. It does not trust a model's assertion. `choose()` checks a documented priority list and creates one goal instance.

For example G07 requires a previously played show/micro-drama, an episode not yet completed, and at least three days since its last play. Its context stores the series slug and next uncompleted episode ID. This lets its success predicate require the same series rather than accepting any play.

Each chosen goal stores:

```text
instance_id, user_id, id, started_at, deadline,
success_signal, rule_version, context, eligibility_evidence, status
```

G10 is undefined; G11 has no observable event. Neither is made measurable by inventing a proxy. G06 interprets "recently lapsed" as 30 days. G09 counts distinct IST dates. A first-play/first-completion claim is limited to the supplied history and is disclosed as an assumption.

An active goal is retained across visits. Billing events can close or invalidate it and immediately create a replacement. Actions are still emitted only on triggers.

**Practice:** Why is a deadline essential? Without a start and end window, any eventual behavior could be called success, and the agent could keep moving its target after seeing the outcome.

## Step 6 — Treat the model as a proposal source

**File:** [`provider.py`](../src/stage_agent/provider.py).

`Budget` counts logical tool/model calls before invoking them. `MockProvider.propose()` normally returns the deterministic candidate ID and its evidence references. Fault fixtures can instead produce malformed JSON, a timeout, a 503, or an unsupported billing claim.

The mock is intentionally modest: it demonstrates orchestration and failure handling without pretending that a model adds predictive value. No API key or viewer-data upload is required. A real adapter should implement the same contract and deadlines; this repository does not implement that adapter.

Named faults on stale triggers are logged as configured but skipped, because stale visits do not justify model work. The report does not call those faults successfully exercised.

**Practice:** Why use a model if the default candidate is deterministic? For this baseline it tests an untrusted proposal boundary. In production, model use should be justified by a measurable uncertainty reduction, not by the label "agent."

## Step 7 — Plan an action, then let a separate checker reject it

**Files:** [`planner.py`](../src/stage_agent/planner.py), [`verifier.py`](../src/stage_agent/verifier.py).

The planner selects available content for the resolved dialect. It prefers the goal's target series, then recent releases, prevents duplicate slugs, and uses non-premium content for non-subscribers. It builds one hero and valid row sizes; insufficient content yields no candidate.

The verifier is called after planning. It independently recomputes eligibility at commitment, then checks current publication policy. It checks holdout, duplicate trigger actions, supported types, row structure, dialect, availability and unique slugs. Model evidence is checked separately before the model is allowed to influence the plan.

A checker that just reads `proposal['eligible']` would not be independent. Here the model's injected "billing confirmed" claim is rejected because it has no evidence in the pack.

This version emits only `home_page` or `NO_ACTION`. The messaging gate is tested, but outbound generation/scheduling is not implemented. Outbound messaging remains out of scope. Local page revocation and safe rebuilding are implemented and tested.

**Practice:** Why is no action a first-class result? It preserves the reason, facts and timing for a safe abstention. Missing output cannot tell you whether the system was cautious or crashed.

## Step 8 — Orchestrate replay and react to changes

**Files:** [`engine.py`](../src/stage_agent/engine.py), [`cli.py`](../src/stage_agent/cli.py).

The main flow is:

```text
deliver event/control/trigger in server-time order
  -> ingest unique evidence
  -> settle/revise current goal
  -> resolve facts
  -> reject stale visit or unavailable required data
  -> retain/select one goal
  -> bounded model proposal
  -> independent proposal check
  -> deterministic page plan or explicit abstention
  -> independent publication check
  -> persist decision and action
```

A goal-rule correction changes the policy and only open instances of that goal. Closed instances keep their prior rule. A withdrawal blocks future promotion, revokes affected local pages and attempts verified replacements. If there is insufficient valid content, serving uses the default page. External platform revocation remains an integration boundary.

Model failures fall back to deterministic planning with the same gate. Required-data failures abstain. Actual SQLite failures are caught across the decision and recorded in a separate fsynced recovery journal; further publication closes until a fresh engine/replay is prepared. The mock times out the 45-second fault at 20ms; the degraded-store window is a fail-fast circuit. No long real network dependency was benchmarked.

**Practice:** Can this handle a production evening spike? The main replay is sequential; `load_test.py` separately measures a burst across isolated process shards, including queue and startup time. Neither establishes distributed production capacity. Explain the partitioned per-viewer queue, bounded admission, timeouts and shared database changes you would need. Do not equate low local latency with a proven load test.

## Step 9 — Judge outcomes and measure impact honestly

**Files:** [`goals.py`](../src/stage_agent/goals.py), [`reports.py`](../src/stage_agent/reports.py).

The CLI runs the supplied simulator unchanged. `judge()` applies each committed goal's predicate to evidence inside its window. It returns succeeded, failed or inconclusive. A goal with incomplete follow-up is not automatically failed. Invalidated goals have a censored observation window.

The primary report freezes a baseline measurement goal for every randomized viewer before intervention (`cohort.py`). It records success, failure and inconclusive outcomes and reports missing-outcome bounds by randomized arm and goal. Recorded completion within seven days is a secondary endpoint. All randomized agent/holdout users remain in the arm comparison. It additionally shows triggered viewers and initial-goal subgroups. It uses user-level binary outcomes so a heavy viewer's 50 plays do not become 50 independent experimental observations.

```text
known_success_rate = observed successes / all assigned viewers in arm
possible_success_rate = (observed successes + inconclusive) / all assigned viewers
difference_bounds = [agent_lower - holdout_upper, agent_upper - holdout_lower]
```

With complete observed binary outcomes, confidence intervals express sampling uncertainty. When follow-up is missing, the primary goal report gives worst-case outcome bounds and a sampling envelope; it does not turn missing observations into failures. Untriggered users have no simulator follow-up. The secondary full-arm recorded-completion endpoint measures the observation process. The primary goal analysis keeps unavailable follow-up inconclusive and does not claim an identified population uplift. Read this caveat aloud when presenting the result.

The pilot report is recomputed by randomized assignment. Served vs everyone else is biased because being served depends on viewer activity and reachability.

**Practice:** Did a particular successful goal prove the action worked? No. It proves an attributable event was observed in-window. Randomized group comparisons are needed to estimate incremental impact.

## Step 10 — Verify and practice with real artifacts

**File:** [`test_agent.py`](../tests/test_agent.py).

```bash
python -m unittest discover -s tests -v
python run.py --pack data_pack --out practice_run --seed my-practice-seed
```

Open one decision in `practice_run/decisions.jsonl`, its viewer-state file, the corresponding action, and its outcome judgment. Locate each referenced event or catalogue title in the pack. Follow the [generated viewer trace](../sample_run/viewer_walkthrough.md) first, then pick another viewer yourself.

Use the tests to practice changes in a scratch copy: change a dialect, set holdout, withdraw the hero, inject malformed JSON, or put an event outside the goal window. Predict the output before running it. This is stronger interview preparation than memorizing this guide.
