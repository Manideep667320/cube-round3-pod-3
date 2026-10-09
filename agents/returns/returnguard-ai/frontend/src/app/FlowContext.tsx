import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

/**
 * In-memory carrier for the multi-step agent flow:
 * QR scan token -> OTP verification -> inspection token.
 *
 * Deliberately kept in memory only (module state): refresh tokens are never
 * persisted to web storage, so scan/inspection authorizations cannot leak
 * through localStorage.
 */
interface ScanState {
  scanToken: string
  returnId: string
  returnCode: string
  productDescription: string
}

interface InspectionState {
  inspectionToken: string
  returnId: string
  returnCode: string
}

interface FlowState {
  scan: ScanState | null
  inspection: InspectionState | null
  setScan: (s: ScanState | null) => void
  setInspection: (s: InspectionState | null) => void
  clear: () => void
}

const FlowContext = createContext<FlowState | null>(null)

export function FlowProvider({ children }: { children: ReactNode }) {
  const [scan, setScanState] = useState<ScanState | null>(null)
  const [inspection, setInspectionState] = useState<InspectionState | null>(null)

  const setScan = useCallback((s: ScanState | null) => setScanState(s), [])
  const setInspection = useCallback((s: InspectionState | null) => setInspectionState(s), [])
  const clear = useCallback(() => {
    setScanState(null)
    setInspectionState(null)
  }, [])

  const value = useMemo(() => ({ scan, inspection, setScan, setInspection, clear }), [scan, inspection, setScan, setInspection, clear])
  return <FlowContext.Provider value={value}>{children}</FlowContext.Provider>
}

export function useFlow(): FlowState {
  const ctx = useContext(FlowContext)
  if (!ctx) throw new Error('useFlow must be used within FlowProvider')
  return ctx
}
