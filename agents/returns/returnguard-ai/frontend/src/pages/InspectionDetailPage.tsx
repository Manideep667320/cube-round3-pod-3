import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAsync } from '../hooks/useAsync'
import * as flowService from '../services/flow'
import * as adminService from '../services/admin'
import * as returnsService from '../services/returns'
import { useToast } from '../app/ToastContext'
import { Alert, Button, Card, Label, Spinner, Textarea } from '../components/ui'
import { InspectionDetailView } from '../components/InspectionDetailView'
import { ReturnStatusBadge } from '../components/StatusBadge'
import { errorMessage } from '../hooks/useAsync'

export function InspectionDetailPage() {
  const { inspectionId = '' } = useParams()
  const { data, loading, error, reload } = useAsync(() => flowService.getInspection(inspectionId), [inspectionId])
  const ret = useAsync(
    () => (data?.return_id ? returnsService.getReturn(data.return_id) : Promise.resolve(null)),
    [data?.return_id],
  )
  const { pushSuccess, pushError } = useToast()
  const navigate = useNavigate()
  const [outcome, setOutcome] = useState<'APPROVE' | 'REJECT'>('APPROVE')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  if (loading) return <Spinner label="Loading inspection…" />
  if (error) return <Alert title="Could not load inspection">{error}</Alert>
  if (!data) return null

  const awaitingReview = ret.data?.status === 'NEEDS_REVIEW'

  const resolve = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await adminService.resolveReview(data.id, outcome, reason.trim())
      pushSuccess(`Review recorded: ${outcome === 'APPROVE' ? 'approved' : 'rejected'}.`)
      reload()
      ret.reload()
    } catch (err) {
      pushError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to={ret.data ? `/admin/returns/${ret.data.id}` : '/admin/returns'} className="text-sm font-medium text-brand-600 hover:underline">
            ← Back to return {data.return_code}
          </Link>
          <h1 className="mt-1 text-xl font-semibold text-slate-900">
            Inspection <span className="font-mono text-base">{data.id.slice(0, 8)}…</span>
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Uploaded {new Date(data.created_at).toLocaleString()} · {data.status}
          </p>
        </div>
        {ret.data && <ReturnStatusBadge status={ret.data.status} />}
      </div>

      <InspectionDetailView inspection={data} />

      {awaitingReview ? (
        <Card title="Resolve review" subtitle="A reason is mandatory; the automated decision is preserved.">
          <form onSubmit={resolve} className="flex flex-col gap-4">
            <fieldset className="flex flex-wrap gap-3">
              <legend className="mb-2 text-sm font-medium text-slate-700">Decision</legend>
              <label className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium ${outcome === 'APPROVE' ? 'border-green-500 bg-green-50 text-green-800' : 'border-slate-300 bg-white text-slate-700'}`}>
                <input type="radio" name="outcome" value="APPROVE" checked={outcome === 'APPROVE'} onChange={() => setOutcome('APPROVE')} className="h-4 w-4" />
                Approve return
              </label>
              <label className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium ${outcome === 'REJECT' ? 'border-red-500 bg-red-50 text-red-800' : 'border-slate-300 bg-white text-slate-700'}`}>
                <input type="radio" name="outcome" value="REJECT" checked={outcome === 'REJECT'} onChange={() => setOutcome('REJECT')} className="h-4 w-4" />
                Reject return
              </label>
            </fieldset>
            <div>
              <Label htmlFor="review-reason" hint="required">Reason for this decision</Label>
              <Textarea
                id="review-reason"
                required
                minLength={5}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Explain what you verified in the photo (e.g. charger visible bottom-right, label glare explains low OCR confidence)."
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => navigate('/admin/review')}>
                Back to queue
              </Button>
              <Button type="submit" loading={busy}>
                Submit review
              </Button>
            </div>
          </form>
        </Card>
      ) : (
        data.reviews.length > 0 && (
          <Alert kind="info" title="This return is closed">
            A reviewer already resolved this inspection. See the review history above.
          </Alert>
        )
      )}
    </div>
  )
}
