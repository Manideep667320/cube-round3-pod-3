import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { QrCode, XCircle } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import * as returnsService from '../services/returns'
import { useToast } from '../app/ToastContext'
import { Alert, Badge, Button, Card, Dialog, KeyValue, Spinner } from '../components/ui'
import { ReturnStatusBadge, DecisionBadge } from '../components/StatusBadge'
import { QRDisplay } from '../components/QRDisplay'
import { errorMessage } from '../hooks/useAsync'
import type { QRGenerateResponse } from '../types/api'

export function ReturnDetailPage() {
  const { returnId = '' } = useParams()
  const detail = useAsync(() => returnsService.getReturn(returnId), [returnId])
  const agents = useAsync(() => import('../services/admin').then((m) => m.listUsers()))
  const { pushSuccess, pushError } = useToast()
  const [qrResult, setQrResult] = useState<QRGenerateResponse | null>(null)
  const [busy, setBusy] = useState(false)

  if (detail.loading) return <Spinner label="Loading return…" />
  if (detail.error) return <Alert title="Could not load return">{detail.error}</Alert>
  const ret = detail.data
  if (!ret) return null

  const agent = agents.data?.find((u) => u.id === ret.assigned_agent_id)

  const act = async (fn: () => Promise<unknown>, successMsg: string) => {
    setBusy(true)
    try {
      await fn()
      pushSuccess(successMsg)
      detail.reload()
    } catch (e) {
      pushError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/admin/returns" className="text-sm font-medium text-brand-600 hover:underline">← Back to returns</Link>
          <h1 className="mt-1 text-xl font-semibold text-slate-900">
            Return <span className="font-mono">{ret.return_code}</span>
          </h1>
        </div>
        <ReturnStatusBadge status={ret.status} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Return details">
          <KeyValue
            items={[
              { label: 'Order reference', value: ret.order_reference },
              { label: 'Expected SKU', value: ret.expected_sku },
              { label: 'Assigned agent', value: agent ? `${agent.full_name || agent.username}${agent.phone_verified ? '' : ' (phone unverified)'}` : ret.assigned_agent_id ?? '—' },
              { label: 'Created', value: new Date(ret.created_at).toLocaleString() },
              { label: 'Description', value: ret.product_description || '—' },
            ]}
          />
          <h3 className="mt-4 mb-2 text-sm font-semibold text-slate-800">Expected components</h3>
          {ret.expected_components.length === 0 ? (
            <p className="text-sm text-slate-500">None defined.</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {ret.expected_components.map((c) => (
                <li key={c.id ?? c.name}>
                  <Badge tone="blue">{c.name}</Badge>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="danger"
              loading={busy}
              onClick={() => act(() => returnsService.cancelReturn(ret.id), 'Return cancelled.')}
            >
              <XCircle className="h-4 w-4" aria-hidden />
              Cancel return
            </Button>
          </div>
        </Card>

        <Card
          title="Hidden QR authorization"
          subtitle="Single-use, bound to this return and agent. No OTP or personal data inside."
          actions={
            <Button
              loading={busy}
              onClick={async () => {
                setBusy(true)
                try {
                  const result = await returnsService.generateQR(ret.id)
                  setQrResult(result)
                  detail.reload()
                } catch (e) {
                  pushError(errorMessage(e))
                } finally {
                  setBusy(false)
                }
              }}
            >
              <QrCode className="h-4 w-4" aria-hidden />
              Generate QR
            </Button>
          }
        >
          {ret.qr_authorizations.length === 0 ? (
            <p className="text-sm text-slate-500">No QR authorizations yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {ret.qr_authorizations.map((auth) => (
                <li key={auth.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={auth.status === 'ACTIVE' ? 'green' : auth.status === 'USED' ? 'blue' : 'slate'}>{auth.status}</Badge>
                    <span className="font-mono text-slate-600">{auth.token_prefix}…</span>
                    <span className="text-xs text-slate-400">expires {new Date(auth.expires_at).toLocaleString()}</span>
                  </div>
                  {auth.status === 'ACTIVE' && (
                    <Button
                      variant="secondary"
                      loading={busy}
                      onClick={() => act(() => returnsService.revokeQR(auth.id), 'QR authorization revoked.')}
                    >
                      Revoke
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="OTP verification status" subtitle="Codes are never shown here — only challenge metadata">
        {ret.otp_summary.length === 0 ? (
          <p className="text-sm text-slate-500">No OTP challenges issued yet.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {ret.otp_summary.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2">
                <Badge tone={c.status === 'VERIFIED' ? 'green' : c.status === 'PENDING' ? 'amber' : 'slate'}>{c.status}</Badge>
                <span className="text-slate-600">attempts {c.attempts}</span>
                <span className="text-xs text-slate-400">issued {new Date(c.issued_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Inspections" subtitle="Real OCR and YOLO results per uploaded photo">
        {ret.inspections.length === 0 ? (
          <p className="text-sm text-slate-500">No inspections yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {ret.inspections.map((insp) => (
              <li key={insp.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex items-center gap-2">
                  <Badge tone={insp.status === 'COMPLETED' ? 'green' : 'amber'}>{insp.status}</Badge>
                  <DecisionBadge outcome={insp.decision_outcome} />
                  <span className="text-xs text-slate-400">{new Date(insp.created_at).toLocaleString()}</span>
                </div>
                <Link to={`/admin/inspections/${insp.id}`} className="font-medium text-brand-600 hover:underline">
                  View evidence →
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Dialog open={qrResult !== null} title="QR generated — shown once" onClose={() => setQrResult(null)}>
        {qrResult && (
          <QRDisplay qrPngBase64={qrResult.qr_png_base64} token={qrResult.token} returnCode={ret.return_code} />
        )}
      </Dialog>
    </div>
  )
}
