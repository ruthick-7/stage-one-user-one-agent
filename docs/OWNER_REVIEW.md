# Owner review and technical ownership

The assignment permits AI tools. The strongest preparation is being able to explain and check the submitted system yourself. Record actual work here; do not change authorship claims to create an impression unsupported by the development history.

## Work already reported by the owner

- Ran the original 16 tests on Windows: all passed.
- Ran the full practice replay after fixing the local data-pack path.
- Shared the final report and asked whether the results and requirement coverage were adequate.
- Requested an implementation review and fixes for the gaps it found.

## Suggested review exercises

For each exercise, predict the result first, run it in a separate output directory or scratch copy, then write down what happened and why.

1. Read `goals.py`. Explain why a late-delivered older play must not replace a more recent server-received play. Run the corresponding regression test.
2. Read `recovery.py` and the pending/ready paths in `store.py`. Explain what survives a process restart and why a storage error cannot authorize an action. Identify the remaining same-machine durability limitation.
3. Inspect one published and one abstained viewer in `sample_run/`. Find the underlying event IDs, app dialect, goal deadline and outcome predicate.
4. Read `cohort.py`. Explain why measurement goals are frozen before intervention and why a missing simulator outcome is not a failed goal.
5. Change a synthetic fixture's arm to holdout, or withdraw its hero. Predict whether an action can still be served. Run the test.
6. Run `load_test.py`. Explain what end-to-end timing includes and why a four-shard mock benchmark does not prove real model or shared-database performance.
7. Make one small improvement you can defend, add its regression test, and document your own reasoning.

## Review record template

Copy this only when completing a real review:

```text
Date:
File/function reviewed:
Prediction or concern:
Command/test run:
Observed output:
Explanation in my own words:
Change I made (if any):
Remaining uncertainty:
```
