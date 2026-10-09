import { Link, useNavigate } from 'react-router-dom'
import { Camera, ScanLine } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import * as returnsService from '../services/returns'
import { Alert, Badge, Card, EmptyState, Spinner } from '../components/ui'
import { ReturnStatusBadge, DecisionBadge } from '../components/StatusBadge'

export function DeliveryDashboard() {
  const { data, loading, error, reload } = useAsync(() => returnsService.listAssignedReturns())
  const navigate = useNavigate()

  const actionable = (status: string) => status === 'AWAITING_SCAN' || status === 'AWAITING_OTP' || status === 'AWAITING_INSPECTION'

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="My assigned returns"
        subtitle="Only returns assigned to you are visible here"
        actions={
          <>
            <button onClick={reload} className="text-sm font-medium text-brand-600 hover:underline">
              Refresh
            </button>
            <Link
              to="/agent/scan"
              className="inline-flex min-h-11 items-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              <ScanLine className="mr-2 h-4 w-4" aria-hidden />
              Scan QR
            </Link>
          </>
        }
      >
        {loading ? (
          <Spinner label="Loading your returns…" />
        ) : error ? (
          <Alert title="Could not load returns">{error}</Alert>
        ) : !data || data.length === 0 ? (
          <EmptyState title="No returns are assigned to you" hint="New assignments appear here automatically." />
        ) : (
          <ul className="flex flex-col gap-3">
            {data.map((r) => (
              <li key={r.id} className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-semibold text-slate-800">{r.return_code}</span>
                    <ReturnStatusBadge status={r.status} />
                  </div>
                  <p className="mt-1 text-sm text-slate-600">
                    {r.product_description || 'No description'} · SKU <span className="font-medium">{r.expected_sku}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {r.expected_components.length} expected component{r.expected_components.length === 1 ? '' : 's'}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {actionable(r.status) ? (
                    <button
                      onClick={() => navigate('/agent/scan', { state: { returnCode: r.return_code } })}
                      className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
                    >
                      <Camera className="h-4 w-4" aria-hidden />
                      Start scan & inspection
                    </button>
                  ) : (
                    <Badge tone="slate">No action needed</Badge>
                  )}
                  {r.status === 'NEEDS_REVIEW' && <DecisionBadge outcome="MANUAL_REVIEW" />}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
