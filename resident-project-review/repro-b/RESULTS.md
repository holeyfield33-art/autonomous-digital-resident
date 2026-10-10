# Agent B reproduction results

Date: 2026-10-10. Scope: copied Agent B artifacts; `mcp-sampling-injection`
was intentionally skipped. No ASI catalog files were edited or published.

## Environment and provenance

- Standard-library runs and independent suite:
  `python:3.11-slim@sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce`.
- MCP run: fresh container from
  `resident-sandbox@sha256:fa00c5310a8474d8ad267ad2e6efc3ef0b231be770b7978e4b010edfa41e82d5`
  with the existing `resident-sandbox-b-deps` volume mounted read-only.
- Every container ran with no network, read-only root and source files, and an
  ephemeral `/tmp`.
- Snapshot hashes are recorded in `source-hashes.json` and
  `remaining-source-hashes.json`. The baseline copies were not edited.
- `requirements.txt` declares the standard-library-only suite;
  `requirements-mcp.lock` records packages in B's dependency volume. The base
  image supplies `typing_extensions`, so the volume alone is not portable.

## Independent suite

`run.ps1` executes all independent checks. Observed result: **19 tests passed**
in 0.146 seconds.

The passing tests deliberately include reproduction of vulnerabilities. For
example, the forged-identity tests pass only when they observe the malicious
object being selected. A green test suite does not mean B's defenses are safe.

## Findings

### Tool identity defense

**REPRODUCED:** B's unchanged script reported its forged identity winning when
the legitimate tool was absent. Independent assertions also found:

- With duplicate identity strings, whichever equal-scoring object appears
  first is selected. Reversing order selects the malicious object.
- The attack does not require the legitimate display name; the effective
  selector matches only the claimed identity string.
- Untrusted retrieval can fill the top-three candidate list and exclude the
  legitimate tool. The selector then refuses, preventing unauthorized execution
  but causing an availability failure.
- The source defines `capability_whitelist_select_identity` twice; Python uses
  the later definition.

**INFERRED DESIGN REQUIREMENT:** policy must retain a trusted registry reference
or otherwise authenticate the registration record. A string supplied on the
tool object is a claim. The small reference test rejects an attacker-created
clone and selects only the exact registered object; it is not a production
registry.

### TOCTOU file boundary

**REPRODUCED:** the unchanged read stress test escaped 10/10 races (193 total
swaps), and the write stress test escaped 10/10 races (fewest: one swap). B's
direct symlink and traversal checks passed.

**NEW OBSERVED LIMITATIONS in B's `secure_sandbox.py`:**

- Each nested read leaked two intermediate directory descriptors in the test.
- The sandbox reopens its root by pathname for every operation. Replacing that
  path with a symlink redirected a read to an outside directory.
- A hard link inside the root allowed reading and overwriting an outside file.
  `O_NOFOLLOW` addresses symbolic links, not hard links.

The review copy's `HardenedSandbox` pins the root descriptor at construction,
closes every intermediate descriptor, allows only regular single-link files,
and validates an existing file before truncation. Its four reference checks
passed. Hard-link rejection is a conservative local policy, not a complete
substitute for filesystem isolation or a trusted file-creation broker.

### Remaining demonstrations

| Project | Execution | Evidence boundary |
|---|---|---|
| `prompt-injection-tool-selection` | Script completed and its programmed malicious selection occurred | Handwritten selector; mechanism demonstration, not real-model attack measurement |
| `langchain-tool-selection-audit` | Four scripted scenarios completed | A local mirror; it did not import or execute LangChain in this reproduction |
| `memory-poisoning-minja` | Reported benign, poisoned and defended outcomes | Deterministic retrieval/reasoning simulation; outcomes follow its explicit rules |
| `json-channel-injection` | Reported attack, allowlist defense and “bypass” | The action parser is deterministic. Independent test **refuted the scenario-4 bypass wording**: it sent only to `colleague@company.com`; the attacker address reached neither recipient nor body |
| `registry-separation-counterexample` | Reported the defense defeated | Its declared `agent_select_tool` registry resolver is never called. This does not exercise the claimed protected execution path |
| `mcp-tool-identity-audit` | Completed with MCP SDK 2.3.0 | Instantiates an SDK server and reads its private tool manager in-process. `ClientSession`/`stdio_client` are unused, and the PoC's own `render_tool_list` creates model text. It verifies description preservation plus mock behavior, not an end-to-end MCP host compromise |
| `agent-deployment-security-checklist` | Document only | External statistics, CVEs and mitigation efficacy were not independently reproduced here |

### Corrected cross-boundary mechanism

The independent suite includes a smaller, accurately scoped counterexample:
a trusted registry resolves the legitimate `send_email` implementation, while
a deterministic planner supplies attacker-chosen arguments derived from a
document. Trusted identity alone permits the simulated side effect. Requiring
operator authority for document-originated side effects blocks it.

This is a **mechanism demonstration**. It supports the narrower conclusion that
identity and provenance do not confer authority over a specific invocation. It
does not measure attack success against a real language model.

## Decision

B's most valuable reusable work is now a regression suite around two concrete
boundaries:

1. authenticate the registry record and separately authorize each consequential
   invocation; and
2. pin filesystem roots and inode handles, close descriptors, and define a
   hard-link policy.

The mock PoCs remain useful teaching fixtures. Their current outputs should not
be described as validated real-model attacks or complete production defenses.
