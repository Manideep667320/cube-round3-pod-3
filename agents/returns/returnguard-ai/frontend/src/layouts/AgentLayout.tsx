import { AppLayout } from '../components/AppLayout'
import type { NavItem } from '../components/AppLayout'
import { Home, ScanLine } from 'lucide-react'
import type { ReactNode } from 'react'

const items: NavItem[] = [
  { to: '/agent', label: 'My returns', icon: <Home className="h-4 w-4" aria-hidden /> },
  { to: '/agent/scan', label: 'Scan QR', icon: <ScanLine className="h-4 w-4" aria-hidden /> },
]

export function AgentLayout({ children }: { children: ReactNode }) {
  return (
    <AppLayout items={items} title="Delivery agent">
      {children}
    </AppLayout>
  )
}
