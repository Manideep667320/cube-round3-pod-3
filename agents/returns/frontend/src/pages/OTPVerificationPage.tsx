import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, ShieldCheck } from 'lucide-react'
import { useFlow } from '../app/FlowContext'
import * as flowService from '../services/flow'
import { Alert, Badge, Button, Card, Input, KeyValue, Label } from '../components/ui'
import { errorMessage } from '../hooks/useAsync'
import type { OTPRequestOut } from '../types/api'

/**
 * OTP stage: request a code (delivered by SMS to the agent's verified phone),
 * enter it, and receive the inspection token that authorizes the photo upload.
 * The OTP value never touches this page's storage - only the typed code.
 */
export function OTPVerificationPage() {
  const { scan, setInspection } = useFlow()
  const navigate = useNavigate()
  const [otpInfo, setOtpInfo] = useState<OTPRequestOut | null>(null)
  const [code, setCode] = useState('')
  const [requesting, setRequesting] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = window.setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => window.clearTimeout(t)
  }, [cooldown])

  if (!scan) {
    return (
      <Card title="Scan required">
        <p className="text-sm text-slate-600">Scan the return's QR code first.</p>
        <Button className="mt-3" onClick={() => navigate('/agent/scan')}>
          Go to scanner
        </Button>
      </Card>
    )
  }

  const requestOtp = async () => {
    setRequesting(true)
    setError(null)
    try {
      const info = await flowService.requestOTP(scan.scanToken)
      setOtpInfo(info)
      const secs = Math.max(0, Math.ceil((new Date(info.resend_available_at).getTime() - Date.now()) / 1000))
      setCooldown(secs)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setRequesting(false)
    }
  }

  const verify = async (e: React.FormEvent) => {
    e.preventDefault()
    setVerifying(true)
    setError(null)
    try {
      const result = await flowService.verifyOTP(scan.scanToken, code)
      setInspection({
        inspectionToken: result.inspection_token,
        returnId: result.return_id,
        returnCode: result.return_code,
      })
      navigate('/agent/inspect')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setVerifying(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4">
      <Card title={`Verify possession — return ${scan.returnCode}`} subtitle={scan.productDescription || undefined}>
        <KeyValue
          items={[
            { label: 'Return', value: <span className="font-mono">{scan.returnCode}</span> },
            { label: 'Delivery to', value: otpInfo ? <span className="font-mono">{otpInfo.masked_phone}</span> : 'request a code first' },
          ]}
        />
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={() => void requestOtp()} loading={requesting} disabled={cooldown > 0}>
            <MessageSquare className="h-4 w-4" aria-hidden />
            {otpInfo ? 'Resend code' : 'Send verification code'}
          </Button>
          {cooldown > 0 && (
            <span className="text-sm text-slate-500" role="status">
              Resend available in <span className="font-medium tabular-nums">{cooldown}s</span>
            </span>
          )}
          {otpInfo && <Badge tone="slate">expires {new Date(otpInfo.expires_at).toLocaleTimeString()}</Badge>}
        </div>
        {error && (
          <div className="mt-3">
            <Alert>{error}</Alert>
          </div>
        )}
      </Card>

      <Card title="Enter the 6-digit code">
        <form onSubmit={(e) => void verify(e)} className="flex flex-col gap-4">
          <div>
            <Label htmlFor="otp-code" hint={otpInfo ? `${otpInfo.max_attempts} attempts allowed` : undefined}>Verification code</Label>
            <Input
              id="otp-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="\d{6}"
              maxLength={6}
              minLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000"
              className="text-center font-mono text-2xl tracking-[0.5em]"
            />
          </div>
          <Button type="submit" loading={verifying} disabled={code.length !== 6 || !otpInfo}>
            <ShieldCheck className="h-4 w-4" aria-hidden />
            Verify & continue to photo
          </Button>
        </form>
      </Card>
    </div>
  )
}
