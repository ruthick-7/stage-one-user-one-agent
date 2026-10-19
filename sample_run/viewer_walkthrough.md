# How I trace a viewer through this run

Viewer `U-02825`, decision `D-d3336a57-97db-43cb-92eb-5dc1e6690578`.

1. Trigger `d3336a57-97db-43cb-92eb-5dc1e6690578` arrived at `2026-09-30T19:04:41.737Z`.

2. App dialect `d1` came from `app_setting:event:d3336a57-97db-43cb-92eb-5dc1e6690578`. I check the conflicts and source ages in the decision record.

3. Goal `G02` (first_full_episode_3d) started `2026-09-30T19:04:41.737000Z`, with deadline `2026-10-03T19:04:41.737000Z`. Its signal is `episode_completed`.

4. Home page action `A-d3336a57-97db-43cb-92eb-5dc1e6690578` passed the independent checks. I can trace its hero and genre rows in actions.jsonl.

5. Judgment: `succeeded`. Event `oua-017658` was `episode_completed` at `2026-10-03T16:22:50.000Z`, inside the goal window.

6. I count this as observed goal success. To assess impact, I turn to the randomized-arm report; this single outcome cannot establish causation.


Open `viewer_state/U-02825.json`, decisions.jsonl, actions.jsonl, outcomes.jsonl and sim/outcome_events.jsonl to locate these records.


## Abstention example

Viewer `U-03644`, trigger `163209cc-c061-449e-9451-d250a7954846`, estimated age 228588.402 seconds. Reason: `stale_trigger_over_600s`. My agent takes no action for this trigger.
