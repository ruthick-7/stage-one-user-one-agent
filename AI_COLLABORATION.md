# AI collaboration log

Codex read the user-supplied brief, guide, data pack and simulator, then generated this implementation and explanations. All implementation here is AI-assisted. The candidate has not yet independently reviewed or defended it; do not present this log as a human review that already happened.

Evidence of checks performed during this build:

- Executed behavioral tests for duplicate/restarted triggers, stale buffering vs fixed clock skew, profile/app/campaign conflicts, billing precedence, model and data failures, unsupported claims, rule corrections, holdout, withdrawals, row limits, consent, quiet hours, shared caps and budgets.
- Ran the supplied simulator unchanged and inspected its acceptance counts and policy problems.
- Inspected actual model-fault outputs, abstention reasons and effect denominators rather than assuming a successful process meant correct behavior.

Concrete AI-produced approaches corrected during implementation:

1. **Missing profiles changed a counter.** Using a `defaultdict` lookup for new viewers created empty profile lists; summing `len(rows)-1` then incorrectly reported negative duplicates. Changed reads to `.get(user, [])` and rechecked the measured count.
2. **An active goal's old references were compared with today's references.** Normal mock proposals were incorrectly rejected after a newer app setting arrived. Eligibility/evidence verification now anchors to the goal's commitment time; publication dialect remains checked at the current time.
3. **Historical buffered receipts contaminated a follow-up endpoint.** The initial seven-day report included historical receipts arriving after replay start. Restricted the fixed endpoint to simulator follow-up and separately kept attributable historical/live evidence for goal judging. Added a predicate excluding behavior estimated to precede goal commitment.

These are corrections made during AI-assisted execution, not examples of the candidate personally rejecting suggestions. Before submission, the candidate should read each module, run tests/replay themselves, add their actual review observations, and practice the concrete viewer trace in the discussion notes.
