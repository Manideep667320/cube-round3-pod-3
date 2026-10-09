import { useState } from 'react'
import { Plus } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import * as adminService from '../services/admin'
import { useToast } from '../app/ToastContext'
import { Alert, Badge, Button, Card, Dialog, Input, Label, Select, Spinner } from '../components/ui'
import { errorMessage } from '../hooks/useAsync'
import type { User } from '../types/api'

export function UsersPage() {
  const { data, loading, error, reload } = useAsync(() => adminService.listUsers())
  const { pushSuccess, pushError } = useToast()
  const [creating, setCreating] = useState(false)

  const toggleActive = async (u: User) => {
    try {
      await adminService.updateUser(u.id, { is_active: !u.is_active })
      pushSuccess(`${u.username} ${u.is_active ? 'deactivated' : 'activated'}.`)
      reload()
    } catch (e) {
      pushError(errorMessage(e))
    }
  }

  const verifyPhone = async (u: User) => {
    try {
      await adminService.updateUser(u.id, { phone_verified: true })
      pushSuccess(`Phone verified for ${u.username}.`)
      reload()
    } catch (e) {
      pushError(errorMessage(e))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Users"
        subtitle="Accounts are provisioned here; there is no public registration path"
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            New user
          </Button>
        }
      >
        {loading ? (
          <Spinner label="Loading users…" />
        ) : error ? (
          <Alert title="Could not load users">{error}</Alert>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                  <th className="py-2 pr-4">Username</th>
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2 pr-4">Phone</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {(data ?? []).map((u) => (
                  <tr key={u.id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="py-2 pr-4 font-medium text-slate-800">{u.username}</td>
                    <td className="py-2 pr-4">{u.full_name || '—'}</td>
                    <td className="py-2 pr-4"><Badge tone={u.role === 'ADMIN' ? 'blue' : 'slate'}>{u.role}</Badge></td>
                    <td className="py-2 pr-4">
                      {u.phone ?? '—'}{' '}
                      {u.phone && !u.phone_verified && (
                        <Button variant="ghost" className="min-h-0 px-2 py-1 text-xs" onClick={() => verifyPhone(u)}>
                          Mark verified
                        </Button>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      <Badge tone={u.is_active ? 'green' : 'red'}>{u.is_active ? 'Active' : 'Inactive'}</Badge>
                    </td>
                    <td className="py-2 text-right">
                      <Button variant="secondary" className="min-h-9 px-3 py-1 text-xs" onClick={() => toggleActive(u)}>
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <CreateUserDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={() => {
          setCreating(false)
          pushSuccess('User created.')
          reload()
        }}
        onError={(m) => pushError(m)}
      />
    </div>
  )
}

function CreateUserDialog({ open, onClose, onCreated, onError }: {
  open: boolean
  onClose: () => void
  onCreated: () => void
  onError: (m: string) => void
}) {
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'AGENT' | 'ADMIN' | 'OPERATOR'>('AGENT')
  const [phone, setPhone] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await adminService.createUser({
        username: username.trim().toLowerCase(),
        password,
        role,
        full_name: fullName.trim(),
        phone: phone.trim() || undefined,
        phone_verified: false,
      })
      setUsername('')
      setFullName('')
      setPassword('')
      setPhone('')
      onCreated()
    } catch (err) {
      onError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} title="Create user" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="new-username">Username</Label>
          <Input id="new-username" required minLength={3} value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="new-fullname">Full name</Label>
          <Input id="new-fullname" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="new-password" hint="min 8 characters">Password</Label>
          <Input id="new-password" type="password" required minLength={8} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="new-role">Role</Label>
          <Select id="new-role" value={role} onChange={(e) => setRole(e.target.value as 'AGENT' | 'ADMIN' | 'OPERATOR')}>
            <option value="AGENT">Delivery agent</option>
            <option value="OPERATOR">Inspection operator (warehouse)</option>
            <option value="ADMIN">Administrator</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="new-phone" hint="required for OTP delivery to agents">Phone (E.164)</Label>
          <Input id="new-phone" placeholder="+15551234567" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <p className="mt-1 text-xs text-slate-500">An admin must mark the phone verified before OTPs can be delivered.</p>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={busy}>Create user</Button>
        </div>
      </form>
    </Dialog>
  )
}
