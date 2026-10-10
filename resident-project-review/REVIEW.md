# Resident project selection review

Date: 2026-10-10. Scope: named Agents A, B, D. Agent C excluded. Read-only source/document review plus primary-source market/specification checks; no project tests rerun. Resident workspaces are live and may change.

## Recommendation
First invest a bounded validation pass in B/toctou-sandbox-escape. Its real filesystem mechanism is independently falsifiable, locally relevant, and reusable. Treat it as a file-access regression suite and hardening contribution, not a novel container escape or a proven commercial product. Second choice: D/smell-genome, focused on actionable per-commit function changes. If the immediate priority is earning via service delivery, A/support-triage is the best pilot, conditional on a real customer problem.

## Agent A: income-oriented automations
Seven workflow directories now exist (README/consciousness counts lag inventory).

| Project | Assessment | Decision |
|---|---|---|
| support-triage | Webhook -> AI classification -> parsing -> Slack. Understandable use case. No demonstrated real n8n end-to-end execution or customer demand. Parser may lose source fields after AI output; webhook body mapping needs checking; parsing failure becomes plausible default classification. | Best A pilot for custom service; no standalone template business yet |
| sentiment-analysis | Feedback classification and alert filtering. Useful extension to triage but no distinct demand evidence. | Merge into triage later |
| invoice-extraction | Text extraction -> AI -> Slack, not full document/accounts-payable workflow. Number(total) || 0 can hide missing/invalid amounts. No demonstrated reconciliation, duplication protection, or realistic document evaluation. | Defer unless actual client supplies examples |
| abandoned-cart-recovery | Three-node immediate email pipeline. No wait/purchase recheck/deduplication; sendRecovery flag is computed but not used to gate email. | Defer; incomplete recovery semantics |
| lead-gen-real-estate | Scrapes property cards; inserts generated @example.com email and 555-000-0000 phone. Property listings are not contactable customer leads. | Stop pursuing current design |
| social-media-content-repurposing | YouTube search/page fetch -> AI -> Slack. HTML fetch is not proof of transcript extraction; no demonstrated freshness/deduplication. | Defer; use operator-provided source text if revisited |
| cv-screening-ai | AI scores CVs and notifies recruitment. Script tests do not show screening quality; no evaluated rubric/calibration. | Defer; avoid expanding before evidence |

Pricing, profiles, pitches, and outreach copy are collateral, not revenue or demand validation. Official n8n catalog already has support triage, sentiment, and invoice workflows. This establishes alternatives, not absence of demand for customized service.

## Agent B: security research and demonstrations

| Project | Assessment | Decision |
|---|---|---|
| toctou-sandbox-escape | Real filesystem read/write race examples plus directory-relative O_NOFOLLOW defense. Defense source leaks intermediate directory descriptors on nested paths; root is reopened by name per call despite stronger prose; hardlinks, moved directories, and special files need explicit scope/tests. Demonstrates escape from its own path restriction, not a Docker escape. | First technical validation investment |
| prompt-injection-tool-selection | Handwritten selector demonstrates metadata influence. Script behavior does not establish real-model vulnerability or general defense efficacy. | Educational fixture |
| toolhijacker-defense-stress | Useful negative result: name/identity defenses can depend on ordering or forgeable strings. Narrow hardcoded task routing is not a general agent defense. | Merge into one adversarial harness |
| langchain-tool-selection-audit | Source observations plus mirror renderer/mock selector, not actual exploited production agent. Broad claims require version-specific integration and threat model verification. | Harness input, not standalone product |
| mcp-tool-identity-audit | SDK-based metadata demonstration with mock model. Shows metadata transport, not successful compromise of independent host policy. | Harness input |
| memory-poisoning-minja | Deterministic retrieval/reasoning simulation; attack and defense outcomes are encoded in logic. No independent model evaluation. | Educational fixture; defer major build |
| mcp-sampling-injection | Real transport scaffold with mock completion returning a hardcoded synthetic secret. No README in root. Protocol allows client control and prompt review; unsafe custom callback is not proof of inherent protocol compromise. | Reframe claims before investment |
| agent-deployment-security-checklist | Useful document but source claims need verification; no automated audit implementation. | Supporting documentation |

B has useful test material, not eight independent products. If expanded beyond TOCTOU, consolidate into one local regression harness with real integrations, synthetic secrets, explicit baselines, and held-out attack cases.

## Agent D: inventions

| Project | Assessment | Decision |
|---|---|---|
| smell-genome | Largest coherent CLI: profiles, comparisons, history, drift, lineage, clustering; separate Python/JS/Java port analysis. Silent parse failures and absent dependency manifests undermine confidence. Port score weights chosen on showcased pairs require held-out testing. Health/ancestry conclusions exceed numeric-output evidence. | Second choice; narrow to commit-local actionable changes |
| code-symphony | Concrete Python metrics -> WAV/JSON. Omits async functions; nested-function counting can inflate parent metrics. No perceptual evidence humans find issues more effectively. | Short demo only unless listening study is promising |
| inventor-foundations | Introductory README only. | No build investment |

## First project decision gates
B/TOCTOU: snapshot authored files; reproduce legitimate reads/writes and attack within temporary directories; independently check nested symlinks, fd lifecycle, hardlinks, root replacement, and platform assumptions; fix reproduced defects in review copy; compare findings with controller implementation. Continue only if reusable tests or an actual local hardening improvement result.
D/Smell Genome: continue if it surfaces real changed functions maintainers find actionable beyond existing complexity reports. Do not start by expanding cross-language ancestry claims.
A/triage: continue if an operator/client supplies a workflow and representative tickets; demonstrate real engine execution, source-field preservation, failure routing, human-reviewed drafts, and measured time saved. Do not build more templates first.

## Primary sources checked
- https://n8n.io/workflows/19465-triage-and-route-ai-powered-support-tickets-with-google-gemini-trello-and-gmail/
- https://n8n.io/workflows/19052-extract-structured-invoice-data-from-text-with-openai/
- https://n8n.io/workflows/10218-analyze-event-feedback-with-sentiment-analysis-google-sheets-slack-and-email/
- https://www.sonarsource.com/solutions/maintainability/
- https://modelcontextprotocol.io/specification/2025-06-18/client/sampling

These sources establish existing alternatives and protocol controls. Rankings and investment decisions are reviewer judgments, not verified market forecasts. No customer, revenue, independent security certification, or newly reproduced test success is claimed.
