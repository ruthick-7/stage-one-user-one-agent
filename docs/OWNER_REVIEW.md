# My review notes

I use this page to keep track of what I have checked myself and what I still need to understand. The automated validation results are in [VALIDATION.md](VALIDATION.md) and [WEBSITE_VALIDATION.md](WEBSITE_VALIDATION.md); they are separate from my personal review record.

## What I have already checked

- I ran the original 16 tests on Windows, and all passed.
- I ran the earlier full practice replay after correcting the local data-pack path.
- I shared that run's final report and asked whether its results and requirement coverage were adequate.
- I requested a closer implementation review and fixes for the gaps it found.

These notes refer to the earlier version. I still need to record my own checks of the revised implementation and website below.

## My next review steps

Before each check, I will write down what I expect. Then I will run it in a separate output directory or scratch copy and compare the result with my prediction.

- [ ] Read `goals.py` and explain why an older play delivered late must not replace a more recent server-received play. Run its regression test.
- [ ] Follow the recovery journal and pending/ready publication paths in `recovery.py` and `store.py`. Explain what survives a restart and what happens if both stores fail.
- [ ] Trace one published page and one abstention in `sample_run/`, including the source events, dialect, goal deadline and outcome predicate.
- [ ] Read `cohort.py` and explain why measurement goals are frozen before intervention and missing follow-up remains inconclusive.
- [ ] Change a synthetic fixture to holdout, or withdraw its hero. Predict the action before running the test.
- [ ] Run `load_test.py` and explain exactly what its timing includes, along with the limits of the mock provider and separate SQLite shards.
- [ ] Make a small improvement I can explain, add an appropriate regression test, and record my reasoning.

## My review record

I will copy this template for each completed review:

```text
Date:
File/function I reviewed:
What I expected or wanted to check:
Command/test I ran:
What I observed:
How I explain the result:
Change I made (if any):
What I still need to check:
```
