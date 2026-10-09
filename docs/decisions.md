# Decisions

Every non-obvious design choice gets one entry, so a reviewer can see **what you chose, why, and what you rejected.** Newest last. This is where *Decision quality* and *Orchestration* in the [rubric](../ROUND3-RUBRIC.md) are won or lost. It is not meant to become a long report: a few lines per decision.

Write an entry whenever you: change the flow or its policies; change how the orchestrator stores state or evidence; change the final-outcome or status rules; choose a communication mechanism; decide how retries and overrides work; pick a side on a **known finding** (below); add to the contract's `payload`; or choose a deployment shape.

## Template

```text
### D-NNN · Short title
- Date / Owner:
- Context: what forced a decision?
- Options considered: A, B, C
- Decision: what we chose
- Why: the evidence or reasoning
- Consequences: what gets easier / harder; what would make us revisit
```

## Questions your Pod's decisions should answer

- Why this orchestration approach, and who owns what in it?
- Why this communication mechanism (in-process, HTTP, queue)?
- How is workflow state stored, and how does it survive a restart?
- How are retries, timeouts and resume handled?
- How is evidence persisted, and how is its immutability enforced?
- How are overrides captured, referenced, and used downstream?
- What do we do about UNCERTAIN: continue or block, and who decides?
- How does the final outcome treat weak or uncertain evidence?

## Starter decisions (made by the organisers; change them with a new entry)

### D-000 · The default flow is routed, not strictly sequential
- Context: the Round 2 sample gives each unit a Prep record *or* a Pack record, never both, and Returns only for returned units.
- Decision: `flow.json` routes FBA units through Prep, merchant-fulfilled units through Pack, and runs Returns only when a return happened. A stage that does not apply is `skipped` with the reason recorded.
- Why: forcing every unit through all five stages would invent evidence. Units with neither route (F-12) skip both.

### D-001 · The orchestrator owns state; status and outcome are derived
- Decision: workflow status and final outcome are pure functions of the stored evidence and the overrides (`orchestration/rollup.py`). Agents return evidence and a recommendation; they never write state.
- Why: "the latest agent outcome" and "Recovery's reading of it" are not the source of truth; the traceable evidence chain is.

### D-002 · UNCERTAIN continues by default; blocking is a policy
- Decision: `on_uncertain: continue` by default; `block` halts only when the UNCERTAIN result asks for a person (`needs_human`). Either way the workflow is `BLOCKED` with outcome `NEEDS_REVIEW` until an override resolves it.
- Why: a warehouse line must not wait, and the evidence of later stages is not lost. Recovery's SILENT (UNCERTAIN, `needs_human: false`) must not halt anything.

### D-003 · Failures are recorded, never hidden; never success
- Decision: a failed stage gets a degraded evidence record (no checks, UNCERTAIN, the error) and the workflow ends `FAILED` / `INCOMPLETE` (`provisional`). `resume` retries it and keeps the failed attempt's evidence.

### D-004 · Overrides are workflow entries that reference evidence
- Decision: evidence is immutable. A person's override is appended to the workflow's `overrides` with actor, reason, timestamp, the record it supersedes, the previous effective verdict and the new one. The latest wins; downstream agents receive them in `context.overrides`.

### D-005 · Zero-amount reimbursements are not claimable (F-09)
- Decision: the Recovery stub treats a 0.00 line as SILENT. Why: claiming $0 is meaningless and the meaning of 0.00 is unresolved.

### D-006 · Field names (F-15)
- Decision: `check_key`, `detail`, `content_hash`, `latency_ms`, `client_id` follow the Round 2 Returns list; `org_id`, `operator_id`, `inputs`, `model.version` follow the CSVs. Mapping in [`EVIDENCE-CONTRACT.md`](../EVIDENCE-CONTRACT.md). Open for the organisers.

## Known findings carried over from Round 2

Round 2 participants raised these contradictions and gaps in the shared data and documents. They are **open**: the organisers will rule on them. Until then **do not silently pick a side**: add an entry above with your assumption, and design so that changing it is cheap. `F-07` to `F-12` match the issue numbers on the Round 2 Recovery repo.

| ID | Finding | Why it matters for integration | Source |
|---|---|---|---|
| **F-07** | 42 of 61 sample fee lines are `fulfilment_fee_weight_tier`, and no upstream sample records measured weight or dimensions. | Recovery can only mark these SILENT. Prep is the natural source: see `payload.measurements`. | [Recovery #7](https://github.com/Cube-Build-A-Thon/cube-05-recovery-manager/issues/7) |
| **F-08** | `unit_id` means a **PO line** in Receiving (RCV-0003: 48 ordered, 44 received) but a **single unit** in the fee report. UNIT-0003 is lost inbound, then charged a fulfilment fee, then returned: that cannot be one physical unit. | Joins on a bare id can be wrong. The contract adds `subject.unit_scope` and `subject.refs`. | [Recovery #8](https://github.com/Cube-Build-A-Thon/cube-05-recovery-manager/issues/8) |
| **F-09** | A `lost_inbound` adjustment is posted with `amount_usd` 0.00. "Not reimbursed" (a claim to raise) or "amount missing"? | The answer flips the verdict. See D-005. | [Recovery #9](https://github.com/Cube-Build-A-Thon/cube-05-recovery-manager/issues/9) |
| **F-10** | Receiving shortfalls are supplier-side and happen before goods reach the channel, so they cannot support a channel `lost_inbound` claim. | Keep supplier shortfall and channel loss separate in your decision logic. | [Recovery #10](https://github.com/Cube-Build-A-Thon/cube-05-recovery-manager/issues/10) |
| **F-11** | Returns records exist for FBA-routed units (UNIT-0003 has a Prep record **and** a seller-side Returns record). Do FBA returns come back to the seller or to the channel's warehouse? | Decides whether Returns evidence can contradict `refund_issued_item_not_returned`. | [Recovery #11](https://github.com/Cube-Build-A-Thon/cube-05-recovery-manager/issues/11) |
| **F-12** | 9 of the 100 sample units have neither a Prep nor a Pack record, although each unit is meant to take one route. | The starter marks these `route: "unknown"` and skips both stages. Recovery's SILENT rate depends on it. | [Recovery #12](https://github.com/Cube-Build-A-Thon/cube-05-recovery-manager/issues/12) |
| **F-13** | The Round 2 rules said the organisers would provide an official evidence contract. None was published, and one participant's v0 proposal was withdrawn pending it. | **Resolved for Round 3:** [`EVIDENCE-CONTRACT.md`](../EVIDENCE-CONTRACT.md) v1.0. | [Receiving #4](https://github.com/Cube-Build-A-Thon/cube-01-receiving-manager/issues/4), [Recovery #13](https://github.com/Cube-Build-A-Thon/cube-05-recovery-manager/issues/13) |
| **F-14** | The Round 2 repos do not all carry the same rules: Receiving, Prep and Recovery share one short `RULES.md`; Pack's differs in wording; Returns has a much longer one (field names, evaluation method, mandatory LinkedIn post) that also ends mid-sentence. | Round 3 carries over the **union**; the organisers should confirm which is authoritative and finish the truncated section (presumably how Round 2 counts towards the final result). | [Returns `RULES.md`](https://github.com/Cube-Build-A-Thon/cube-04-returns-manager/blob/main/RULES.md) |
| **F-15** | The only organiser-authored list of "official evidence contract" fields is in the Returns repo (`organization_id`, `operator_label`, `images`, …) and is "concepts such as", not a schema. The sample CSVs use `org_id`, `operator_id`. | v1.0 uses a mix; see D-006 and the note at the top of [`EVIDENCE-CONTRACT.md`](../EVIDENCE-CONTRACT.md). | [Returns README](https://github.com/Cube-Build-A-Thon/cube-04-returns-manager/blob/main/README.md) |

### Raising a new finding

A contradiction between documents or data is a **finding**, not a failure. Open an issue on your Pod's repo with the `finding` label: what contradicts what, an example row, and what you assumed (and add the assumption above). Good findings are credited under *Decision quality*.

## Your Pod's decisions

_Add entries below._

### Receiving v2 — 2026-10-09 (@gayathri2665)

| # | Decision | Trade-off |
|---|---|---|
| R-1 | `decision.verdict` is always `rollup(checks)`; the plan's ACCEPT/QUARANTINE/REJECT/ESCALATE vocabulary lives in `decision.outcome` + `payload.plan_verdict` | schema only allows PASS/FAIL/UNCERTAIN; consumers needing the physical action read outcome + reasons |
| R-2 | Checks are emitted only when actually judged (no `carton_count` / `unit_damage` filler) | an always-UNCERTAIN filler check would make ACCEPT unreachable; recommended check keys are optional per contract §8 |
| R-3 | `record_id` = deterministic from `request_id`; genuinely changed findings get a suffixed id | satisfies both idempotency and "different content, new record_id" |
| R-4 | One FastAPI app (make_app + UI/API routes); `mode` stays `inproc` | `tests/conftest.py` forces `ORCH_MODE=inproc`; HTTP contract endpoints still served |
| R-5 | Review queue filters `source=ui` | orchestrator runs without captures also land in `final_open` but are not operator work |
| R-6 | Evaluation is benchmarked directly against the 100 sample units in `data/sample/receiving_sample.csv` (70 train, 30 hold-out) | evaluated purely against manifest & inspection fields without external folder dependencies |
| R-7 | Overrides are agent-level (append-only, outside the content hash) and mirrored as `RECEIVING_OVERRIDDEN` events | workflow-level overrides in the orchestrator's state are not written automatically |

### Prep v2 — 2026-10-09 (@Manideep667320)

| # | Decision | Trade-off |
|---|---|---|
| P-1 | Standardized on Amazon Rules 101–601 + Google Gemini Flash multimodal VLM | Pure rules miss physical image nuances; Gemini VLM validates polybag seals, suffocation text, and FNSKU seam positions |
| P-2 | Hardened async execution with event loop offloading (`concurrent.futures`) | Calling `asyncio.run` inside FastAPI's running event loop crashed HTTP mode; thread pool execution guarantees safe dual-mode operation (inproc + HTTP) |
| P-3 | Emits `payload.measurements` (length, width, height, gross weight) to resolve **Finding F-07** | Provides ground-truth physical packaging data downstream, enabling Recovery to contest Amazon `fulfilment_fee_weight_tier` overcharges |

### Pack v1 — 2026-10-09 (@ayeshaxsa)

| # | Decision | Trade-off |
|---|---|---|
| PK-1 | Decoupled domain engine from orchestrator using `order_adapter.py` and `prep_adapter.py` | Adapters translate upstream `RCV` / `PRP` evidence into internal order representations without altering core packing verification code |
| PK-2 | Enforces Prep gate check (`ALLOW` vs `HOLD`) before sealing | Prevents packaging non-compliant units while allowing compliant units to proceed cleanly |
| PK-3 | Records pre-seal contents observations in `payload` | Provides pre-shipment baseline truth used by Returns to detect customer-swapped or missing return items |

### Returns v1 — 2026-10-09 (@Adithya-charan)

| # | Decision | Trade-off |
|---|---|---|
| RT-1 | ReturnGuard AI: edge CV (RapidOCR + YOLOv8) + Google Gemini multimodal fallback | Local edge inference runs instantly offline; Gemini provides semantic reasoning on wear and accessory completeness |
| RT-2 | Authoritative Amazon Published 6-Point Condition Scale (`New`, `Used - Like New`, `Used - Very Good`, `Used - Good`, `Used - Acceptable`, `Unsellable`) | Maps directly to published Amazon warehouse return disposition standards (`restock`, `refurbish`, `liquidate`, `dispose`) |
| RT-3 | Inspects Pack evidence (`sent_contents_seen`) to resolve **Finding F-11** | Cross-references pre-shipment contents against return arrivals; verified SKU matches produce PASS evidence records cited by Recovery |

### Recovery v2 — 2026-10-09 (@saikiranpulagalla)

| # | Decision | Trade-off |
|---|---|---|
| RC-1 | Strict dispute positioning: `CONTRADICTS` (actionable claim), `SUPPORTS` (valid fee), `SILENT` (insufficient proof) | Never raises false-positive dispute claims; protects seller account health from frivolous Amazon support escalations |
| RC-2 | Zero-dollar fees treated as `SILENT` (**Finding F-09**) | Claiming $0.00 is commercially meaningless; avoids cluttering recovery submissions |
| RC-3 | Distinguishes supplier shortfall from channel loss (**Finding F-10**) | Receiving supplier shortages do not support carrier/Amazon `lost_inbound` claims |
| RC-4 | Cites Returns proof for `refund_issued_item_not_returned` (**Finding F-11**) | If Returns verified the correct item was received (`identity_match == PASS`), Recovery cites `RTN-*` to claw back the customer refund |

### Infrastructure & Orchestration Unified Decisions

| # | Decision | Trade-off |
|---|---|---|
| I-1 | Single unified PostgreSQL database (Neon) for production, single SQLite file for local dev | Eliminates 5 fragmented storage engines; keeps state synchronized across microservices |
| I-2 | Google Gemini (`gemini-3.5-flash`) as the unified cloud multimodal model | Single API key (`GEMINI_API_KEY`) powers visual inspection across all agents with consistent prompt latency |
