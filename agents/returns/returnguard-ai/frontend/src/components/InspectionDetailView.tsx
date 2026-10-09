import { useState } from 'react'
import { DetectionCanvas } from './DetectionCanvas'
import { CVStatusBadge, DecisionBadge, ObservationBadge } from './StatusBadge'
import { Alert, Badge, Card, KeyValue } from './ui'
import type { InspectionDetail } from '../types/api'

/**
 * Full evidence view for one inspection: original photo with real detection
 * boxes, real OCR output, structured evidence and the deterministic decision
 * with its persisted rationale. Nothing here is synthesized client-side.
 */
export function InspectionDetailView({ inspection }: { inspection: InspectionDetail }) {
  const [showBoxes, setShowBoxes] = useState(true)
  const ocr = inspection.ocr
  const run = inspection.detection_run
  const evidence = inspection.evidence?.payload
  const decision = inspection.decision

  return (
    <div className="flex flex-col gap-4">
      <Card title="Product photo" subtitle={`${inspection.image.width}×${inspection.image.height} · ${(inspection.image.size_bytes / 1024).toFixed(0)} KB · SHA-256 ${inspection.image.sha256.slice(0, 12)}…`}>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            <input
              type="checkbox"
              checked={showBoxes}
              onChange={(e) => setShowBoxes(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            Show detection boxes
          </label>
          <a
            href={inspection.image.url}
            download={inspection.image.original_name || 'inspection.jpg'}
            className="inline-flex min-h-11 items-center rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Download original
          </a>
        </div>
        <div className="mt-3">
          <DetectionCanvas
            imageUrl={inspection.image.url}
            detections={showBoxes && run ? run.detections : []}
            width={inspection.image.width}
            height={inspection.image.height}
          />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="OCR result" subtitle={ocr ? `${ocr.engine}${ocr.engine_version ? ` ${ocr.engine_version}` : ''} · ${ocr.processing_ms} ms` : undefined}>
          {ocr ? (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <CVStatusBadge status={ocr.status} kind="ocr" />
                {ocr.mean_confidence !== null && <Badge tone="slate">Mean confidence {ocr.mean_confidence}%</Badge>}
              </div>
              {ocr.error && <Alert kind="warning">{ocr.error}</Alert>}
              {ocr.full_text ? (
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-800">{ocr.full_text}</pre>
              ) : (
                <p className="text-sm text-slate-500">
                  {ocr.status === 'NO_TEXT_DETECTED'
                    ? 'No readable text was detected in this photo. The photo can still support visual inspection.'
                    : 'No text available.'}
                </p>
              )}
              {ocr.blocks.length > 0 && (
                <details className="rounded-lg border border-slate-200 p-3">
                  <summary className="cursor-pointer text-sm font-medium text-slate-700">Recognized text blocks ({ocr.blocks.length})</summary>
                  <ul className="mt-2 space-y-1 text-sm text-slate-700">
                    {ocr.blocks.map((b, i) => (
                      <li key={i} className="flex items-center justify-between gap-3">
                        <span className="font-mono">{b.text}</span>
                        {b.confidence !== null && <span className="text-xs text-slate-400">{b.confidence}%</span>}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No OCR result recorded.</p>
          )}
        </Card>

        <Card
          title="Object detection"
          subtitle={run ? `${run.model_name || 'model'} · ${run.device} · conf ≥ ${run.confidence_threshold} · ${run.inference_ms} ms` : undefined}
        >
          {run ? (
            <div className="flex flex-col gap-3">
              <CVStatusBadge status={run.status} kind="detection" />
              {run.error && <Alert kind="warning">{run.error}</Alert>}
              {run.detections.length > 0 ? (
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                      <th className="py-2">Class</th>
                      <th className="py-2">Confidence</th>
                      <th className="py-2">Bounding box (x1,y1,x2,y2)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.detections.map((d, i) => (
                      <tr key={i} className="border-b border-slate-100">
                        <td className="py-2 font-medium text-slate-800">{d.class_label}</td>
                        <td className="py-2">{(d.confidence * 100).toFixed(1)}%</td>
                        <td className="py-2 font-mono text-xs text-slate-500">{d.bbox.join(', ')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-slate-500">
                  {run.status === 'OK'
                    ? 'The model ran successfully but detected no objects above the confidence threshold.'
                    : 'No detections available because inference did not complete.'}
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No detection run recorded.</p>
          )}
        </Card>
      </div>

      {inspection.ai_analysis && (
        <Card
          title="AI visual analysis (Groq / Qwen)"
          subtitle={`${inspection.ai_analysis.provider} · ${inspection.ai_analysis.model || 'model n/a'} · ${inspection.ai_analysis.latency_ms} ms · ${inspection.ai_analysis.attempts} attempt(s)`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <CVStatusBadge status={inspection.ai_analysis.status} kind="ai" />
            {inspection.ai_analysis.status === 'OK' && inspection.ai_analysis.payload && (
              <span className="text-sm text-slate-600">
                identity {(inspection.ai_analysis.payload.identity as string) ?? '—'} ·
                condition {(inspection.ai_analysis.payload.condition_grade as string) ?? '—'}
                {(inspection.ai_analysis.payload.confidence as number) != null &&
                  ` · confidence ${Math.round(((inspection.ai_analysis.payload.confidence as number) ?? 0) * 100)}%`}
              </span>
            )}
          </div>
          {inspection.ai_analysis.error && (
            <p className="mt-2 text-sm text-amber-700">{inspection.ai_analysis.error}</p>
          )}
          <p className="mt-2 text-xs text-slate-500">
            Model output is schema-validated evidence; it can never approve a return on its own.
          </p>
        </Card>
      )}

      {evidence && (
        <Card title="Structured evidence" subtitle={`Evidence schema v${evidence.schema_version}${evidence.view_type ? ` · view: ${evidence.view_type}` : ''}`}>
          <div className="flex flex-col gap-4">
            <div>
              <h3 className="mb-1 text-sm font-semibold text-slate-800">A. Product identity</h3>
              {evidence.identity ? (
                <>
                  <KeyValue
                    items={[
                      { label: 'Expected SKU', value: evidence.identity.expected_sku },
                      {
                        label: 'Verdict',
                        value: <Badge tone={evidence.identity.verdict === 'PASS' ? 'green' : evidence.identity.verdict === 'FAIL' ? 'red' : 'amber'}>{evidence.identity.verdict}</Badge>,
                      },
                      { label: 'SKU found in text', value: evidence.identity.sku_found_in_ocr ? 'Yes' : 'No' },
                      { label: 'Evidence sources', value: evidence.identity.sources.join(', ') || '—' },
                    ]}
                  />
                  <ul className="mt-1 list-inside list-disc text-xs text-slate-500">
                    {evidence.identity.notes.map((n, i) => <li key={i}>{n}</li>)}
                  </ul>
                </>
              ) : (
                <p className="text-sm text-slate-500">No identity assessment recorded.</p>
              )}
            </div>

            <div>
              <h3 className="mb-1 text-sm font-semibold text-slate-800">B. Completeness (expected components)</h3>
              {evidence.components.length === 0 ? (
                <p className="text-sm text-slate-500">No expected components were defined for this return.</p>
              ) : (
                <ul className="space-y-2">
                  {evidence.components.map((c) => (
                    <li key={c.name} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium text-slate-800">{c.name}</span>
                        <ObservationBadge observation={c.observation} />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{c.note}</p>
                      {c.matched_detections.length > 0 && (
                        <p className="mt-1 font-mono text-xs text-slate-500">
                          matched: {c.matched_detections.map((m) => `${m.class_label} ${(m.confidence * 100).toFixed(0)}%`).join(', ')}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2 text-xs text-slate-500">
                “Not observed” in standard photos is never treated as missing; CONFIRMED_MISSING
                requires a contents-layout view.
              </p>
            </div>

            <div>
              <h3 className="mb-1 text-sm font-semibold text-slate-800">C. Condition</h3>
              {evidence.condition ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={evidence.condition.grade === 'UNKNOWN' ? 'amber' : 'blue'}>{evidence.condition.grade}</Badge>
                    {evidence.condition.assessed_by && <span className="text-xs text-slate-500">assessed by {evidence.condition.assessed_by}</span>}
                  </div>
                  {evidence.condition.reasoning && <p className="mt-1 text-sm text-slate-600">{evidence.condition.reasoning}</p>}
                  {evidence.condition.visible_defects.length > 0 && (
                    <ul className="mt-1 list-inside list-disc text-sm text-slate-600">
                      {evidence.condition.visible_defects.map((d, i) => <li key={i}>{d}</li>)}
                    </ul>
                  )}
                  <p className="mt-1 text-xs text-slate-500">{evidence.condition.note}</p>
                </>
              ) : (
                <p className="text-sm text-slate-500">No condition assessment recorded.</p>
              )}
            </div>

            <div>
              <h3 className="mb-1 text-sm font-semibold text-slate-800">D. Recommended disposition</h3>
              {decision?.disposition ? (
                <Badge tone="blue">{decision.disposition}</Badge>
              ) : (
                <p className="text-sm text-slate-500">No confident disposition — evidence insufficient or withheld.</p>
              )}
            </div>

            {evidence.uncertainties.length > 0 && (
              <div>
                <h3 className="mb-1 text-sm font-semibold text-slate-800">Uncertainties</h3>
                <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
                  {evidence.uncertainties.map((u, i) => (
                    <li key={i}>{u}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>
      )}

      {decision && (
        <Card title="Automated decision" subtitle={`Decision engine v${decision.engine_version} · ${new Date(decision.decided_at).toLocaleString()}`}>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <DecisionBadge outcome={decision.outcome} />
            {decision.disposition && <Badge tone="blue">Disposition: {decision.disposition}</Badge>}
            {decision.outcome === 'MANUAL_REVIEW' && <span className="text-sm text-slate-500">A human reviewer must resolve this return.</span>}
          </div>
          <ul className="space-y-2">
            {decision.rationale.map((r, i) => (
              <li key={i} className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm">
                <Badge tone={r.outcome === 'supporting' ? 'green' : r.outcome === 'reject' ? 'red' : 'amber'}>{r.rule_id}</Badge>
                <span className="text-slate-700">{r.explanation}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {inspection.reviews.length > 0 && (
        <Card title="Human review history">
          <ul className="space-y-2">
            {inspection.reviews.map((r) => (
              <li key={r.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <DecisionBadge outcome={r.outcome} />
                  {r.overrides_automated && <Badge tone="amber">Overrides automated decision</Badge>}
                  <span className="text-xs text-slate-400">{new Date(r.created_at).toLocaleString()}</span>
                </div>
                <p className="mt-1 text-slate-700">{r.reason}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
