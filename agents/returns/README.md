# agents/returns/  ·  Returns Manager Agent

**Owner:** `@Manideep667320` (`returns-manager@1.0.0`)

The **Returns Manager Agent** evaluates product returns to verify product identity, check accessory completeness, grade item condition using Amazon's published condition scale, and determine evidence-backed dispositions.

---

## Capabilities & Architecture

| Component | Description |
|---|---|
| **Reads (inputs)** | Returned item captures/photos, expected SKU, expected parts list |
| **Reads (upstream)** | Pack & Receiving stage evidence records |
| **Checks Produced** | `identity_match`, `completeness`, `condition` |
| **Condition Scale** | Amazon Published Condition Scale (`New`, `Used - Like New`, `Used - Very Good`, `Used - Good`, `Used - Acceptable`, `Unsellable`) |
| **Dispositions** | `restock`, `refurbish`, `liquidate`, `dispose`, `pending_review` |
| **AI / Vision Pipeline** | RapidOCR + YOLOv8n + Groq API Qwen 3.8 27B Vision Model (`qwen/qwen3.8-27b`) |

---

## Directory Structure

```text
agents/returns/
├── app.py              ← FastAPI server & handle(request) entry point
├── agent.json          ← Agent metadata & configuration
├── engine.py           ← Returns inspection logic & check builder
├── condition.py        ← Amazon published condition classifier & disposition rules
├── vision.py           ← Multimodal vision pipeline (OCR, YOLO, Groq Qwen Vision)
├── PROVENANCE.md       ← Component provenance & architectural notes
├── README.md           ← Agent documentation
└── tests/              ← Unit & contract integration tests
    └── test_returns.py
```

---

## Running the Returns Agent

```bash
# Serve over HTTP (Port 8104)
python -m uvicorn agents.returns.app:app --port 8104

# Run tests
pytest tests/integration/test_agent_contracts.py -k returns
pytest agents/returns/tests/
```
