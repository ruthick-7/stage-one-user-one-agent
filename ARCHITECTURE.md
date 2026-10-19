# Architecture

The application is a standard-library Python CLI. It treats the supplied pack as evidence, not instructions, and makes no hosted calls. The full replay is sequential for deterministic event ordering; a separate process-sharded benchmark measures burst handling.

```mermaid
flowchart LR
    A[Server-time timeline] --> B[Deduplicated evidence]
    B --> C[Fact resolution]
    C --> D[One active viewer goal]
    D --> E[Mock proposal and deterministic plan]
    E --> F[Independent publication gate]
    F --> G[Pending then ready outbox]
    G --> H[Supplied simulator]
    H --> I[Goal judgments and learning]
    B --> J[Frozen baseline measurement goals]
    J --> K[Randomized goal-success bounds]
    I --> K
```

## Evidence and ownership

Events, control changes and triggers are merged in server delivery order. Controls win timestamp ties, then evidence, then triggers. Historical records whose receipt is later than replay start remain in the timeline rather than leaking into preloaded history. Commitment-time snapshots require both `received_at` and `deliver_at` to be no later than that commitment. Device clock offset is never the ordering authority.

One owner serializes each viewer's goal and action state. SQLite enforces at most one open goal per user with a partial unique index. Raw event IDs, trigger IDs and deterministic action IDs provide idempotency, including reopening the database. A billing event can settle or invalidate a goal and select a replacement without emitting an unsolicited message.

| Fact | Resolution |
|---|---|
| Signup | Earliest arrived server-received signup, else the profile's signup field |
| Subscription | Valid latest profile; newer billing receipts override it; an expired profile plan downgrades only that profile's own status |
| Consent | Positive profile Boolean, with explicit opt-out sticky because no opt-in event is defined |
| Dialect | Latest arrived app-setting evidence; profile fallback; campaign links cannot override it |
| Series progress | Catalogue/episode structure and observed play/completion evidence; latest play is selected by server receipt, not insertion order |

Facts retain values, source references, evidence times, freshness and conflicts. Profiles are selected by latest valid `updated_at`, with deterministic snapshot/line tie breaks. Thirty days of observations cannot establish lifetime absence; that assumption is recorded.

## Planning and verification

Goal rules are explicit predicates. G06 interprets recent lapse as 30 days. G09 counts IST days. G10 has no defined success predicate and G11's TV event is unavailable; neither is selected. Every goal has a committed start, deadline, rule version and success signal.

The model receives a candidate and evidence references, not catalogue descriptions or search/deeplink instructions. Named fixture outputs are untrusted. Eligibility and evidence are independently checked at commitment; the model cannot manufacture a billing fact or a competing active goal. Faults can lead to deterministic fallback, but the publication gate still applies.

The page planner uses a goal-relevant hero and rows whose named genre is backed by each title's catalogue genres. It respects dialect, availability and content-slug uniqueness across hero and rows. Non-subscribers get non-premium candidates. The separate verifier checks goal eligibility, holdout, duplicates, row shape/semantics, dialect and availability again at measured release time.

## Durable publication and actual storage failures

`Store.publish` stages the decision and optional action with `publication_state=pending`. After measured-time revalidation, `Store.release` commits their ready state. Ledger exports and local serving ignore pending entries. A process interruption before release is recovered as an abstention on reopening; it cannot expose an unchecked staged page.

`Engine.decide` catches actual SQLite and operating-system I/O exceptions across reads, ingestion, planning persistence and release. It rolls back, restores that viewer's in-memory snapshot, closes publication in the current engine instance, and writes an idempotent no-action decision to a separate JSON journal using flush, fsync and atomic replacement. Journal decisions survive reopening and supersede any interrupted primary outbox entry. If both stores fail, the error is visible rather than misreported as durable. A fresh replay is required after a genuine primary failure; control-cursor resume is not implemented.

Decision timestamps mark the final release request. `latency_observations.jsonl` separately measures method entry through completion of the final durable release, and the latency report uses that full value. This separates a transaction's assigned business timestamp from observed commit completion without losing the latter.

## Withdrawals

Withdrawal controls update availability, identify affected live pages, persist revocations, and attempt verified replacements for viewers with active plans. `current_page` rejects revoked or expired pages immediately; if no replacement is valid, it returns no personalized page so serving uses the platform default. Reopening the ledger preserves the revoked flags.

The provided simulator understands valid replacement pages but does not implement a pure revocation API. Its source stays unchanged. Tests validate the local serving contract, including the no-valid-replacement case. Production integration still needs an adapter for revocation acknowledgements and cache invalidation.

## Time, failures and scale

The provider and logical tools have configurable budgets, default 8 and 20. Provider 503s, malformed output, unsupported claims and timeout fixtures are bounded and fail safely. The named 45-second mock timeout is cancelled at 20ms. The degraded 8-second store fixture opens a conservative whole-window circuit. Actual SQL read/write failures are tested separately.

`load_test.py` queues a configurable burst at once and hashes viewers into isolated process shards, so a viewer is owned by one worker. Each shard has its own SQLite writer. Timings include process startup, pack loading, history ingestion, queue wait and durable release. The benchmark reports per-request observations, counts and deadline misses and fails if any selected request exceeds 60 seconds. It is not a shared-database, hosted-model, distributed-failover or ten-million-user claim.

## Measurement and learning

The adaptive agent's goals and the experiment's measurement goals are separate. Before the first intervention, `freeze_cohort` assigns a measurement goal to every randomized viewer using only already-arrived facts, with explicit no-goal cases. These goals do not change because treatment served or succeeded. Rule corrections apply only when a measurement goal was still open at correction time, using evidence available by that time.

Goal outcomes require attributable events inside committed windows: non-trial purchase for paid goals, the target slug for G07, release date for G08, and three IST dates for G09. Buffered evidence estimated to precede commitment is excluded. Incomplete windows and missing follow-up are inconclusive. Outcomes, evidence and conservative learning are saved to SQLite and per-viewer exports.

The primary report retains every randomized user and breaks out baseline goals. Because the simulator follows triggered users only, full-population point estimates are not identified. The report shows observed success/failure/inconclusive counts, worst-case missing-outcome bounds and a sampling envelope using Newcombe/Wilson limits at both extremes. Baseline eligibility is established before treatment; it is not served-only selection. Secondary recorded-completion contrasts have their coverage caveat. Pilot ITT uses randomized assignment and retains unserved treatment viewers.
