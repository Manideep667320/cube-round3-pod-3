import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, CheckCircle2, RefreshCcw, Upload } from 'lucide-react'
import { useFlow } from '../app/FlowContext'
import * as flowService from '../services/flow'
import { Alert, Badge, Button, Card, Spinner } from '../components/ui'
import { InspectionDetailView } from '../components/InspectionDetailView'
import { DecisionBadge } from '../components/StatusBadge'
import { errorMessage } from '../hooks/useAsync'
import type { InspectionDetail } from '../types/api'

/**
 * Capture or upload the returned-product photo; the backend runs real image
 * validation, OCR and YOLO inference, then returns the persisted evidence and
 * the deterministic decision. Results are only shown after the backend
 * operation succeeds.
 */
export function ProductInspectionPage() {
  const { inspection, clear } = useFlow()
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [cameraOn, setCameraOn] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState<InspectionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [viewType, setViewType] = useState<'STANDARD' | 'CONTENTS_LAYOUT'>('STANDARD')
  const [photoCount, setPhotoCount] = useState(0)

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!inspection) {
    return (
      <Card title="Verification required">
        <p className="text-sm text-slate-600">Complete the QR scan and OTP verification before uploading a photo.</p>
        <Button className="mt-3" onClick={() => navigate('/agent/scan')}>
          Go to scanner
        </Button>
      </Card>
    )
  }

  const startCamera = async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setCameraOn(true)
    } catch (e) {
      setError(`Could not start the camera: ${errorMessage(e)}. You can upload a file instead.`)
    }
  }

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setCameraOn(false)
  }

  const takePhoto = () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) {
      setError('Camera is not ready yet.')
      return
    }
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d')?.drawImage(video, 0, 0)
    canvas.toBlob((blob) => {
      if (!blob) return
      const file = new File([blob], `capture-${Date.now()}.jpg`, { type: 'image/jpeg' })
      setPendingFile(file)
      setPreviewUrl(URL.createObjectURL(blob))
      stopCamera()
    }, 'image/jpeg', 0.92)
  }

  const pickFile = (file: File | null) => {
    if (!file) return
    setPendingFile(file)
    setPreviewUrl(URL.createObjectURL(file))
  }

  const submit = async () => {
    if (!pendingFile) return
    setProcessing(true)
    setError(null)
    try {
      const detail = await flowService.uploadInspectionImage(inspection.inspectionToken, pendingFile, viewType)
      setResult(detail)
      setPhotoCount((n) => n + 1)
      setPendingFile(null)
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
        setPreviewUrl(null)
      }
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setProcessing(false)
    }
  }

  const addAnotherView = () => {
    setResult(null)
    setViewType('CONTENTS_LAYOUT')
  }

  const startOver = () => {
    clear()
    setResult(null)
    navigate('/agent/scan')
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Card title={`Inspect return ${inspection.returnCode}`} subtitle="Take or upload a clear photo of the returned product and its components.">
        {error && <div className="mb-3"><Alert>{error}</Alert></div>}

        {!result && (
          <>
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-900">
              <video ref={videoRef} className="aspect-video w-full object-cover" muted playsInline aria-label="Camera viewfinder for product photo" />
            </div>
            {previewUrl && (
              <figure className="mt-3">
                <img src={previewUrl} alt="Selected product photo preview" className="max-h-80 rounded-lg border border-slate-200" />
                <figcaption className="mt-1 text-xs text-slate-500">Preview — submit to run OCR and object detection.</figcaption>
              </figure>
            )}
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <div>
                <label htmlFor="view-type" className="mb-1 block text-sm font-medium text-slate-700">
                  Photo view type
                </label>
                <select
                  id="view-type"
                  value={viewType}
                  onChange={(e) => setViewType(e.target.value as 'STANDARD' | 'CONTENTS_LAYOUT')}
                  className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
                >
                  <option value="STANDARD">Standard product photo</option>
                  <option value="CONTENTS_LAYOUT">Contents layout (all returned items shown)</option>
                </select>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {!cameraOn ? (
                <Button onClick={() => void startCamera()}>
                  <Camera className="h-4 w-4" aria-hidden />
                  Start camera
                </Button>
              ) : (
                <Button onClick={takePhoto}>
                  <Camera className="h-4 w-4" aria-hidden />
                  Capture photo
                </Button>
              )}
              <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                <Upload className="h-4 w-4" aria-hidden />
                Upload image
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/bmp"
                  className="sr-only"
                  onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
                />
              </label>
              <Button onClick={() => void submit()} loading={processing} disabled={!pendingFile}>
                <CheckCircle2 className="h-4 w-4" aria-hidden />
                Submit for inspection
              </Button>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              JPEG, PNG, WEBP or BMP. Add a contents-layout photo (all returned items laid out) if you
              want missing accessories to be confirmable. Results appear only after the backend finishes.
            </p>
          </>
        )}

        {processing && (
          <div className="mt-4 flex items-center gap-3 rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900" role="status">
            <Spinner label="Running image validation, OCR and object detection…" />
          </div>
        )}
      </Card>

      {result && (
        <>
          <Card
            title="Inspection result"
            subtitle={
              <span className="flex flex-wrap items-center gap-2">
                <DecisionBadge outcome={result.decision?.outcome ?? null} />
                {result.decision?.outcome === 'APPROVE' && <span className="text-green-700">The return can proceed.</span>}
                {result.decision?.outcome === 'MANUAL_REVIEW' && (
                  <span className="text-amber-700">A human reviewer must confirm this return — you do not need to do anything else.</span>
                )}
                {result.decision?.outcome === 'REJECT' && (
                  <span className="text-red-700">Evidence conflicts with this return; an administrator will review it.</span>
                )}
              </span>
            }
          >
            <Badge tone="slate">Inspection {result.id.slice(0, 8)}… · {new Date(result.created_at).toLocaleString()}</Badge>
          </Card>
          <InspectionDetailView inspection={result} />
          <div className="flex flex-wrap justify-end gap-2">
            {result.decision?.outcome === 'MANUAL_REVIEW' && (
              <Button onClick={addAnotherView}>
                <Camera className="h-4 w-4" aria-hidden />
                Add another view ({photoCount} photo{photoCount === 1 ? '' : 's'} so far)
              </Button>
            )}
            <Button variant="secondary" onClick={startOver}>
              <RefreshCcw className="h-4 w-4" aria-hidden />
              Scan next return
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
