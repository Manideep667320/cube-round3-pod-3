import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { Menu, ScanLine, ShieldCheck, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { useAuth } from '../app/AuthContext'
import { Button } from './ui'

export interface NavItem {
  to: string
  label: string
  icon?: ReactNode
}

export function AppLayout({ items, children, title }: { items: NavItem[]; children: ReactNode; title: string }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow">
        Skip to main content
      </a>
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden"
              aria-label={open ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={open}
              onClick={() => setOpen((o) => !o)}
            >
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
                <ShieldCheck className="h-5 w-5" aria-hidden />
              </span>
              <div>
                <p className="text-sm font-semibold text-slate-900">ReturnGuard AI</p>
                <p className="text-xs text-slate-500">{title}</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {user && (
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium text-slate-800">{user.full_name || user.username}</p>
                <p className="text-xs text-slate-500">{user.role === 'ADMIN' ? 'Administrator' : 'Delivery agent'}{user.phone_verified ? ' · verified phone' : ''}</p>
              </div>
            )}
            <Button variant="secondary" onClick={handleLogout}>
              Sign out
            </Button>
          </div>
        </div>
        <nav aria-label="Primary" className={`${open ? 'block' : 'hidden'} border-t border-slate-100 md:block`}>
          <div className="mx-auto flex max-w-7xl flex-col gap-1 p-3 md:flex-row md:items-center md:justify-start md:py-1">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
                    isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                  }`
                }
              >
                {item.icon}
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </header>
      <main id="main-content" className="mx-auto max-w-7xl px-4 py-6">
        {children}
      </main>
      <footer className="border-t border-slate-200 py-4 text-center text-xs text-slate-400">
        ReturnGuard AI · every result shown is produced by real backend inference
      </footer>
    </div>
  )
}

export function scanIcon(): ReactNode {
  return <ScanLine className="h-4 w-4" aria-hidden />
}
