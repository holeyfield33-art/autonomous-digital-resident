$ErrorActionPreference = 'Stop'
$reviewRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$image = 'python:3.11-slim@sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce'

docker run --rm --network none --read-only `
    --tmpfs /tmp:rw,noexec,nosuid,size=128m `
    -v "${reviewRoot}:/work:ro" -w /work $image `
    python -m unittest -v `
        test_identity_defense.py `
        test_toctou_defense.py `
        test_claim_boundaries.py

if ($LASTEXITCODE -ne 0) {
    throw "Agent B reproduction suite failed with exit code $LASTEXITCODE"
}
