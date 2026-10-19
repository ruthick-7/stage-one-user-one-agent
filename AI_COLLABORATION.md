# How I used Codex

I used Codex extensively for implementation, debugging, tests and documentation. This project reflects that collaboration. I keep this note alongside the code so the development process is clear.

## My involvement

I supplied the assignment and data pack, asked for a step-by-step explanation, and ran the original 16 tests and the full replay on my Windows machine. I shared the results, asked whether the project covered the requirements, and requested a closer review and fixes. I also requested the website and local setup instructions.

Those local runs helped me check the earlier version. My later review notes belong in [my review checklist](docs/OWNER_REVIEW.md), where I can record exactly what I have read, tested or changed.

## Where Codex helped

Codex generated substantial parts of the Python implementation, SQLite ledger, replay pipeline, verifier, tests and documentation. It also helped compare the implementation with the brief and fix gaps that the original tests had missed.

That work included delivery ordering, late series plays, actual storage failures, interrupted publication, a separate recovery journal, local page revocation and replacement, baseline-goal measurement, missing-outcome bounds, the load benchmark and the artifact auditor.

For the website, Codex helped produce the frontend, local account and session backend, viewer and report APIs, background replay jobs, setup guide and tests. Automated browser checks covered sign-up, sign-in, navigation, reports and a full replay.

## What needed correction

The first implementation passing its tests did not mean every requirement was covered. These issues came up during development:

1. A missing-profile `defaultdict` lookup changed a data-quality denominator. The fix uses a lookup that leaves the collection unchanged.
2. Active-goal evidence was compared with newer fact references. Eligibility is now checked against the commitment-time snapshot, while publication checks use current facts.
3. Buffered historical receipts leaked into a follow-up endpoint. Simulator follow-up is now kept separate, and behavior estimated to predate commitment is excluded.
4. G07 used arrival order instead of the latest server-received play. A regression test now delivers an older play after a more recent one.
5. The original storage tests covered a fixture flag, but missed real SQLite errors. The suite now covers read, write and release failures, recovery after reopening, and interrupted pending publications.
6. A successful replay left measurement and performance gaps. Frozen baseline goals, missing-data bounds, burst timing and an independent artifact audit make those gaps easier to inspect.

## How I use this for review

I use [OWNER_REVIEW.md](docs/OWNER_REVIEW.md) to separate checks I have personally completed from automated checks run during development. For a technical discussion, I need to understand the evidence, decisions and failure paths well enough to explain them and make changes. The assignment allows AI assistance; this record makes that assistance explicit without assigning an unsupported authorship percentage.
