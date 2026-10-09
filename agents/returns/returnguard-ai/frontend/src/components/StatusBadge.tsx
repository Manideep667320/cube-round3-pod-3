import { Badge } from './ui'
import type { ReactNode } from 'react'

const RETURN_STATUS: Record<string, { label: string; tone: 'slate' | 'green' | 'red' | 'amber' | 'blue' }> = {
  PENDING: { label: 'Pending QR', tone: 'slate' },
  AWAITING_SCAN: { label: 'Awaiting scan', tone: 'blue' },
  AWAITING_OTP: { label: 'Awaiting OTP', tone: 'amber' },
  AWAITING_INSPECTION: { label: 'Awaiting photo', tone: 'amber' },
  INSPECTED: { label: 'Inspected', tone: 'blue' },
  NEEDS_REVIEW: { label: 'Needs review', tone: 'amber' },
  APPROVED: { label: 'Approved', tone: 'green' },
  REJECTED: { label: 'Rejected', tone: 'red' },
  CANCELLED: { label: 'Cancelled', tone: 'slate' },
}

export function ReturnStatusBadge({ status }: { status: string }) {
  const meta = RETURN_STATUS[status] ?? { label: status, tone: 'slate' as const }
  return <Badge tone={meta.tone}>{meta.label}</Badge>
}

const DECISION_TONE: Record<string, 'green' | 'red' | 'amber'> = {
  APPROVE: 'green',
  REJECT: 'red',
  MANUAL_REVIEW: 'amber',
}

export function DecisionBadge({ outcome }: { outcome: string | null }) {
  if (!outcome) return <Badge tone="slate">No decision</Badge>
  const tone = DECISION_TONE[outcome] ?? 'slate'
  const label = outcome === 'MANUAL_REVIEW' ? 'Human review' : outcome.charAt(0) + outcome.slice(1).toLowerCase()
  return <Badge tone={tone}>{label}</Badge>
}

const CV_TONE: Record<string, 'green' | 'red' | 'amber' | 'slate'> = {
  OK: 'green',
  NO_TEXT_DETECTED: 'slate',
  LOW_CONFIDENCE: 'amber',
  ENGINE_UNAVAILABLE: 'red',
  MODEL_UNAVAILABLE: 'red',
  TIMEOUT: 'red',
  FAILED: 'red',
  RATE_LIMITED: 'amber',
  MALFORMED: 'red',
  UNAVAILABLE: 'amber',
}

export function CVStatusBadge({ status, kind }: { status: string; kind: 'ocr' | 'detection' | 'ai' }) {
  const tone = CV_TONE[status] ?? 'slate'
  const labels: Record<string, string> = {
    OK: kind === 'ocr' ? 'Text extracted' : kind === 'ai' ? 'AI analysis complete' : 'Detections complete',
    NO_TEXT_DETECTED: 'No readable text',
    LOW_CONFIDENCE: 'Low confidence',
    ENGINE_UNAVAILABLE: 'OCR engine unavailable',
    MODEL_UNAVAILABLE: 'Model unavailable',
    UNAVAILABLE: 'AI analysis unavailable',
    RATE_LIMITED: 'Provider rate limited',
    MALFORMED: 'Invalid AI response',
    TIMEOUT: 'Timed out',
    FAILED: 'Processing failed',
  }
  return <Badge tone={tone}>{labels[status] ?? status}</Badge>
}

const OBSERVATION_TONE: Record<string, 'green' | 'amber' | 'slate' | 'red'> = {
  OBSERVED: 'green',
  UNCERTAIN: 'amber',
  NOT_VISIBLE: 'amber',
  NOT_OBSERVED: 'slate',
  CONFIRMED_MISSING: 'red',
}

export function ObservationBadge({ observation }: { observation: string }): ReactNode {
  const tone = OBSERVATION_TONE[observation] ?? 'slate'
  const label: Record<string, string> = {
    OBSERVED: 'Observed',
    UNCERTAIN: 'Uncertain',
    NOT_VISIBLE: 'Not visible',
    NOT_OBSERVED: 'Not observed',
    CONFIRMED_MISSING: 'Confirmed missing',
  }
  return <Badge tone={tone}>{label[observation] ?? observation}</Badge>
}
