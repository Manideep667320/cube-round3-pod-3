/** TypeScript mirrors of the backend Pydantic response/request schemas. */

export interface User {
  id: string
  username: string
  full_name: string
  role: 'ADMIN' | 'AGENT' | 'OPERATOR'
  phone: string | null
  phone_verified: boolean
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface ExpectedComponent {
  id?: string
  name: string
  yolo_class_hints: string
  ocr_text_hint: string
}

export interface ExpectedComponentInput {
  name: string
  yolo_class_hints: string[]
  ocr_text_hint?: string
}

export interface QRAuth {
  id: string
  return_id: string
  token_prefix: string
  status: 'ACTIVE' | 'USED' | 'REVOKED' | 'EXPIRED'
  created_at: string
  expires_at: string
  used_at: string | null
  revoked_at: string | null
}

export interface QRGenerateResponse {
  qr_authorization: QRAuth
  token: string
  qr_png_base64: string
  scan_value: string
}

export interface ReturnRecord {
  id: string
  return_code: string
  order_reference: string
  expected_sku: string
  catalogue_product_id: string | null
  product_description: string
  status: string
  assigned_agent_id: string | null
  created_by_id: string
  created_at: string
  updated_at: string
  expected_components: ExpectedComponent[]
}

export interface OTPChallengeSummary {
  id: string
  status: string
  attempts: number
  issued_at: string
  expires_at: string
  verified_at: string | null
}

export interface InspectionSummary {
  id: string
  status: string
  created_at: string
  completed_at: string | null
  decision_outcome: string | null
  image_url: string | null
}

export interface ReturnDetail extends ReturnRecord {
  qr_authorizations: QRAuth[]
  otp_summary: OTPChallengeSummary[]
  inspections: InspectionSummary[]
}

export interface QRScanResponse {
  scan_token: string
  return_id: string
  return_code: string
  product_description: string
  assigned_agent_id: string
}

export interface OTPRequestOut {
  masked_phone: string
  expires_at: string
  resend_available_at: string
  max_attempts: number
}

export interface OTPVerifyResponse {
  inspection_token: string
  return_id: string
  return_code: string
}

export interface OCRBlock {
  text: string
  confidence: number | null
  box: number[][] | null
}

export interface OCRResult {
  id: string
  engine: string
  engine_version: string
  status: string
  full_text: string
  mean_confidence: number | null
  blocks: OCRBlock[]
  processing_ms: number
  error: string | null
}

export interface Detection {
  class_id: number
  class_label: string
  confidence: number
  bbox: number[]
}

export interface DetectionRun {
  id: string
  model_name: string
  device: string
  confidence_threshold: number
  status: string
  inference_ms: number
  error: string | null
  detections: Detection[]
}

export interface EvidenceRecord {
  id: string
  payload: EvidencePayload
}

export interface EvidencePayload {
  schema_version: string
  view_type?: string
  /** v2 four-dimension evidence */
  identity?: {
    verdict: 'PASS' | 'FAIL' | 'UNCERTAIN'
    expected_sku: string
    sku_found_in_ocr: boolean
    sources: string[]
    detected_classes: string[]
    notes: string[]
  }
  components: {
    name: string
    observation: 'OBSERVED' | 'NOT_OBSERVED' | 'NOT_VISIBLE' | 'UNCERTAIN' | 'CONFIRMED_MISSING'
    evidence_sources: string[]
    matched_detections: { class_label: string; confidence: number; bbox: number[] }[]
    note: string
  }[]
  condition?: {
    grade: string
    source: string
    assessed_by: string | null
    reasoning: string
    visible_defects: string[]
    note: string
  }
  ai_summary?: {
    provider: string
    model: string
    status: string
    identity: string | null
    condition_grade: string | null
    confidence: number | null
    latency_ms?: number
    attempts?: number
    error?: string | null
  }
  ocr_summary: { engine: string; status: string; mean_confidence: number | null; text_excerpt: string; processing_ms: number }
  yolo_summary: {
    model_name: string
    status: string
    device: string
    confidence_threshold: number
    inference_ms: number
    detection_count: number
    class_labels: string[]
    notes: string[]
  }
  uncertainties: string[]
}

export interface Decision {
  id: string
  outcome: 'APPROVE' | 'REJECT' | 'MANUAL_REVIEW'
  disposition: 'RESTOCK' | 'REFURBISH' | 'LIQUIDATE' | 'DISPOSE' | null
  rationale: { rule_id: string; outcome: string; explanation: string }[]
  engine_version: string
  decided_at: string
}

export interface Review {
  id: string
  inspection_id: string
  return_id: string
  reviewer_id: string
  outcome: 'APPROVE' | 'REJECT'
  reason: string
  overrides_automated: boolean
  created_at: string
}

export interface InspectionDetail {
  id: string
  return_id: string
  return_code: string
  agent_id: string
  status: string
  view_type: string
  created_at: string
  completed_at: string | null
  error_message: string | null
  image: {
    url: string
    original_name: string
    content_type: string
    size_bytes: number
    sha256: string
    width: number
    height: number
  }
  ocr: OCRResult | null
  detection_run: DetectionRun | null
  ai_analysis?: AIAnalysis | null
  evidence: EvidenceRecord | null
  decision: Decision | null
  reviews: Review[]
}

export interface AIAnalysis {
  id: string
  provider: string
  model: string
  status: string
  latency_ms: number
  attempts: number
  payload: Record<string, unknown>
  error: string | null
}

export interface CatalogueProduct {
  id: string
  sku: string
  name: string
  description: string
  default_components: { name: string; yolo_class_hints: string[]; ocr_text_hint: string }[]
  identifying_features: string[]
  created_by_id: string
  created_at: string
}

export interface ReviewQueueItem {
  id: string
  return_id: string
  agent_id: string
  status: string
  created_at: string
  completed_at: string | null
  decision_outcome: string | null
  image_url: string | null
  ocr_status: string | null
  detection_status: string | null
  return_code: string
  expected_sku: string
  product_description: string
}

export interface AuditEvent {
  id: string
  actor_id: string | null
  actor_role: string | null
  action: string
  entity_type: string
  entity_id: string
  details: Record<string, unknown>
  created_at: string
}

export interface Stats {
  returns_by_status: Record<string, number>
  total_returns: number
  total_inspections: number
  decisions: Record<string, number>
  otp_challenges: Record<string, number>
  agents: number
}

export interface HealthReport {
  status: string
  app_env: string
  database: { status: string; url_scheme: string }
  sms_provider: string
  ocr: { configured_engine: string; available: boolean; engine: string | null; version: string }
  yolo: { configured_model_path: string; weights_present: boolean; confidence_threshold: number; device: string; loaded: boolean }
  storage: { status: string; writable: boolean }
}
