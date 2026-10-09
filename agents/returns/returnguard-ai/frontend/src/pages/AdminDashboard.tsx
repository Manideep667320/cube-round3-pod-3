import { Link } from 'react-router-dom'
import { AlertTriangle, ClipboardCheck, ClipboardList, ShieldCheck, Users } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import * as adminService from '../services/admin'
import { Alert, Card, EmptyState, Spinner } from '../components/ui'
import { ReturnStatusBadge } from '../components/StatusBadge'

export function AdminDashboard() {
  const { data: stats, loading, error, reload } = useAsync(() => adminService.getStats())
  const health = useAsync(() => adminService.getHealth())

  if (loading) return <Spinner label="Loading dashboard…" />
  if (error) return <Alert title="Could not load statistics">{error}</Alert>

  const needsReview = stats?.returns_by_status['NEEDS_REVIEW'] ?? 0
  const active = (stats?.returns_by_status['AWAITING_SCAN'] ?? 0) + (stats?.returns_by_status['AWAITING_OTP'] ?? 0) + (stats?.returns_by_status['AWAITING_INSPECTION'] ?? 0)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card title="Total returns">
          <p className="text-3xl font-semibold text-slate-900">{stats?.total_returns ?? 0}</p>
          <Link to="/admin/returns" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">
            Manage returns →
          </Link>
        </Card>
        <Card title="In progress">
          <p className="text-3xl font-semibold text-blue-600">{active}</p>
          <p className="mt-2 text-sm text-slate-500">Awaiting scan, OTP or photo</p>
        </Card>
        <Card title="Needs human review">
          <p className={`text-3xl font-semibold ${needsReview > 0 ? 'text-amber-600' : 'text-slate-400'}`}>{needsReview}</p>
          <Link to="/admin/review" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">
            Open review queue →
          </Link>
        </Card>
        <Card title="Inspections">
          <p className="text-3xl font-semibold text-slate-900">{stats?.total_inspections ?? 0}</p>
          <p className="mt-2 text-sm text-slate-500">{stats?.agents ?? 0} delivery agents</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Decisions (all returns)" subtitle="Produced by the deterministic decision engine and human reviewers">
          {stats && stats.total_inspections === 0 ? (
            <EmptyState title="No inspections yet" hint="Decisions appear after agents upload product photos." />
          ) : (
            <ul className="space-y-2 text-sm">
              {Object.entries(stats?.decisions ?? {}).map(([outcome, count]) => (
                <li key={outcome} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
                  <span className="font-medium text-slate-700">{outcome.replace('_', ' ')}</span>
                  <span className="text-slate-900">{count}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Returns by status">
          <ul className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            {Object.entries(stats?.returns_by_status ?? {}).map(([status, count]) => (
              <li key={status} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2">
                <ReturnStatusBadge status={status} />
                <span className="font-medium text-slate-900">{count}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="System health" subtitle="Live dependency availability reported by the backend">
        {health.loading ? (
          <Spinner label="Checking dependencies…" />
        ) : health.error ? (
          <Alert>{health.error}</Alert>
        ) : health.data ? (
          <ul className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <li className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2">
              <ShieldCheck className="h-4 w-4 text-green-600" aria-hidden /> Database: {health.data.database.status}
            </li>
            <li className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2">
              <ClipboardCheck className="h-4 w-4 text-green-600" aria-hidden /> SMS: {health.data.sms_provider}
            </li>
            <li className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2">
              <ClipboardList className="h-4 w-4 text-green-600" aria-hidden /> OCR: {health.data.ocr.available ? health.data.ocr.engine : 'unavailable'}
            </li>
            <li className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2">
              <AlertTriangle className={`h-4 w-4 ${health.data.yolo.weights_present ? 'text-green-600' : 'text-amber-500'}`} aria-hidden />
              YOLO weights: {health.data.yolo.weights_present ? 'present' : 'missing'}
            </li>
          </ul>
        ) : null}
      </Card>

      <Card title="Quick actions">
        <div className="flex flex-wrap gap-3">
          <Link to="/admin/returns" className="inline-flex min-h-11 items-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            <Users className="mr-2 h-4 w-4" aria-hidden />
            Create return
          </Link>
          <Link to="/admin/review" className="inline-flex min-h-11 items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Review queue
          </Link>
        </div>
      </Card>
      <button onClick={reload} className="self-start text-sm font-medium text-brand-600 hover:underline">
        Refresh statistics
      </button>
    </div>
  )
}
