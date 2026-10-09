import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import * as catalogueService from '../services/catalogue'
import { useToast } from '../app/ToastContext'
import { Alert, Badge, Button, Card, Dialog, EmptyState, Input, Label, Spinner, Textarea } from '../components/ui'
import { errorMessage } from '../hooks/useAsync'
import type { CatalogueProduct } from '../types/api'

/**
 * Admin-managed product catalogue: definitions the inspection pipeline compares
 * returns against (expected components, identifying features).
 */
export function CataloguePage() {
  const { data, loading, error, reload } = useAsync(() => catalogueService.listCatalogue())
  const { pushSuccess, pushError } = useToast()
  const [editing, setEditing] = useState<CatalogueProduct | 'new' | null>(null)

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Product catalogue"
        subtitle="Expected components and identifying features used by the inspection pipeline"
        actions={
          <Button onClick={() => setEditing('new')}>
            <Plus className="h-4 w-4" aria-hidden />
            New product
          </Button>
        }
      >
        {loading ? (
          <Spinner label="Loading catalogue…" />
        ) : error ? (
          <Alert title="Could not load catalogue">{error}</Alert>
        ) : !data || data.length === 0 ? (
          <EmptyState title="The catalogue is empty" hint="Add products so returns can reference their expected component lists." action={<Button onClick={() => setEditing('new')}>New product</Button>} />
        ) : (
          <ul className="flex flex-col gap-3">
            {data.map((p) => (
              <li key={p.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono font-semibold text-slate-800">{p.sku}</span>
                      <span className="text-sm text-slate-600">{p.name}</span>
                    </div>
                    <p className="mt-1 text-sm text-slate-500">{p.description || '—'}</p>
                  </div>
                  <Button variant="secondary" onClick={() => setEditing(p)}>
                    Edit
                  </Button>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {p.default_components.map((c) => (
                    <Badge key={c.name} tone="blue">{c.name}</Badge>
                  ))}
                </div>
                {p.identifying_features.length > 0 && (
                  <p className="mt-2 text-xs text-slate-500">Identifying: {p.identifying_features.join(' · ')}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {editing && (
        <CatalogueDialog
          product={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            pushSuccess('Catalogue saved.')
            reload()
          }}
          onError={(m) => pushError(m)}
        />
      )}
    </div>
  )
}

function CatalogueDialog({ product, onClose, onSaved, onError }: {
  product: CatalogueProduct | null
  onClose: () => void
  onSaved: () => void
  onError: (m: string) => void
}) {
  const [sku, setSku] = useState(product?.sku ?? '')
  const [name, setName] = useState(product?.name ?? '')
  const [description, setDescription] = useState(product?.description ?? '')
  const [components, setComponents] = useState(
    product?.default_components.map((c) => ({ ...c })) ?? [{ name: '', yolo_class_hints: [] as string[], ocr_text_hint: '' }],
  )
  const [features, setFeatures] = useState(product?.identifying_features.join(', ') ?? '')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const payload = {
        sku: sku.trim().toUpperCase(),
        name: name.trim(),
        description: description.trim(),
        default_components: components
          .filter((c) => c.name.trim())
          .map((c) => ({ name: c.name.trim(), yolo_class_hints: c.yolo_class_hints, ocr_text_hint: c.ocr_text_hint })),
        identifying_features: features.split(',').map((f) => f.trim()).filter(Boolean),
      }
      if (product) {
        await catalogueService.updateCatalogueProduct(product.id, payload)
      } else {
        await catalogueService.createCatalogueProduct(payload)
      }
      onSaved()
    } catch (err) {
      onError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open title={product ? `Edit ${product.sku}` : 'New catalogue product'} onClose={onClose} wide>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="cat-sku">SKU</Label>
            <Input id="cat-sku" required value={sku} onChange={(e) => setSku(e.target.value)} placeholder="HP-X100" />
          </div>
          <div>
            <Label htmlFor="cat-name">Product name</Label>
            <Input id="cat-name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Wireless Headphones X100" />
          </div>
        </div>
        <div>
          <Label htmlFor="cat-desc">Description</Label>
          <Textarea id="cat-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-slate-700">Default expected components</legend>
          <div className="flex flex-col gap-2">
            {components.map((c, i) => (
              <div key={i} className="flex flex-col gap-2 sm:flex-row">
                <Input
                  aria-label={`Component ${i + 1} name`}
                  placeholder="Component name"
                  value={c.name}
                  onChange={(e) => setComponents(components.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                />
                <Input
                  aria-label={`Component ${i + 1} YOLO hints`}
                  placeholder="YOLO class hints, comma separated"
                  value={c.yolo_class_hints.join(', ')}
                  onChange={(e) =>
                    setComponents(components.map((x, j) =>
                      j === i ? { ...x, yolo_class_hints: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) } : x,
                    ))
                  }
                />
                <Button type="button" variant="ghost" aria-label={`Remove component ${i + 1}`}
                  onClick={() => setComponents(components.filter((_, j) => j !== i))} disabled={components.length === 1}>
                  <Trash2 className="h-4 w-4" aria-hidden />
                </Button>
              </div>
            ))}
          </div>
          <Button type="button" variant="secondary" className="mt-2"
            onClick={() => setComponents([...components, { name: '', yolo_class_hints: [], ocr_text_hint: '' }])}>
            Add component
          </Button>
        </fieldset>
        <div>
          <Label htmlFor="cat-features" hint="comma separated">Identifying features</Label>
          <Input id="cat-features" value={features} onChange={(e) => setFeatures(e.target.value)}
            placeholder="foldable ear cups, brand logo on headband" />
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={busy}>Save product</Button>
        </div>
      </form>
    </Dialog>
  )
}
