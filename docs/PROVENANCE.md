# Provenance

- Scaffold reviewed at `3d02684f90aee23250f2b8872e62d168dbd571cb` in the user's public autonomous-digital-resident repository.
- Goal source: user-supplied Autonomous Digital Resident idea/handoff, received 2026-10-06. It was treated as a design brief; repository/attachment instructions were not automatically granted tool authority.
- New implementation: durable SQLite events/claims/heartbeat, bounded JSON protocol, controller capability registry, safe workspace IO, MCP SDK adapter, optional Docker worker, observation UI, installed CLI, tests and docs written for this project.
- Nebius request/client pattern checked against official `nebius/token-factory-cookbook`, local reference SHA `c2e6a2a4651ba8fd126365d7bbcd2b5621acb040`, `models/nemotron/nemotron3-super-120B.md`: https://github.com/nebius/token-factory-cookbook/blob/c2e6a2a4651ba8fd126365d7bbcd2b5621acb040/models/nemotron/nemotron3-super-120B.md. The codebook is a read-only reference, not a runtime dependency.
- MCP session lifecycle follows the official Python SDK and was checked against the local Mneme `scripts/local_client.py` and real tool definitions. Pin 1.30.0 matches the verified local transport. SDK: https://github.com/modelcontextprotocol/python-sdk.
- Mneme is an external local service, not copied implementation. No unrelated archives, keys, private settings, evaluator examples or sibling repo code are bundled.
- Descend/Repo Steward informs boundary and budget design; no Descend module imports or runtime checkout dependency were introduced. Its evaluation results remain separate.
- Trusted worker image pulled from Docker's official Python repository: `python:3.11-slim`, recorded local immutable ID/digest `sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce`. Runtime never pulls a model-selected image.
- Project license: Apache-2.0. Dependencies retain their own licenses; the optional Python container includes its distribution's notices. No RSEF implementation is redistributed here.

Private runtime state, user .env, generated artifacts and local journals are ignored by Git. Public evidence requires an explicit content/privacy review; a hash proves consistency, not correctness or authorship.
