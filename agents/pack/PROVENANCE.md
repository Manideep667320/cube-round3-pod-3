# Provenance

Round 3 Pack Manager is the Round 2 Pack Manager adapted into the CUBE Round 3 Pod contract.

Round 2 repository:
https://github.com/Cube-Build-A-Thon/cube-03-pack-manager

Round 2 commit:
REPLACE_WITH_YOUR_ROUND2_COMMIT_SHA

Round 3 adaptations:
- `handle()` Agent Input → Agent Output adapter
- shared evidence/output builders
- deterministic verification separated from vision observation
- one batched model call per unit
- fail-open model errors
- explicit UNCERTAIN handling
- content-addressed input references
- tenant guard and deterministic request-to-record IDs
