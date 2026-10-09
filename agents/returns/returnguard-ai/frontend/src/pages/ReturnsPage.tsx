import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import * as returnsService from '../services/returns'
import * as adminService from '../services/admin'
import * as catalogueService from '../services/catalogue'
import { useToast } from '../app/ToastContext'
import { Alert, Button, Card, Dialog, EmptyState, Input, Label, Select, Spinner, Textarea } from '../components/ui'
import { ReturnStatusBadge } from '../components/StatusBadge'
import { errorMessage } from '../hooks/useAsync'
import type { ExpectedComponentInput } from '../types/api'

export function ReturnsPage() {
  const returns = useAsync(() => returnsService.listReturns())
  const agents = useAsync(() =>
    adminService.listUsers().then((us) => us.filter((u) => u.role !== 'ADMIN' && u.is_active)),
  )
  const catalogue = useAsync(() => catalogueService.listCatalogue())
  const { pushSuccess, pushError } = useToast()
  const [creating, setCreating] = useState(false)

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Returns"
        subtitle="Every record below is persisted in the database"
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            New return
          </Button>
        }
      >
        {returns.loading ? (
          <Spinner label="Loading returns…" />
        ) : returns.error ? (
          <Alert title="Could not load returns">{returns.error}</Alert>
        ) : !returns.data || returns.data.length === 0 ? (
          <EmptyState title="No returns yet" hint="Create your first return to generate a hidden QR authorization." action={<Button onClick={() => setCreating(true)}>New return</Button>} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                  <th className="py-2 pr-4">Code</th>
                  <th className="py-2 pr-4">Order ref</th>
                  <th className="py-2 pr-4">Expected SKU</th>
                  <th className="py-2 pr-4">Description</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Created</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {returns.data.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="py-2 pr-4 font-mono font-medium text-slate-800">{r.return_code}</td>
                    <td className="py-2 pr-4">{r.order_reference}</td>
                    <td className="py-2 pr-4">{r.expected_sku}</td>
                    <td className="max-w-56 truncate py-2 pr-4 text-slate-600">{r.product_description || '—'}</td>
                    <td className="py-2 pr-4"><ReturnStatusBadge status={r.status} /></td>
                    <td className="py-2 pr-4 text-slate-500">{new Date(r.created_at).toLocaleString()}</td>
                    <td className="py-2 text-right">
                      <Link to={`/admin/returns/${r.id}`} className="font-medium text-brand-600 hover:underline">
                        Manage →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <CreateReturnDialog
        open={creating}
        onClose={() => setCreating(false)}
        agents={agents.data ?? []}
        catalogue={catalogue.data ?? []}
        onCreated={(code) => {
          setCreating(false)
          pushSuccess(`Return ${code} created.`)
          returns.reload()
          agents.reload()
        }}
        onError={(m) => pushError(m)}
      />
    </div>
  )
}

function CreateReturnDialog({ open, onClose, agents, catalogue, onCreated, onError }: {
  open: boolean
  onClose: () => void
  agents: { id: string; username: string; full_name: string; phone_verified: boolean }[]
  catalogue: { id: string; sku: string; name: string }[]
  onCreated: (code: string) => void
  onError: (message: string) => void
}) {
  const [catalogueId, setCatalogueId] = useState('')
  const [orderRef, setOrderRef] = useState('')
  const [sku, setSku] = useState('')
  const [description, setDescription] = useState('')
  const [agentId, setAgentId] = useState('')
  const [components, setComponents] = useState<ExpectedComponentInput[]>([{ name: '', yolo_class_hints: [], ocr_text_hint: '' }])
  const [busy, setBusy] = useState(false)

  const reset = () => {
    setOrderRef('')
    setSku('')
    setDescription('')
    setAgentId('')
    setComponents([{ name: '', yolo_class_hints: [], ocr_text_hint: '' }])
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const created = await returnsService.createReturn({
        order_reference: orderRef.trim(),
        expected_sku: sku.trim(),
        product_description: description.trim(),
        assigned_agent_id: agentId || null,
        catalogue_product_id: catalogueId || null,
        expected_components: components
          .filter((c) => c.name.trim())
          .map((c) => ({
            name: c.name.trim(),
            yolo_class_hints: c.yolo_class_hints,
            ocr_text_hint: c.ocr_text_hint?.trim() ?? '',
          })),
      })
      reset()
      onCreated(created.return_code)
    } catch (err) {
      onError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} title="Create return" onClose={onClose} wide>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="catalogue-select" hint="optional — pre-fills expected components">Catalogue product</Label>
          <Select id="catalogue-select" value={catalogueId} onChange={(e) => setCatalogueId(e.target.value)}>
            <option value="">None (manual entry)</option>
            {catalogue.map((p) => (
              <option key={p.id} value={p.id}>
                {p.sku} — {p.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="order-ref">Order reference</Label>
            <Input id="order-ref" required value={orderRef} onChange={(e) => setOrderRef(e.target.value)} placeholder="ORD-123456" />
          </div>
          <div>
            <Label htmlFor="sku">Expected SKU / product identifier</Label>
            <Input id="sku" required value={sku} onChange={(e) => setSku(e.target.value)} placeholder="LAPTOP-X1-CARBON" />
          </div>
        </div>
        <div>
          <Label htmlFor="description">Product description</Label>
          <Textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="ThinkPad X1 Carbon laptop, grey, order from March" />
        </div>
        <div>
          <Label htmlFor="agent" hint={agents.length === 0 ? '— create a delivery agent first' : undefined}>Assigned delivery agent</Label>
          <Select id="agent" required value={agentId} onChange={(e) => setAgentId(e.target.value)}>
            <option value="">Select an agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.full_name || a.username} {a.phone_verified ? '' : '(phone not verified)'}
              </option>
            ))}
          </Select>
        </div>
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-slate-700">Expected components</legend>
          <p className="mb-2 text-xs text-slate-500">
            Component names are checked against YOLO detection classes; class hints improve matching (e.g. “charger” → “charger, power adapter”).
          </p>
          <div className="flex flex-col gap-2">
            {components.map((c, i) => (
              <div key={i} className="flex flex-col gap-2 sm:flex-row">
                <Input
                  aria-label={`Component ${i + 1} name`}
                  placeholder="Component name (e.g. charger)"
                  value={c.name}
                  onChange={(e) => setComponents(components.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                />
                <Input
                  aria-label={`Component ${i + 1} YOLO class hints`}
                  placeholder="YOLO class hints, comma separated"
                  value={c.yolo_class_hints.join(', ')}
                  onChange={(e) =>
                    setComponents(
                      components.map((x, j) =>
                        j === i ? { ...x, yolo_class_hints: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) } : x,
                      ),
                    )
                  }
                />
                <Button
                  type="button"
                  variant="ghost"
                  aria-label={`Remove component ${i + 1}`}
                  onClick={() => setComponents(components.filter((_, j) => j !== i))}
                  disabled={components.length === 1}
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                </Button>
              </div>
            ))}
          </div>
          <Button type="button" variant="secondary" className="mt-2" onClick={() => setComponents([...components, { name: '', yolo_class_hints: [], ocr_text_hint: '' }])}>
            Add component
          </Button>
        </fieldset>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Create return
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
