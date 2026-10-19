# Final report

In this replay, my agent recorded 2679 unique decisions; 917 home pages; 1762 abstentions.

Outcome judgments: {'failed': 1265, 'succeeded': 105}.

Local maximum decision latency: 48.40 ms. Simulator policy problems: 0.

I use data_quality.json to inspect input quality, audit.jsonl to trace control reactions, impact_report.md for randomized comparisons, and ../KNOWN_LIMITATIONS.md to explain the scope. My primary comparison is baseline-goal ITT with explicit bounds for missing outcomes. I handle page revocation and safe replacement locally; the supplied simulator has no revocation API. I keep outbound messages disabled and use a mock provider.
