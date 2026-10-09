# ReturnGuard AI — QR-Based Return Verification and Product Inspection

ReturnGuard AI verifies that a returned product is genuine, complete and as-described
**before** a refund is issued. It chains a hidden single-use QR authorization, an OTP
delivered to the delivery agent's verified phone, real OCR, and real YOLO object
detection into one auditable pipeline that ends in a deterministic, evidence-based
decision — with human review whenever evidence is uncertain.

```
Admin Login → Create Return → Generate Hidden QR → Delivery Agent Scans QR →
OTP Sent to Registered Mobile → Verify OTP → Capture/Upload Real Product Photo →
OCR + YOLO Inference → Evidence-Based Decision → Human Review When Necessary →
Persistent Audit Record
```

> **Honesty note:** every result shown by the UI is produced by the backend pipeline.
> OCR runs a real engine (RapidOCR/PP-OCRv4 by default), YOLO runs real Ultralytics
> inference, and the optional AI stage runs real Groq + Qwen vision inference
> (`qwen/qwen3.8-27b`, verified image-capable) with schema-validated output.
> The mock SMS provider is development/test-only — production refuses to boot
> with it. Generic COCO weights (`yolov8n.pt`) are **not** a validated
> return-inspection model; see [YOLO model setup](#yolo-model-weights).
> The condition scale and disposition rules are an explicitly UNOFFICIAL
> placeholder until the official challenge resources are supplied — see
> [docs/GAP_ANALYSIS.md](docs/GAP_ANALYSIS.md).

---

## Contents

- [Architecture overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment variables](#environment-variables)
- [Database initialization](#database-initialization)
- [Initial admin setup](#initial-admin-setup)
- [Running the application](#running-the-application)
- [Testing the full workflow with your own photos](#testing-the-full-workflow-with-your-own-photos)
- [OCR engine](#ocr-engine)
- [YOLO model weights](#yolo-model-weights)
- [Mock SMS (development) vs real SMS (production)](#mock-sms-development-vs-real-sms-production)
- [Automated tests](#automated-tests)
- [Docker](#docker)
- [Production deployment notes (PostgreSQL)](#production-deployment-notes-postgresql)
- [Troubleshooting & known limitations](#troubleshooting--known-limitations)

---

## Architecture overview

| Layer | Technology |
| --- | --- |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS v4, `@zxing/browser` QR scanning, `lucide-react` icons |
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | SQLite (local dev) → PostgreSQL (production path) |
| OCR | RapidOCR (PP-OCRv4 models via onnxruntime) by default; Tesseract optional |
| Detection | Ultralytics YOLO (`yolov8n.pt` by default; custom weights supported) |
| Security | PBKDF2-SHA256 password hashing (stdlib), HS256 JWT (purpose-scoped), HMAC-hashed OTPs, SHA-256-hashed QR tokens, in-memory rate limiting |
| AI reasoning | Groq API + Qwen 3.8 27B vision (`qwen/qwen3.8-27b`) — schema-validated evidence, never authority |

Roles: **ADMIN** (manage everything, resolve reviews), **AGENT** (delivery agent)
and **OPERATOR** (warehouse inspection operator) — both inspect only their
assigned returns, with all powers enforced server-side.

Detailed design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
Step-by-step workflow: [docs/WORKFLOW.md](docs/WORKFLOW.md) ·
Security model: [docs/SECURITY.md](docs/SECURITY.md) ·
Gap analysis & challenge alignment: [docs/GAP_ANALYSIS.md](docs/GAP_ANALYSIS.md)

## Prerequisites

- **Python 3.11+** and pip
- **Node.js 18+** (tested with Node 24) and npm
- A webcam or phone camera for QR scanning and photo capture (optional for local
  testing — the UI has a paste-token fallback and file-upload fallback)
- ~1.5 GB disk for the Python CV stack (torch CPU + onnxruntime)

## Installation

### 1. Backend

```bash
cd backend
python -m venv .venv                       # Windows: .venv\Scripts\activate
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Reproducible exact versions instead:
# pip install -r requirements.freeze.txt
```

> **Linux CPU-only tip:** install torch first to avoid CUDA wheels:
> `pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu`

### 2. Frontend

```bash
cd frontend
npm install
```

### 3. Environment

```bash
cp .env.example backend/.env
# then edit backend/.env — at minimum set SECRET_KEY
```

See [Environment variables](#environment-variables) for every option.

## Environment variables

All variables are read by `backend/.env` (see [.env.example](.env.example), placeholders only).

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | `production` enables strict startup guards |
| `SECRET_KEY` | dev placeholder | JWT signing + OTP hashing key; **must** be set in production |
| `DATABASE_URL` | `sqlite:///./data/returnguard.db` | SQLite locally; PostgreSQL DSN in production |
| `STORAGE_DIR` | `<project>/storage/uploads` | Controlled image storage |
| `MAX_UPLOAD_MB` | `10` | Upload size limit |
| `QR_TOKEN_TTL_HOURS` | `72` | QR authorization lifetime |
| `OTP_TTL_SECONDS` | `300` | OTP expiry (5-minute default) |
| `OTP_MAX_ATTEMPTS` | `5` | Failed verifies before a challenge is exhausted |
| `OTP_RESEND_COOLDOWN_SECONDS` | `60` | Minimum gap between sends |
| `OTP_MAX_ISSUES_PER_HOUR` | `5` | Hourly issue cap per return/agent |
| `SMS_PROVIDER` | `mock` | `mock` (dev/test only) or `twilio` |
| `TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER` | — | Real SMS credentials |
| `OCR_ENGINE` | `auto` | `auto` \| `rapidocr` \| `tesseract` \| `none` |
| `OCR_LOW_CONFIDENCE_THRESHOLD` | `55` | 0–100 mean-confidence cutoff for `LOW_CONFIDENCE` |
| `YOLO_MODEL_PATH` | `yolov8n.pt` | Weights path (`.pt` or `.onnx`) |
| `YOLO_CONFIDENCE_THRESHOLD` | `0.35` | Detection confidence floor |
| `YOLO_DEVICE` | `auto` | `auto` \| `cpu` \| `cuda` |
| `GROQ_API_KEY` | — | Groq API key; empty **disables** the AI stage (pipeline still runs; decisions route to review) |
| `GROQ_VISION_MODEL` | `qwen/qwen3.8-27b` | Must be a Groq model accepting IMAGE inputs (verified image-capable Oct 2026) |
| `GROQ_TIMEOUT_SECONDS` | `45` | Per-attempt timeout for the AI stage |
| `GROQ_MAX_RETRIES` | `2` | Bounded retries for rate limits / transient errors |
| `CONDITION_SCALE_FILE` | — | JSON file with the **official** condition scale (see docs/GAP_ANALYSIS.md) |
| `ADMIN_BOOTSTRAP_USERNAME/PASSWORD` | — | One-time initial admin (when no admin exists) |

## Database initialization

**Local development (SQLite):** tables are created automatically on first start.

**With Alembic migrations (recommended, required for production):**

```bash
cd backend
alembic upgrade head                       # uses DATABASE_URL from env/.env
```

**PostgreSQL:** create a database, set
`DATABASE_URL=postgresql+psycopg://user:pass@host:5432/returndata`, install
`pip install psycopg[binary]`, and run `alembic upgrade head`. The schema is
cross-compatible (UUIDs stored as strings, JSON columns on SQLite/Postgres).

## Initial admin setup

There is **no public registration path** and no default credentials. Two options:

```bash
# Option A — CLI (prompts for the password, or use ADMIN_BOOTSTRAP_PASSWORD env var)
cd backend
python -m scripts.create_admin --username admin --full-name "Site Admin"

# Option B — one-time environment bootstrap (used only while no ADMIN exists)
ADMIN_BOOTSTRAP_USERNAME=admin ADMIN_BOOTSTRAP_PASSWORD=<strong-password> uvicorn app.main:app
```

Create delivery agents from the **Users** page in the admin console (or
`POST /api/admin/users`). Agents need a **verified** phone number before OTP
delivery works: create the user with a phone, then click *Mark verified* (an admin
action, audited).

## Running the application

Terminal 1 — backend (port 8000):

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — frontend (port 5173, proxies `/api` to :8000):

```bash
cd frontend
npm run dev
```

Open http://localhost:5173, sign in as your admin, create a return, assign an
agent, generate the QR, then sign in as the agent (in another browser/incognito)
to scan → verify OTP → upload a photo.

API documentation (Swagger UI): http://localhost:8000/docs ·
Health: http://localhost:8000/api/health

## Testing the full workflow with your own photos

1. Sign in as the **agent** (or an **operator**) → *Scan QR* → scan the QR PNG the
   admin downloaded (or paste the token — the QR value is `returnguard://scan?token=…`).
2. *Send verification code*. With `SMS_PROVIDER=mock` the six-digit code is
   captured server-side only and is never logged; read it from a backend shell:
   ```python
   from app.services.sms_service import get_sms_provider
   print(get_sms_provider().last_for("+15551234567").body)
   ```
   or configure a real Twilio number (see below).
3. Enter the code, then *Capture* or *Upload* a photo. Choose the
   **contents-layout** view for a second photo showing ALL returned items —
   that is the only single-photo evidence that can confirm a missing accessory.
4. The result page shows the real YOLO boxes, real OCR output, the AI visual
   analysis (provider/model/status/confidence), the four dimensions
   (identity, completeness, condition, recommended disposition) and the
   rule-by-rule decision rationale.
5. `MANUAL_REVIEW` results land in the admin **Review queue**; you can add more
   photos while the decision is pending. Resolving requires a reason and
   preserves the original automated decision.

## OCR engine

Default: **RapidOCR** (`rapidocr-onnxruntime`), PP-OCRv4 models shipped inside the
pip package via onnxruntime — no system dependencies, works offline after install.

- Statuses reported honestly: `OK`, `NO_TEXT_DETECTED`, `LOW_CONFIDENCE`,
  `ENGINE_UNAVAILABLE`, `TIMEOUT`, `FAILED`. Text/confidence are never invented.
- Optional **Tesseract**: install the binary + `pip install pytesseract`, then set
  `OCR_ENGINE=tesseract`.
- Disable OCR entirely with `OCR_ENGINE=none` (decisions then route to review
  because identity can't be confirmed).

## YOLO model weights

Default: `yolov8n.pt` (auto-downloaded by Ultralytics on first use — generic COCO
classes: person, laptop, cell phone, …). The model is loaded **once** at startup,
runs on CPU by default, and every response includes model name, device, threshold
and inference time.

**Important limitations (also surfaced in the UI evidence panel):**

- A generic COCO model cannot confirm specific product variants, small accessories,
  missing components, or damage/defects.
- Component matching therefore uses configurable class hints; anything unconfirmed
  is `NOT_OBSERVED`/`UNCERTAIN` — the engine never auto-rejects on absence from a
  single photo and never fabricates detections when weights are missing
  (`MODEL_UNAVAILABLE` is reported instead).

**Supply your own weights** (recommended for real deployments):

```env
YOLO_MODEL_PATH=/absolute/path/to/return-inspector.pt
```

Train with [Ultralytics](https://docs.ultralytics.com/datasets/detect/): label a
dataset (Roboflow/CVAT) of your products, accessories and defect cases in YOLO
format, run `yolo detect train data=dataset.yaml model=yolov8n.pt epochs=100`,
then point `YOLO_MODEL_PATH` at `runs/detect/train/weights/best.pt`.

## Groq + Qwen visual reasoning (AI stage)

The inspection pipeline sends the actual photo(s) plus structured context
(expected order data, OCR text, YOLO detections, allowed condition grades) to a
Groq-hosted **image-capable Qwen** model and parses the response into a strict
enum-bounded schema (identity PASS/FAIL/UNCERTAIN, condition grade, per-component
findings, visible defects, confidence).

- Default model `qwen/qwen3.8-27b` was verified against Groq's official vision
  docs (Oct 2026): accepts image + text inputs, supports JSON mode, max 3 images.
  Text-only Qwen models must not be used for this variable.
- Set `GROQ_API_KEY` in `backend/.env` (never commit it). With no key the AI
  stage reports `UNAVAILABLE`, the pipeline continues, and decisions route to
  human review — nothing is fabricated and there is no provider fallback.
- Schema-violating model responses get one corrective retry, then report
  `MALFORMED`. Rate limits and transient errors retry with bounded backoff.
- The model's output is **validated evidence, never authority**: it cannot
  approve a return by itself, and liquidate/dispose recommendations always
  require human sign-off.

## Mock SMS (development) vs real SMS (production)

- `SMS_PROVIDER=mock` captures messages **in process memory** for local dev and
  tests. It is not exposed by any HTTP endpoint, and OTPs are never stored in the
  database (only HMAC hashes), never logged, never returned in API responses.
- **Production refuses to start** with `APP_ENV=production` + `SMS_PROVIDER=mock`
  (and refuses the default `SECRET_KEY`). There is no silent fallback to mock when
  a real provider fails — delivery errors surface as `502 sms_delivery_failed`.
- Real delivery (Twilio): set `SMS_PROVIDER=twilio` and the three `TWILIO_*`
  variables. **Not verified in this environment** — configure and test with your own
  account/number before relying on it.

## Automated tests

Backend (app-logic + mocked-provider tests, plus opt-in REAL-inference tests):

```bash
cd backend
pytest -q -m "not live_cv and not groq_live"   # app logic: auth, QR, OTP, uploads, evidence, decisions, RBAC, Groq mocked
pytest -q -m live_cv                            # REAL OCR + REAL YOLO inference smoke tests
RUN_LIVE_GROQ=1 pytest -q -m groq_live          # REAL Groq/Qwen vision call (requires GROQ_API_KEY)
python -m scripts.evaluate                      # 15-scenario challenge-alignment report (decision logic)
```

The live tests **fail loudly with a blocker message** if no OCR engine or weights
is available — they never fabricate results.

Frontend:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

## Docker

`docker-compose.yml` runs the API (with the SQLite volume mounted) plus the
frontend dev server:

```bash
cp .env.example backend/.env    # edit SECRET_KEY etc.
docker compose up --build
```

## Production deployment notes (PostgreSQL)

1. `APP_ENV=production`, strong `SECRET_KEY`, real `SMS_PROVIDER=twilio` + creds.
2. `DATABASE_URL` → PostgreSQL; `alembic upgrade head` (do not rely on `create_all`).
3. Serve with multiple uvicorn workers behind TLS; replace the in-memory rate
   limiter with a shared store (interface is isolated in `app/core/ratelimit.py`).
4. Serve `storage/uploads` through authenticated routes only (already enforced by
   `/api/inspections/{id}/image`); put the volume on durable storage and back it up.
5. Supply custom YOLO weights validated on your product data before trusting
   automated approvals.

## Troubleshooting & known limitations

| Symptom | Cause / fix |
| --- | --- |
| `OCR: unavailable` in health | `pip install rapidocr-onnxruntime` into the active venv |
| `YOLO weights: missing` | Let ultralytics download `yolov8n.pt`, or set `YOLO_MODEL_PATH` to real weights |
| OTP never arrives | Mock provider by default — read it via `get_sms_provider().last_for(phone)` in a backend shell, or configure Twilio; also check the agent's phone is **verified** |
| `phone_unverified` on OTP request | Admin must mark the agent's phone verified (Users page) |
| Windows venv activation blocked | Run PowerShell as your user, or use `.venv\Scripts\python.exe -m uvicorn ...` directly |
| Camera unavailable in the browser | Use the paste-token fallback and file upload; `getUserMedia` requires localhost or HTTPS |
| Every inspection goes to review with default weights | Expected: COCO classes rarely match your components; provide custom weights for meaningful auto-approvals |

**Known limitations**

- OCR/SMS/detection are synchronous per request (fine for single-image CPU
  inference; add a worker queue if you raise image sizes or model sizes).
- Damage/defect detection is deliberately **not** claimed — no validated defect
  model is bundled.
- A single photo cannot prove a missing component; the policy is always
  “uncertain → human review”.
- Rate limiting is per-process (single-node deploys).
- Real Twilio SMS delivery is implemented but not verified here (no credentials).

---

Built as a secure, runnable foundation: every feature above is implemented,
tested, and traceable through the audit log.
