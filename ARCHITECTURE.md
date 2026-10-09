# Architecture

This document describes the **starter**. At the bottom is a section for **your Pod's architecture**, which you must fill in and which is part of the submission. A submission whose `ARCHITECTURE.md` still only describes the starter has not documented its system.

## 1. The system

```text
                POD
                 │
       ┌─────────▼─────────┐      owns workflow state; derives status and final outcome from the evidence chain
       │    Orchestrator   │      routes · validates · records evidence · retries · handles failures and UNCERTAIN
       └─────────┬─────────┘
                 │  Agent Input ▼          ▲ Agent Output (evidence)
       ┌─────────▼─────────┐
       │     Receiving     │
       └─────────┬─────────┘
                 ↓
       ┌───────────────────┐
       │       Prep        │   (FBA units)
       └─────────┬─────────┘
                 ↓
       ┌───────────────────┐
       │       Pack        │   (merchant-fulfilled / 3PL units)
       └─────────┬─────────┘
                 ↓
       ┌───────────────────┐
       │      Returns      │   (if a return happened)
       └─────────┬─────────┘
                 ↓
       ┌───────────────────┐
       │     Recovery      │   reads ALL accumulated evidence
       └─────────┬─────────┘
                 ↓
          Final Outcome        derived by the orchestrator, not copied from any agent

  shared/schemas · shared/contracts · shared/utils      data/input · data/sample · data/expected      examples/
```

The arrows show the *expected commerce journey*. Physically, every hand-off goes through the orchestrator ([`INTEGRATION-GUIDE.md`](INTEGRATION-GUIDE.md) section 1).

## 2. Responsibilities

| Component | Responsible for | Not responsible for |
|---|---|---|
| **Agent** (`agents/<stage>/`) | One stage's judgment, returned as an Agent Output with an Evidence Record. Failing open. Refusing other tenants. | Calling other agents. Setting workflow state. Rewriting earlier evidence. |
| **Orchestrator** (`orchestration/`) | Starting workflows; identifying the current stage; invoking agents with context; validating and recording evidence; updating state; routing; retries; failures; UNCERTAIN; the final outcome. | Making stage judgments. Fabricating or deleting evidence. Turning UNCERTAIN into PASS/FAIL without an explicit rule. |
| **Contract** (`shared/schemas/`) | One strict set of data shapes. | Agent-specific logic (that goes in `payload`). |
| **Stubs** (`agents/*/app.py` as shipped) | Replaying Round 2 CSV rows as valid evidence, so the plumbing can be tested. | Pretending to be agents. |

## 3. Shared data

| Object | Owner | Lives in |
|---|---|---|
| Evidence Record | the agent that produced it (immutable) | the evidence store |
| Workflow State | **the orchestrator** | the workflow store |
| Overrides | the orchestrator records them; a person makes them | Workflow State (`overrides[]`), referencing evidence |
| Final Outcome | **the orchestrator**, derived | Workflow State (`final_outcome`) |
| Captures | the Pod | `data/input/<subject>/<stage>/`, referenced by `sha256` |

## 4. Evidence flow and workflow state

```text
Agent Result → Evidence Record → Orchestrator state transition → Next stage → New evidence → Updated workflow state → Final Outcome
```

- Each stage's evidence is stored and passed to **every later stage** as `previous_evidence`.
- State is `PENDING → IN_PROGRESS → COMPLETED`, or `FAILED` / `BLOCKED` / `RECOVERY_REQUIRED` ([`ORCHESTRATION-GUIDE.md`](ORCHESTRATION-GUIDE.md) section 5), always derived from the evidence and overrides.
- `transitions[]` is the audit trail.
- A reviewer can walk from the Final Outcome to `contributing_records`, to checks, to `evidence_refs`, to the `sha256` of the exact bytes examined.

## 5. Error handling

Every failure is **recorded and never becomes success**: a degraded evidence record stands in (no checks, UNCERTAIN, the error), the stage is `error`, the workflow `FAILED` with outcome `INCOMPLETE`. Transient failures retry; refusals and invalid output do not; UNCERTAIN is preserved; `resume` retries. Full table: [`ORCHESTRATION-GUIDE.md`](ORCHESTRATION-GUIDE.md) section 8. Tenancy: `org_id` on every request, record and workflow; a record about another org is rejected as a security event; **your storage must enforce it too**.

## 6. Final outcome

`CLEAN`, `CLAIM_RECOMMENDED`, `EXCEPTION`, `NEEDS_REVIEW` or `INCOMPLETE`, with the reason, the contributing evidence, `needs_human`, and `provisional` (true unless the workflow is `COMPLETED`). Default rules: [`ORCHESTRATION-GUIDE.md`](ORCHESTRATION-GUIDE.md) section 6.

## 7. What is fixed and what is yours

**Fixed (the contract, strict):**

- The five required agents and their stages (Specialist Pods: four agents plus integration work, see [`FAQ.md`](FAQ.md))
- Common evidence requirements: the Agent Input/Output and Evidence Record shapes; PASS / FAIL / UNCERTAIN; the status vocabularies
- Required traceability: workflow id, agent id, hashes, `upstream_refs`, overrides that reference what they supersede
- An orchestrator that owns workflow state and produces a **Final Outcome**
- Minimum testing, and the submission and evaluation requirements ([`SUBMISSION-GUIDE.md`](SUBMISSION-GUIDE.md), [`ROUND3-RUBRIC.md`](ROUND3-RUBRIC.md))

**Participant-designed (the implementation, flexible):**

- Internal architecture, programming language, frameworks, how each agent is built
- How the orchestrator is implemented (the starter is one option; LangGraph, a queue, a state machine, your own)
- The communication mechanism (in-process, HTTP, queue) as long as the contract holds
- Database, persistence, deployment platform
- UI, review queue, dashboards
- Additional services, additional features
- The final-outcome policy, routing and `on_uncertain` / `on_error` policies (documented in `docs/decisions.md`)

## 8. Extension points

| You want to… | Change |
|---|---|
| Add or reroute a stage | `orchestration/flow.json` (and write a decision) |
| Change the final decision or status rules | `orchestration/rollup.py` (and its tests, and a decision) |
| Plug in a real agent | `agents/<stage>/app.py` + `agent.json` |
| Run an agent as a service in any language | `agent.json` `mode: "http"` + [`agent-api.md`](shared/contracts/agent-api.md) |
| Run your own subjects | `data/input/<subject>/<stage>/` + a cases file |
| Add agent-specific data to evidence | `payload` (never the envelope) |
| Persist to a database | implement the four store methods in `orchestration/store.py` |

## 9. Deployment options (yours)

- **Single process:** `uvicorn orchestration.api:app` with all agents `inproc`. Simplest.
- **Orchestrator + agent services:** each agent its own process, `mode: "http"`, `<STAGE>_URL` set; `GET /health` for readiness.
- Whatever you pick, the demo runs from the submitted commit and any URL works without your accounts. The API ships with **no authentication**: add it before exposing it.

---

## Your Pod's architecture: Pod 3 Unified Commerce System

### 1. System Architecture & Flow

Pod 3 operates as a unified commerce operations platform where a single stateful Orchestrator coordinates five specialized domain agents speaking the strict Evidence Contract v1.0. Upstream physical evidence flows downstream to form an unbroken audit ledger that directly backs Amazon fee dispute recoveries.

```mermaid
flowchart TD
    subgraph INGRESS["Warehouse Ingress & Order Fulfillment"]
        RCV["Receiving Manager (@gayathri2665)<br/>• Real v2 Engine & Inbound Scanner<br/>• Manifest PO matching & Carton damage<br/>• Distinguishes Supplier Shortfall (F-10)"]
        FBA{"Route = FBA?"}
        MFN{"Route = MFN?"}
        PREP["Prep Manager (@Manideep667320)<br/>• Real Amazon Rules 101-601 Engine<br/>• Google Gemini Flash VLM<br/>• Polybag, FNSKU, Warnings, Dimensions (F-07)"]
        PACK["Pack Manager (@ayeshaxsa)<br/>• Real Packing Slip & Sealing Engine<br/>• Prep Gate Status Check<br/>• Verifies Pre-Shipment Contents Truth"]
    end

    subgraph POST_ORDER["Returns & Channel Dispute Operations"]
        RTN["Returns Manager (@Adithya-charan)<br/>• ReturnGuard AI Engine<br/>• RapidOCR + YOLOv8 + Gemini Multimodal<br/>• Amazon Published Condition Scale<br/>• Confirms Sent Contents Seen (from Pack)<br/>• Emits Identity Proof (F-11)"]
        RCY["Recovery Manager (@saikiranpulagalla)<br/>• Domain Financial Dispute Engine<br/>• Ingests ALL Upstream Records (RCV, PRP, PCK, RTN)<br/>• Disputes refund_issued_item_not_returned<br/>• Disputes weight tier charges (PRP measurements)<br/>• Never claims on SILENT / Supplier Shortfall"]
    end

    subgraph STATE["Authoritative State Ledger & Storage"]
        ORCH["Pod Orchestrator<br/>• Functional Rollup & State Transitions<br/>• Resumption, Retries, Idempotency<br/>• Human Review Queue & Overrides Audit"]
        NEON[("Neon PostgreSQL & Unified Storage<br/>• Database URL configured via SSL<br/>• Storage: out/workflows & out/evidence")]
    end

    RCV -->|RCV-*| FBA
    RCV -->|RCV-*| MFN
    FBA -->|Route: fba| PREP
    MFN -->|Route: mfn| PACK
    PREP -->|PRP-* (if returned)| RTN
    PACK -->|PCK-* (if returned)| RTN
    PREP -->|PRP-*| RCY
    PACK -->|PCK-*| RCY
    RTN -->|RTN-*| RCY
    RCY -->|RCY-*| ORCH
    ORCH <--> NEON
```

### 2. Concrete Agent Implementations (100% Real Engines, Zero Stubs)

- **Receiving Manager (`agents/receiving/` · `@gayathri2665`)**:
  - *Implementation:* Real v2 ingestion service with embedded SQLite manifest matching, barcode decoding, carton puncture/crush evaluation, and review queue.
  - *Data Produced:* `RCV-*` records identifying ordered vs received item count, carton integrity, and supplier shortfall flags (addressing **Finding F-10**).
- **Prep Manager (`agents/prep/` · `@Manideep667320`)**:
  - *Implementation:* Amazon packaging rules engine (rules 101–601) integrated with Google Gemini 3.5 Flash multimodal vision. Asynchronously resilient across in-proc and FastAPI HTTP event loops.
  - *Data Produced:* `PRP-*` records validating polybag seals, suffocation text, seam barcode placement, expiry dates, and packaging dimensions/weights (addressing **Finding F-07**).
- **Pack Manager (`agents/pack/` · `@ayeshaxsa`)**:
  - *Implementation:* Real outbound packing verification engine with dedicated Order & Prep Adapters (`order_adapter.py`, `prep_adapter.py`). Enforces gate status (`ALLOW` vs `HOLD`).
  - *Data Produced:* `PCK-*` records capturing sealed carton integrity, packing slip compliance, and pre-seal item observations.
- **Returns Manager (`agents/returns/` · `@Adithya-charan`)**:
  - *Implementation:* ReturnGuard AI combining local edge CV (RapidOCR + Ultralytics YOLOv8), Gemini Multimodal VLM, and Amazon's published 6-point condition scale.
  - *Data Produced:* `RTN-*` records with product identity match, accessory completeness, physical condition grade, and automated disposition (`restock`, `refurbish`, `liquidate`, `dispose`, `pending_review`).
- **Recovery Manager (`agents/recovery/` · `@saikiranpulagalla`)**:
  - *Implementation:* Real domain dispute engine correlating channel fee reports with all upstream physical records (`RCV`, `PRP`, `PCK`, `RTN`). Evaluates claims as `CONTRADICTS` (disputable), `SUPPORTS` (valid fee), or `SILENT` (insufficient proof).
  - *Data Produced:* `RCY-*` records establishing recovery claims with line-item dollar amounts.

### 3. Orchestration & State Management

- **Authoritative State:** State machine managed in `orchestration/orchestrator.py`. Workflow states (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `BLOCKED`, `FAILED`).
- **Storage:** Persisted via `FileStore` into `out/workflows/` and `out/evidence/`, with unified tabular data managed in Neon PostgreSQL (`DATABASE_URL`).
- **Overrides:** Fully append-only and non-destructive (`apply_override()`). An operator override creates an `OVR-*` transition that preserves the original evidence while updating effective verdicts.
- **Resilience:** Uncaught exceptions or timeouts yield degraded evidence records (`status: error`). Calling `resume()` recovers execution once the service is restored.

### 4. Routing, Policies, and Uncertainty

- **Routing:** Governed by `orchestration/flow.json`. FBA units route to Prep; MFN units route to Pack; units with `returned: true` route to Returns. Unknown routes cleanly skip both fulfillment stages with an explicit audit transition.
- **Uncertainty (`on_uncertain: continue`):** Low-confidence observations proceed to downstream stages without halting warehouse operations. If an UNCERTAIN stage flags `needs_human: True`, the workflow transitions to `BLOCKED` with outcome `NEEDS_REVIEW` until an operator resolves the queue.

### 5. Multi-Tenancy Enforcement

- Strict `org_id` scoping is verified at **three independent boundaries**:
  1. The Orchestrator validates `request["subject"]["org_id"]` against the workflow before invoking any agent.
  2. Each agent refuses cross-tenant subject IDs (raising `LookupError` in-process or HTTP 404/422).
  3. The storage layer verifies tenant integrity before saving evidence records.

### 6. Failure & Recovery Model

- Simulated agent outages (timeouts, connection drops, process crashes) produce degraded records (`status: error`), transition the workflow to `FAILED` with provisional outcome `INCOMPLETE`, and never report false successes.
- Workflows resume from their exact halted stage using `resume(workflow_id)`.

### 7. Deployment & Verification

- **In-process execution:** `python -m orchestration.api` (zero network overhead, instant execution).
- **Service mode:** `docker compose up --build` or individual FastAPI microservices communicating over HTTP (`GET /health`, `POST /run`).
- **Database:** Neon PostgreSQL remote instance verified via SSL connection string.
- **Automated Validation:** 100% of integration, contract, and end-to-end tests pass across all agents (`pytest tests/`).
