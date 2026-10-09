import { AppLayout } from '../components/AppLayout'
import type { NavItem } from '../components/AppLayout'
import { ClipboardList, Database, History, LayoutDashboard, QrCode, Users } from 'lucide-react'
import type { ReactNode } from 'react'

const items: NavItem[] = [
  { to: '/admin', label: 'Dashboard', icon: <LayoutDashboard className="h-4 w-4" aria-hidden /> },
  { to: '/admin/returns', label: 'Returns', icon: <ClipboardList className="h-4 w-4" aria-hidden /> },
  { to: '/admin/catalogue', label: 'Catalogue', icon: <Database className="h-4 w-4" aria-hidden /> },
  { to: '/admin/qr', label: 'QR authorizations', icon: <QrCode className="h-4 w-4" aria-hidden /> },
  { to: '/admin/review', label: 'Review queue', icon: <Users className="h-4 w-4" aria-hidden /> },
  { to: '/admin/users', label: 'Users', icon: <Users className="h-4 w-4" aria-hidden /> },
  { to: '/admin/audit', label: 'Audit history', icon: <History className="h-4 w-4" aria-hidden /> },
]

export function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AppLayout items={items} title="Admin console">
      {children}
    </AppLayout>
  )
}
