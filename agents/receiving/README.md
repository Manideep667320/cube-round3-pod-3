# agents/receiving/ · Receiving Manager v2

**Owner:** Gayathri (@gayathri2665) · [`PROVENANCE.md`](PROVENANCE.md)

A real receiving agent: photos in, an explainable verdict out. Built on the Round 3
starter contract (`handle(agent_input) -> agent_output`), with a scan UI, a review
queue, human overrides and an events feed served from **one FastAPI app**.

## What is real, what is not

| Part | Status |
|---|---|
| Decision logic (`decide.py`) | **Real.** Pure function, 15 plan tests, most-severe-wins, quality flags never change a verdict alone. |
| Perception (`perception.py`) | **Real.** OpenCV quality metrics + zxing-cpp decoding. |
| Damage assessment (`damage.py`) | **Real VLM call** (OpenAI / Anthropic / Gemini, auto-detected from env). Strict pydantic schema, one retry, sha256+prompt-version cache, **fail-safe**: no key / error / low confidence ⇒ `LOW_CONF_DAMAGE` ⇒ QUARANTINE. With no `VLM_*` key in the environment this is the only path taken — every scan quarantines and the README says so. |
| Benchmark (`eval.py`) | Evaluates decision engine against the 100 canonical units in `data/sample/receiving_sample.csv` (70 train / 30 hold-out). |
| Manifest | Seeded from `data/sample/receiving_sample.csv` (100 lines) + CSV import for demo manifests with GTINs. |
| Evidence | Contract-compliant, content-hashed via `shared/utils.records`, idempotent `record_id`s, append-only overrides. |
| Auth | **None** (demo scope). Operator names are free text. |

## Run it

```sh
pip install -r requirements.txt -r agents/receiving/requirements.txt   # opencv, zxing-cpp, pillow
# optional, for real damage detection (otherwise fail-safe QUARANTINE):
echo 'OPENAI_API_KEY=...      # or ANTHROPIC_API_KEY / GEMINI_API_KEY' >> .env

uvicorn agents.receiving.app:app --port 8101
# UI:  http://localhost:8101/         API docs: /docs
# contract endpoints: GET /health, POST /run   (mode stays "inproc" for tests)
```

## Verdict vocabulary (two levels, on purpose)

The contract allows only `PASS / FAIL / UNCERTAIN` for `decision.verdict`, so the
plan's four **physical actions** live in `decision.outcome` + `payload.plan_verdict`:

| Physical state | `payload.plan_verdict` | `decision.verdict` (= rollup of checks) | `decision.outcome` | `next_step` |
|---|---|---|---|---|
| Put the goods away | `ACCEPT` | `PASS` | `accept` | `continue` |
| Hold, evidence insufficient | `QUARANTINE` | `UNCERTAIN` (or `FAIL` if a check like `carton_damage` failed) | `pending_review` | `review` |
| Hold, known discrepancy | `ESCALATE` | `FAIL` | `pending_review` | `review` |
| Refuse the goods | `REJECT` | `FAIL` | `reject` | `route_to_recovery` |

`decision.verdict` is always `rollup(checks)`: a check is emitted **only when it was
actually judged**, so checks and decision can never contradict each other.

**Checks emitted:** `identity_match` (barcode vs GTIN), `quantity` (when a qty was
entered), `lot_match` / `expiry_ok` (when both sides exist), `carton_damage` (when
there are photos). `carton_count` and `unit_damage` from the contract's recommended
list are **not** emitted: this station does not count cartons or open cartons, and
inventing an always-UNCERTAIN check would make `ACCEPT` unreachable. Image-quality
flags (`IMG_BLURRY/IMG_GLARE/IMG_DARK`) are diagnostics in `payload.facts`, never a
verdict on their own.

**Reason codes → physical action** (most severe wins):
`SEVERE_DAMAGE`, `EXPIRED` → REJECT · `WRONG_SKU`, `NOT_IN_MANIFEST`, `QTY_MISMATCH`,
`LOT_CONFLICT` → ESCALATE · `MODERATE_DAMAGE`, `NO_BARCODE`, `LOW_CONF_DAMAGE` → QUARANTINE.

## Retake coach, overrides, immutability

- Retake offered **once**: `attempt == 0` and QUARANTINE with a retakeable reason
  (`NO_BARCODE`, `LOW_CONF_DAMAGE`). One specific instruction + which role to re-shoot.
  Retake and Skip both finalize; there is never a second prompt.
- Overrides (`POST /api/receivings/{id}/override`) **append** an agent-level override
  to the record. `checks`, `decision` and `content_hash` are never rewritten (contract:
  overrides sit outside the hash). Original verdict stays visible in Logs; the row
  tracks the effective verdict.

## Handoff to the other agents

- Primary: the orchestrator passes this record as `previous_evidence` like any stage.
- Pull feed: `GET /api/events?since=<id>` → `RECEIVING_FINAL` / `RECEIVING_OVERRIDDEN`
  with `workflow_id`, `subject{org_id,subject_id}`, `record_id`, `effective_verdict`
  (4-state), contract `verdict`, `reasons`, `image_sha256[]`. Consumers: act on
  `ACCEPT` only; `QUARANTINE`/`ESCALATE` means hold until an override event arrives;
  `REJECT` events carry the evidence for Recovery (hashes, reasons, timestamps).
- Overrides made in this UI live in this service's records/events. They are **not**
  written into the orchestrator's Workflow State automatically — transcribe them if
  the workflow-level override channel must reflect them.

## API

| Method + path | Purpose |
|---|---|
| `POST /api/receivings` | multipart scan: photos+roles, org/line, qty, lot, expiry, operator → record + explanation + coach |
| `POST /api/receivings/{id}/retake` | replacement photos, always finalizes |
| `POST /api/receivings/{id}/finalize` | skip the retake, finalize current evidence |
| `POST /api/receivings/{id}/override` | `{final_verdict, reason_code, note, operator}` → append-only |
| `GET /api/receivings?status=&verdict=&source=` | Logs / queue (`source=ui` = physical scans only) |
| `GET /api/receivings/{id}` | plan-shaped view + full sealed `record` |
| `GET /api/events?since=` | handoff feed |
| `GET/POST /api/manifest` | list / CSV import (`po_id,line_no,unit_id,gtin,sku,description,qty_expected,lot,expiry,supplier,org_id`) |

Tenancy: every lookup is org-scoped; a foreign subject raises `LookupError` → HTTP 404 /
`AgentRejected`, never a cross-tenant answer.

## Tests

```sh
pytest agents/receiving/tests -q     # plan tests 1-15 + tenancy/retake-cap checks
pytest -q                           # whole pod suite (contract, workflow state, e2e)
python -m agents.receiving.eval     # benchmark metrics over sample dataset (n=100)
```

## Benchmark Evaluation (`python -m agents.receiving.eval`)

Evaluates the Receiving decision engine across the 100 canonical units in `data/sample/receiving_sample.csv` (split 70 Train, 30 Hold-out) directly against manifest and inspection attributes:

| Metric | Train (UNIT-0001 to UNIT-0070, n=70) | Hold-out (UNIT-0071 to UNIT-0100, n=30) |
|---|---|---|
| **Overall Decision Accuracy** | **91.4% (64/70)** | **90.0% (27/30)** |
| **Quantity Mismatch Detection** | **12 / 12 (100%)** | **3 / 3 (100%)** |
| **Identity Discrepancy Detection** | **4 / 4 (100%)** | **2 / 2 (100%)** |
| **Decisions Breakdown** | ACCEPT: 43, QUARANTINE: 8, ESCALATE: 11, REJECT: 8 | ACCEPT: 18, QUARANTINE: 5, ESCALATE: 2, REJECT: 5 |

## Demo scenarios

1. **Clean accept** — Scan input photo (+ overall), qty = expected.
   With a VLM key: ACCEPT. Keyless: QUARANTINE via `LOW_CONF_DAMAGE` (fail-safe) — say so.
2. **Glare → coach → retake → finalize** — When glare is detected on barcode label: QUARANTINE with
   “Glare on the label. Tilt the package away from the light.” Retake with clear label photo
   → finalizes, no second prompt.
3. **Qty mismatch → ESCALATE → override** — Scan with a wrong qty: `QTY_MISMATCH`,
   lands in the Review Queue. Override to ACCEPT (`DOC_CORRECTED`): Logs show original vs
   effective; `GET /api/events` shows `RECEIVING_OVERRIDDEN`.
4. **Severe damage → REJECT + handoff** — Scan severely crushed carton (needs VLM key):
   `SEVERE_DAMAGE` → REJECT → `RECEIVING_FINAL` event visible to downstream recovery process polling
   `/api/events`. Keyless this quarantines instead.

## Limits (state these openly)

- Damage is a VLM call with **self-reported** confidence, not a trained model; T=0.7 is
  a starting guess, not a calibrated probability.
- Without VLM credentials the agent **never** accepts a photo scan (fail-safe QUARANTINE).
- Lot and expiry are operator-entered; one manifest line per receiving; no partial receipts.
- No authentication; single SQLite file (`out/receiving/receiving.db`); single process;
  the events feed is pull-only (no webhook, no retries).
- The retake coach reacts to image quality and model confidence, not to ground truth.
- Overrides are local to this service (see Handoff).

## Layout

```text
agents/receiving/
├── app.py          handle() + the one FastAPI app (UI, /api, /run, /health)
├── service.py      shared evaluation pipeline (orchestrator + UI), contract bridge
├── decide.py       pure verdict rules (4-state) + contract mapping
├── explain.py      one template per reason code, real numbers only
├── coach.py        retakeable reason → instruction + photo role
├── perception.py   OpenCV quality + zxing-cpp decode
├── damage.py       VLM call, strict schema, sha256 cache, fail-safe
├── db.py           SQLite: manifest, receivings, photos, append-only records, events, cache
├── config.py       env/paths/thresholds/VLM provider detection
├── eval.py         sample benchmark evaluation (python -m agents.receiving.eval)
├── thresholds.json tuned thresholds
├── static/         scan UI (vanilla JS)
├── tests/          plan tests 1-15 + flow tests
├── PROVENANCE.md
└── requirements.txt  agent-local deps (root requirements.txt untouched)
```
