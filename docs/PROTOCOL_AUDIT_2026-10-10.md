# Resident protocol audit ? 2026-10-10

Audited the local SQLite event records for residents a?d and the active K1 team.
All eight recorded DeepSeek-V4-Flash-0731 responses. Before this maintenance,
there were 13 terminal protocol failures: a=2, b=2, c=3, d=4, k1a=1, k1c=1.
The audited stores had no provider_error events. These failures were JSON
format violations in returned model content, not evidence of a transport outage.

The two K1 failures contained missing action-object closing braces. Repeated
repair requests reproduced them. Other historical failures included prose,
unescaped quotes and malformed/truncated output. The controller also truncated
repair input to 6,000 characters, potentially discarding the content to repair.

Changes:
- Recover missing action braces only after complete name and arguments values,
  decoded by Python's JSON decoder. Validate the complete decision before use.
  Also close a missing outer brace immediately after a complete actions array.
  Do not invent missing strings, argument values, or array closures.
- Record each recovery in decision_normalized.
- Preserve the full reply for model repair, explain the required nested braces,
  and strengthen the second attempt. Preserve the two-attempt limit and ledger.
- Record finish_reason on repaired responses as well as initial responses.

Offline replay of the last rejected response in each failed wake now recovers
12 of the 13 historical terminal failures, including both K1 failures, without
executing any recorded actions. The remaining historical failure still requires model repair.
Live verification additionally caught a missing outer brace on K1 D; the final
fix recovers all three recorded attempts from that failure in offline replay.
Regression tests cover argument preservation, ambiguous/truncated rejection,
and repair input longer than 6,000 characters.

The active K1 team was stopped through the controller and restarted with the
same model, endpoint, price settings, 900-second interval, 16 steps, sandbox,
team directory, identities and $15 per-resident durable budget caps. Existing
state and workspaces were retained. Earlier a?d residents were not restarted.

Limitation: unconstrained model output can still be malformed. This change
handles the verified structural failure and improves repair; it does not
promise that every future provider response will be valid.

Validation: 92 tests passed, two Docker-dependent tests skipped; Ruff passed.

Final live check after the final restart (cycle 4): K1 A and B completed;
K1 C and D were still running. Across the four agents, 35 decisions had been
accepted with zero protocol_error, provider_error, or controller error events
in that cycle at the check. This is a short observation, not a long-run guarantee.
