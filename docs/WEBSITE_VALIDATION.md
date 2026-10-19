# Website validation

The website was tested in the Linux development environment with Chromium. The existing Windows/Linux GitHub Actions matrix runs the standard-library unit and HTTP tests; no unobserved CI result is claimed.

## Automated checks

```bash
python -m unittest discover -s tests -v
node --check web/app.js
```

The suite contains **40 tests**: the existing 29 agent/replay tests and 11 website tests. Website coverage includes protected endpoints, salted password hashing, hashed session storage, cookie attributes, duplicate emails, invalid credentials, session expiry/persistence, CSRF/origin rejection, password changes and session revocation, per-account run isolation, report allowlisting, seed validation, missing-pack errors, rate limits and sample-backed metrics.

Node is used here only to check JavaScript syntax during development; it is not needed to run the website.

## Browser checks

An optional repeatable browser check is included:

```bash
# Development-only dependencies; unnecessary for normal website use.
python -m pip install playwright
python -m playwright install chromium
python scripts/browser_smoke.py --url http://127.0.0.1:8000
```

Run a separate website instance with a separate `--data-dir` when creating automated test accounts. On a development machine with an existing Chromium executable, the script also accepts `--browser-path`.

Validated flows:

- Create an account, load the dashboard and retain the session across refresh.
- Search for a real synthetic viewer and inspect the decision timeline.
- Read randomized experiment results, including uncertainty and missing follow-up.
- Preview and download a report.
- Edit the account name, change its password, sign out and sign back in.
- Navigate at desktop width and 390px mobile width, with no horizontal page overflow.
- Open and close the mobile navigation.
- No uncaught JavaScript errors in these checks.

## Full website replay

A replay was launched through the browser UI with seed `web-ui-check`. It reached completed state only after the CLI and independent auditor succeeded, then opened successfully in the dashboard. Its audit verified **2,679 decisions, 917 actions and the complete 5,000-user randomized cohort**, with no artifact errors. The simulator reported zero policy violations.

Both the basic browser check and its `--run-replay` variant passed with zero uncaught JavaScript errors. The optional browser script's `--run-replay` flag exercises the same background pipeline. It requires the original assignment data pack and may take longer on a different computer.

## Limits

These checks establish local browser/API behavior. They do not establish internet deployment, production HTTP-server suitability, real email verification/recovery, distributed authentication, multi-server jobs or streaming playback. Runtime accounts and generated private jobs are local and excluded from Git. The UI presents historical synthetic replay data, not live production viewing.
