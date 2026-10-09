# Provenance: Returns Manager Agent

## Origin & Ownership
- **Agent Stage:** `returns`
- **Agent ID:** `returns-manager@1.0.0`
- **Owner:** `@Adithya-charan`
- **Repository:** [cube-round3-pod-3](https://github.com/Manideep667320/cube-round3-pod-3)
- **Target Path:** `agents/returns`

## Architecture & Integration
The Returns Manager agent implements evidence-based return product inspection:
1. **Multitenancy Isolation:** Enforces strict `org_id` scoping; raises `LookupError` (HTTP 404) on cross-tenant requests.
2. **Product Identity Matching:** Verifies returned item barcode/OCR label against expected order SKU (`identity_match`).
3. **Accessory Completeness Check:** Verifies expected components against missing parts (`completeness`).
4. **Amazon Published Condition Scale:** Classifies item condition into standard Amazon grades (`New`, `Used - Like New`, `Used - Very Good`, `Used - Good`, `Used - Acceptable`, `Unsellable`).
5. **Evidence-Backed Disposition:** Determines deterministic disposition (`restock`, `refurbish`, `liquidate`, `dispose`, `pending_review`).
6. **Multimodal AI & Computer Vision:** Integrates RapidOCR, YOLO object detection, and Groq API Qwen Vision (`qwen/qwen3.8-27b`), with graceful deterministic fallback.
7. **Evidence Contract v1.0 Compliance:** Produces canonical schema-validated Evidence Records (`RTN-*`) sealed with SHA-256 content hashes.
