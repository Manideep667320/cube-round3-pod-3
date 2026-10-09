import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BrowserQRCodeReader } from '@zxing/browser'
import type { IScannerControls } from '@zxing/browser'
import { Camera, Keyboard } from 'lucide-react'
import { useFlow } from '../app/FlowContext'
import * as flowService from '../services/flow'
import { Alert, Button, Card, Input, Label } from '../components/ui'
import { errorMessage } from '../hooks/useAsync'

/**
 * Agent scans the hidden QR with the device camera (or pastes the token when
 * no camera is available - useful for local testing). A successful scan is
 * validated server-side (single-use, expiry, agent binding) before continuing.
 */
export function QRScannerPage() {
  const navigate = useNavigate()
  const { setScan } = useFlow()
  const videoRef = useRef<HTMLVideoElement>(null)
  const controlsRef = useRef<IScannerControls | null>(null)
  const [cameraOn, setCameraOn] = useState(false)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [manualToken, setManualToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)

  const handleToken = async (token: string) => {
    if (busy) return
    setBusy(true)
    setScanError(null)
    try {
      const result = await flowService.scanQR(token.trim())
      controlsRef.current?.stop()
      setScan({
        scanToken: result.scan_token,
        returnId: result.return_id,
        returnCode: result.return_code,
        productDescription: result.product_description,
      })
      navigate('/agent/otp')
    } catch (e) {
      setScanError(errorMessage(e))
      setBusy(false)
    }
  }

  const startCamera = async () => {
    setCameraError(null)
    if (!videoRef.current) return
    try {
      const reader = new BrowserQRCodeReader()
      const controls = await reader.decodeFromConstraints(
        { video: { facingMode: 'environment' } },
        videoRef.current,
        (result, err) => {
          if (result) {
            void handleToken(result.getText())
          } else if (err && !String(err).includes('NotAllowed')) {
            // Ignore per-frame decode misses; surface camera permission issues.
            if (String(err).includes('Permission') || String(err).includes('insecure')) {
              setCameraError(String(err))
            }
          }
        },
      )
      controlsRef.current = controls
      setCameraOn(true)
    } catch (e) {
      setCameraError(errorMessage(e))
      setCameraOn(false)
    }
  }

  useEffect(() => {
    return () => {
      controlsRef.current?.stop()
    }
  }, [])

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4">
      <Card title="Scan return QR" subtitle="The QR is single-use and bound to your account.">
        {scanError && <div className="mb-3"><Alert title="Scan rejected">{scanError}</Alert></div>}
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-900">
          <video ref={videoRef} className="aspect-video w-full object-cover" muted playsInline aria-label="Camera viewfinder for QR scanning" />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {!cameraOn ? (
            <Button onClick={() => void startCamera()}>
              <Camera className="h-4 w-4" aria-hidden />
              Start camera
            </Button>
          ) : (
            <Button
              variant="secondary"
              onClick={() => {
                controlsRef.current?.stop()
                setCameraOn(false)
              }}
            >
              Stop camera
            </Button>
          )}
        </div>
        {cameraError && (
          <div className="mt-3">
            <Alert kind="warning" title="Camera unavailable">
              {cameraError}. You can paste the QR token below instead.
            </Alert>
          </div>
        )}
      </Card>

      <Card title="No camera? Paste the token" subtitle="The token is the string encoded inside the QR image.">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            void handleToken(manualToken)
          }}
          className="flex flex-col gap-3"
        >
          <div>
            <Label htmlFor="manual-token">QR token</Label>
            <Input
              id="manual-token"
              value={manualToken}
              onChange={(e) => setManualToken(e.target.value)}
              placeholder="returnguard://scan?token=… or the raw token"
              autoComplete="off"
            />
          </div>
          <Button type="submit" loading={busy} disabled={!manualToken.trim()}>
            <Keyboard className="h-4 w-4" aria-hidden />
            Validate token
          </Button>
        </form>
      </Card>
    </div>
  )
}
