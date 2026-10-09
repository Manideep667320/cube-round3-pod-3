import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '../app/AuthContext'
import { Alert, Button, Input, Label } from '../components/ui'
import { errorMessage } from '../hooks/useAsync'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const user = await login(username.trim(), password)
      navigate(user.role === 'ADMIN' ? '/admin' : '/agent', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <main className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <ShieldCheck className="h-7 w-7" aria-hidden />
          </span>
          <h1 className="mt-3 text-xl font-semibold text-slate-900">ReturnGuard AI</h1>
          <p className="mt-1 text-sm text-slate-500">QR-based return verification and product inspection</p>
        </div>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          {error && <Alert title="Sign-in failed">{error}</Alert>}
          <div>
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <Button type="submit" loading={busy}>
            Sign in
          </Button>
        </form>
        <p className="mt-6 text-center text-xs text-slate-400">
          Accounts are provisioned by administrators. There is no public registration.
        </p>
      </main>
    </div>
  )
}
