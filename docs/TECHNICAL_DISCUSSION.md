# My technical discussion notes

Here is how I would explain my project in about 30 seconds:

> Each viewer has one active, measurable goal with a deadline. I resolve facts using source-specific rules and preserve conflicts and freshness. A planner proposes a home page, and a separate verifier can reject it. Decisions and actions are idempotent in SQLite. Replay includes failures and corrections. Outcomes are judged only inside goal windows, and impact uses randomized arms with explicit coverage limits.

I use these questions to prepare explanations of the implementation. They describe the system as it stands; [my review notes](OWNER_REVIEW.md) track which paths I have checked personally. [My collaboration log](../AI_COLLABORATION.md) records where Codex helped.

## Questions I want to be ready for

**Why is this an agent rather than only a recommender?**
I track the viewer's goal and its state transitions across visits. A ranked title list is one possible intervention. The system also abstains, revises a goal after billing, tracks actions and judges outcomes. A recommendation function alone would not own the deadline, evidence or measurement loop.

**How do you know a fact is fresh enough?**
I keep a source, timestamp and age with each fact. Billing and consent have different rules from dialect. Subscription-dependent eligibility uses a 48h freshness limit; app dialect comes from arrived settings. History-based absence is explicitly bounded to the observed pack. The 48h value is my conservative baseline assumption and should be validated with product owners.

**What if profile, app and campaign disagree?**
The app's setting controls which page is requested, so it wins for dialect. I keep the conflicting alternatives visible in the state. A campaign link cannot grant consent or change subscription status. New authoritative billing receipts can override a stale profile for billing.

**Why do nothing?**
A stale buffered visit is not evidence of a live session. Holdout must remain untouched. Missing required facts, no eligible measurable goal, insufficient valid content or a failed verifier all justify abstention. I can look up the exact reason in the decision record.

**Can the verifier reject the model?**
Yes. The unsupported-trial fixture is rejected without supporting evidence. Malformed output and timeout fall back to deterministic logic. Any fallback still passes the same publication gate. A confidence value is not evidence or permission.

**Why only home pages?**
I kept home pages as the baseline because they let the project close the full loop during an active visit. Outbound generation, scheduling, secure structured copy rendering and cancellation are not implemented. I would enable a channel only after those contracts and tests exist. This is a scope tradeoff, not a claim to support all actions.

**How do you handle duplicate triggers after a crash?**
I use the event ID as a durable idempotency key; decision IDs and action IDs are derived from it, and SQLite uniqueness prevents a second action. Restart tests verify it. The outbox exposes only ready entries; a crash before release becomes an abstention. Actual SQLite failures are written to a separate durable no-action journal and close publication in that engine instance. Full timeline resume and external exactly-once delivery still need a platform integration.

**What happens when a goal's success rule is corrected?**
The correction is applied only to the named goal type's open instances, with a new version. Already settled goals remain under their original interpretation. No unrelated viewer is replanned. Tests verify unchanged non-target and closed records.

**What happens after a purchase?**
The event updates subscription facts and closes a conversion goal if the purchase is a valid success, or invalidates an incompatible goal. The viewer selects a replacement from current evidence. No message is sent from that billing event; actions remain trigger-driven. This baseline has no outbound queue to cancel.

**What if a title is withdrawn after publication?**
The control revokes affected local pages immediately and attempts a verified replacement. If no replacement is valid, local serving falls back to default. The provided simulator does not model pure revocations, so regression tests exercise that serving contract directly. A production adapter must apply revocations and invalidate caches.

**How do you prove causation?**
I freeze measurement goals before intervention, separately from the adaptive policy, and compare randomized arms including abstentions. Missing follow-up remains inconclusive; the report gives bounds rather than a misleading full-population point estimate. Served vs unserved conditions on a post-randomization selection and is biased. One viewer's in-window success is attribution in time, not proof of causation. The report's untriggered observation gap also limits its estimand.

**Why a confidence interval?**
A point difference can be noise. The report uses Newcombe differences of Wilson score limits for two binary rates, which behave sensibly even with zero successes. Small goal subgroups have wide intervals. These intervals do not include simulator uncertainty, missing-data uncertainty, or multiple subgroup testing.

**What would you do for 1,000 opens in a minute?**
I would partition by viewer ID so one owner processes each viewer's events in order. I would use cached immutable catalogue indexes, bounded queues, request deadlines and circuit breakers. Under pressure, I would prioritize fresh sessions and skip optional model work, then measure queue plus service latency under load. The included four-process burst benchmark measures actual local queue-to-release timing for 1,000 submitted triggers. It demonstrates this mock-provider/sharded-SQLite setup, not real provider or shared-database capacity.

**What changes for 10 million users and 40 dialects?**
I would replace per-process dictionaries and the single SQLite writer with a partitioned event log and durable keyed state service; version catalogue indexes per dialect; enforce shared caps and idempotency atomically; use an outbox with delivery acknowledgements; build a reverse index for correction/withdrawal impact; sample audits and monitor latency, coverage, opt-outs and randomized metrics. I would keep deterministic gates close to publication.

**Which actions should not be automated?**
Unsupported eligibility, new prices/offers, inferred consent, ambiguous success definitions and overrides of holdout/policy need authoritative decisions. The baseline must abstain rather than let a model invent authority.

**What did AI assistance get wrong?**
My collaboration log records the corrections made during development: missing-profile lookup mutated a counter; active-goal evidence was compared against newer fact references; historical buffered receipts contaminated a follow-up endpoint. Before presenting these as paths I understand, I need to read the code, rerun the relevant tests and record my own observations.

## My preparation checklist

1. Run the tests locally and inspect one failure by modifying a fixture in a scratch copy.
2. Follow the [concrete viewer trace](../sample_run/viewer_walkthrough.md) from evidence to action to judgment.
3. Explain a no-action viewer too; do not only demonstrate a successful page.
4. Read the exact impact estimate and interval from my own run, including missing-outcome bounds.
5. Explain what still needs work: outbound messaging, external platform delivery and production-scale validation.

## Generated worked example

I use [sample_run/viewer_walkthrough.md](../sample_run/viewer_walkthrough.md) as a worked example. It selects a successful published goal from the current run using actual decision, action and outcome IDs, and includes a stale-trigger abstention. The viewer is not hard-coded.
