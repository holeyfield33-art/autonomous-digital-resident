# Agent B independent reproduction

This directory preserves copied Agent B sources under `baseline/` and keeps
independent checks outside those copies. `source-hashes.json` records SHA-256
hashes for the snapshot taken on 2026-10-10.

## Environment

- Python 3.11
- Standard library only (`requirements.txt` intentionally declares no packages)
- Intended clean runner: pinned local image
  `python:3.11-slim@sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce`
- Network disabled, source mounted read-only, container root read-only, temporary
  `/tmp` filesystem

## Commands

Run the unchanged baseline:

```powershell
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m `
  -v "${PWD}/resident-project-review/repro-b/baseline/toolhijacker-defense-stress:/work:ro" `
  -w /work python:3.11-slim python stress_test.py
```

Run the independent security assertions:

```powershell
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m `
  -v "${PWD}/resident-project-review/repro-b:/work:ro" `
  -w /work python:3.11-slim python -m unittest -v test_identity_defense.py
```

The expected outcome is seven passing assertions. Two passes explicitly mean
the original defense was broken as claimed: an attacker-controlled object with
the trusted identity is selected when it is ordered first or the legitimate
tool is absent. A test run is evidence about this deterministic mechanism, not
evidence of attack success against a real model or production framework.

## Security interpretation

The original selector compares an identity string carried by an attacker-created
tool object. That field is a claim, not registry-backed identity. With duplicate
claims it returns the first matching candidate, so stable ordering determines
whether the legitimate or malicious object wins.

Retrieval creates a separate availability problem: attacker-controlled metadata
can fill the top-k candidate list and exclude the legitimate tool. Safe refusal
prevents unauthorized execution but still denies the requested operation.

`TrustedRegistryReference` is a deliberately small boundary test. It shows the
required property: policy points to the trusted registry object and refuses an
attacker-created clone. It is not a production registry or a claim that all
attacks are solved.

## Current execution status

The consolidated independent suite passes 19 checks. See `RESULTS.md` for the
observed baseline runs, new defects, claim corrections, and evidence limits.
Use `run.ps1` to repeat the independent suite in the pinned offline container.
