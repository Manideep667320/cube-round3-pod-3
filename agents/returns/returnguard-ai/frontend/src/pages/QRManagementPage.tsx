import { useAsync } from '../hooks/useAsync'
import { api } from '../services/apiClient'
import * as returnsService from '../services/returns'
import { useToast } from '../app/ToastContext'
import { Alert, Badge, Button, Card, EmptyState, Spinner } from '../components/ui'
import { errorMessage } from '../hooks/useAsync'
import type { QRAuth } from '../types/api'

type QIRow = QRAuth & { return_code: string }

export function QRManagementPage() {
  const { data, loading, error, reload } = useAsync(() => api.get<QIRow[]>('/api/qr'))
  const { pushSuccess, pushError } = useToast()

  const revoke = async (id: string) => {
    try {
      await returnsService.revokeQR(id)
      pushSuccess('QR authorization revoked.')
      reload()
    } catch (e) {
      pushError(errorMessage(e))
    }
  }

  return (
    <Card title="QR authorizations" subtitle="All hidden QR tokens across returns. Only hashes are stored server-side.">
      {loading ? (
        <Spinner label="Loading QR authorizations…" />
      ) : error ? (
        <Alert title="Could not load QR authorizations">{error}</Alert>
      ) : !data || data.length === 0 ? (
        <EmptyState title="No QR authorizations yet" hint="Generate one from a return's detail page." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                <th className="py-2 pr-4">Return</th>
                <th className="py-2 pr-4">Token prefix</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Created</th>
                <th className="py-2 pr-4">Expires</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 pr-4 font-mono font-medium">{row.return_code}</td>
                  <td className="py-2 pr-4 font-mono text-slate-600">{row.token_prefix}…</td>
                  <td className="py-2 pr-4">
                    <Badge tone={row.status === 'ACTIVE' ? 'green' : row.status === 'USED' ? 'blue' : 'slate'}>{row.status}</Badge>
                  </td>
                  <td className="py-2 pr-4 text-slate-500">{new Date(row.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-4 text-slate-500">{new Date(row.expires_at).toLocaleString()}</td>
                  <td className="py-2 text-right">
                    {row.status === 'ACTIVE' && (
                      <Button variant="secondary" onClick={() => revoke(row.id)}>
                        Revoke
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
