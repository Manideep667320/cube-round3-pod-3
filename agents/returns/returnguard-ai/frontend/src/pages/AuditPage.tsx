import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import * as adminService from '../services/admin'
import { Alert, Badge, Button, Card, EmptyState, Input, Label, Spinner } from '../components/ui'

const PAGE_SIZE = 50

export function AuditPage() {
  const [offset, setOffset] = useState(0)
  const [actionFilter, setActionFilter] = useState('')
  const [entityIdFilter, setEntityIdFilter] = useState('')

  const { data, loading, error, reload } = useAsync(
    () =>
      adminService.getAudit({
        limit: PAGE_SIZE,
        offset,
        action: actionFilter.trim() || undefined,
        entity_id: entityIdFilter.trim() || undefined,
      }),
    [offset, actionFilter, entityIdFilter],
  )

  return (
    <Card
      title="Audit history"
      subtitle="Append-only record of security-relevant events. Secrets are redacted."
      actions={
        <Button variant="secondary" onClick={reload}>
          Refresh
        </Button>
      }
    >
      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="audit-action">Filter by action</Label>
          <Input
            id="audit-action"
            placeholder="e.g. QR_SCANNED"
            value={actionFilter}
            onChange={(e) => {
              setOffset(0)
              setActionFilter(e.target.value)
            }}
          />
        </div>
        <div>
          <Label htmlFor="audit-entity">Filter by entity ID</Label>
          <Input
            id="audit-entity"
            placeholder="UUID of a return, inspection…"
            value={entityIdFilter}
            onChange={(e) => {
              setOffset(0)
              setEntityIdFilter(e.target.value)
            }}
          />
        </div>
      </div>

      {loading ? (
        <Spinner label="Loading audit events…" />
      ) : error ? (
        <Alert title="Could not load audit history">{error}</Alert>
      ) : !data || data.length === 0 ? (
        <EmptyState title="No audit events match the current filters" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                <th className="py-2 pr-4">Time</th>
                <th className="py-2 pr-4">Action</th>
                <th className="py-2 pr-4">Actor</th>
                <th className="py-2 pr-4">Entity</th>
                <th className="py-2">Details</th>
              </tr>
            </thead>
            <tbody>
              {data.map((e) => (
                <tr key={e.id} className="border-b border-slate-100 align-top hover:bg-slate-50">
                  <td className="py-2 pr-4 whitespace-nowrap text-slate-500">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-4">
                    <Badge tone={e.action.includes('FAILED') || e.action.includes('REJECTED') ? 'red' : 'blue'}>{e.action}</Badge>
                  </td>
                  <td className="py-2 pr-4 text-slate-600">{e.actor_role ? `${e.actor_role}${e.actor_id ? ` ${e.actor_id.slice(0, 8)}` : ''}` : 'SYSTEM'}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-slate-600">
                    {e.entity_type}:{e.entity_id.slice(0, 13)}
                  </td>
                  <td className="py-2 font-mono text-xs text-slate-500">{JSON.stringify(e.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex items-center justify-between">
        <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
          <ChevronLeft className="h-4 w-4" aria-hidden />
          Newer
        </Button>
        <span className="text-sm text-slate-500">offset {offset}</span>
        <Button variant="secondary" disabled={!data || data.length < PAGE_SIZE} onClick={() => setOffset(offset + PAGE_SIZE)}>
          Older
          <ChevronRight className="h-4 w-4" aria-hidden />
        </Button>
      </div>
    </Card>
  )
}
