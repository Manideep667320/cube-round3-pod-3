import { Link } from 'react-router-dom'
import { useAsync } from '../hooks/useAsync'
import * as adminService from '../services/admin'
import { Alert, Badge, Card, EmptyState, Spinner } from '../components/ui'

export function ReviewQueuePage() {
  const { data, loading, error, reload } = useAsync(() => adminService.getReviewQueue())

  return (
    <Card
      title="Review queue"
      subtitle="Returns whose automated decision needs a human. Resolving preserves the original automated decision."
      actions={
        <button onClick={reload} className="text-sm font-medium text-brand-600 hover:underline">
          Refresh
        </button>
      }
    >
      {loading ? (
        <Spinner label="Loading review queue…" />
      ) : error ? (
        <Alert title="Could not load review queue">{error}</Alert>
      ) : !data || data.length === 0 ? (
        <EmptyState title="The review queue is empty" hint="Returns routed to MANUAL_REVIEW appear here." />
      ) : (
        <ul className="flex flex-col gap-3">
          {data.map((item) => (
            <li key={item.id} className="flex flex-col gap-2 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-semibold text-slate-800">{item.return_code}</span>
                  <Badge tone="amber">Needs review</Badge>
                  <Badge tone="slate">OCR: {item.ocr_status ?? '—'}</Badge>
                  <Badge tone="slate">Detection: {item.detection_status ?? '—'}</Badge>
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  SKU <span className="font-medium">{item.expected_sku}</span>
                  {item.product_description ? ` · ${item.product_description}` : ''}
                </p>
                <p className="mt-0.5 text-xs text-slate-400">{new Date(item.created_at).toLocaleString()}</p>
              </div>
              <Link
                to={`/admin/inspections/${item.id}`}
                className="inline-flex min-h-11 items-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
              >
                Review evidence →
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
