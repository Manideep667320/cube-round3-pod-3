import { Download } from 'lucide-react'
import { Badge } from './ui'

/**
 * Renders the QR PNG produced by the backend. The image encodes only the
 * opaque authorization token - never OTPs, phone numbers or credentials.
 */
export function QRDisplay({ qrPngBase64, token, returnCode }: { qrPngBase64: string; token: string; returnCode: string }) {
  const dataUrl = `data:image/png;base64,${qrPngBase64}`
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-slate-200 p-5">
      <img src={dataUrl} alt={`QR authorization for return ${returnCode}`} className="h-56 w-56 rounded-lg border border-slate-100" />
      <div className="text-center">
        <p className="text-sm font-medium text-slate-800">Return {returnCode}</p>
        <p className="mt-0.5 text-xs text-slate-500">
          Token prefix <span className="font-mono">{token.slice(0, 8)}…</span>
        </p>
      </div>
      <a
        href={dataUrl}
        download={`returndata-qr-${returnCode}.png`}
        className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        <Download className="h-4 w-4" aria-hidden />
        Download QR image
      </a>
      <Badge tone="amber">Token shown once — store it securely if you need to re-print</Badge>
    </div>
  )
}
