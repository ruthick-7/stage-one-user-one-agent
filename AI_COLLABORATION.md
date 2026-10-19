# How I used Codex

I worked with Codex to develop this project, combining my requirements, feedback and local checks with AI assistance for implementation, debugging, testing and documentation.

## My involvement

I provided the assignment and data pack, guided the project’s scope, and requested explanations of how each part works. I ran the original 16 tests and the full replay on Windows, shared the results, and requested a closer review of requirement coverage.

I also requested the website, account features and local setup instructions. I use [my review checklist](docs/OWNER_REVIEW.md) to record the code I have reviewed, tests I have run and changes I have made.

## How Codex assisted me

Codex provided substantial implementation assistance, including code generation for the Python agent, SQLite persistence, replay pipeline, verifier, reports, tests and website.

I used that assistance to develop the project iteratively: checking results, identifying gaps and requesting improvements. Automated tests and browser checks helped validate the implementation during development.

## What changed during development

Review and testing identified several issues that needed correction:

1. A missing-profile lookup changed a data-quality denominator. The lookup now leaves the collection unchanged.
2. Goal eligibility was checked against newer evidence. It now uses the commitment-time snapshot, while publication checks use current facts.
3. Buffered historical events affected follow-up measurement. They are now separated from simulator follow-up.
4. G07 relied on arrival order. It now selects the latest server-received play, with a regression test for late-arriving older events.
5. Storage tests initially missed actual SQLite failures. They now cover read, write and release failures, restart recovery and interrupted publication.
6. Measurement and performance checks needed broader coverage. The project now includes frozen baseline goals, missing-outcome bounds, burst timing and an independent artifact audit.

## My review and understanding

I keep my personal checks separate from automated validation results. My goal is to understand the evidence, decisions and failure paths well enough to explain the implementation and make changes confidently.

This project was developed collaboratively with substantial Codex assistance. These notes describe that process alongside my own involvement and review.
