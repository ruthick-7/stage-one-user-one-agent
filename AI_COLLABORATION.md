# AI collaboration

This project used substantial Codex assistance for implementation, documentation, debugging and test generation.

The project owner supplied the assignment and data, requested step-by-step explanations, ran the original 16 tests and full replay locally on Windows, reported the results, requested a requirement-by-requirement review, and asked for the identified gaps to be fixed. Those are real contributions. Local execution is useful verification; it does not establish a line-by-line review or independent implementation.

## What Codex helped produce

- The initial Python modules, SQLite ledger, replay pipeline, verifier, tests and learning guides.
- A comparison against the supplied brief, including defects the original tests missed.
- Fixes for receipt/delivery ordering, late series plays, real storage failures and interrupted publication.
- A separate recovery journal, local page revocation/rebuilding, baseline-goal measurement with missing-outcome bounds, a process-sharded load benchmark and independently audited sample artifacts.

## Corrections made during AI-assisted development

1. A missing-profile `defaultdict` lookup changed the data-quality denominator. Replaced it with a non-mutating lookup.
2. Active-goal evidence was compared with newer fact references. Anchored eligibility verification to commitment time while keeping publication checks current.
3. Historical buffered receipts contaminated a follow-up endpoint. Kept simulator follow-up separate and excluded behavior estimated to precede commitment.
4. G07 used arrival/insertion order rather than the latest server-received play. Added a regression where an older play arrives after a recent play.
5. Datastore tests originally covered a fixture flag but not real SQLite errors. Added read/write/release fault tests, durable abstention recovery and pending-outbox crash tests.
6. A successful replay was too easy to mistake for full requirement coverage. Added frozen baseline-goal measurement, explicit missing-data bounds, burst timing, sample artifacts and a separate artifact auditor.

These are documented corrections, not invented accounts of the owner rejecting suggestions. No human-authorship percentage is claimed.

## Owner review still to record

Use [OWNER_REVIEW.md](docs/OWNER_REVIEW.md). Add only checks and changes you actually perform: command, observed output, explanation, and any code revision you made. In discussion, distinguish what you implemented independently, what you adapted, and what Codex generated. The assignment explicitly permits AI assistance and evaluates understanding and verification.
