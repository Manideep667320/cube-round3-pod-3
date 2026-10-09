import { useEffect, useRef, useState } from 'react'
import type { Detection } from '../types/api'
import { getAccessToken } from '../services/apiClient'

/**
 * Renders the original inspection image with real YOLO bounding boxes drawn on
 * a canvas overlay. The image is fetched with the caller's bearer token.
 */
export function DetectionCanvas({
  imageUrl,
  detections,
  width,
  height,
}: {
  imageUrl: string
  detections: Detection[]
  width: number
  height: number
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let revoked: string | null = null
    let cancelled = false
    setLoading(true)
    setError(null)
    const token = getAccessToken()
    fetch(imageUrl, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.blob()
      })
      .then((blob) => {
        if (cancelled) return
        const url = URL.createObjectURL(blob)
        revoked = url
        setObjectUrl(url)
        setLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setError('Could not load the inspection image.')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [imageUrl])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !objectUrl || !width || !height) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const img = new Image()
    img.onload = () => {
      canvas.width = width
      canvas.height = height
      ctx.clearRect(0, 0, width, height)
      ctx.drawImage(img, 0, 0, width, height)
      detections.forEach((det, i) => {
        const [x1, y1, x2, y2] = det.bbox
        const hue = (i * 47) % 360
        ctx.lineWidth = 3
        ctx.strokeStyle = `hsl(${hue} 90% 45%)`
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
        const label = `${det.class_label} ${(det.confidence * 100).toFixed(0)}%`
        ctx.font = 'bold 14px sans-serif'
        const textWidth = ctx.measureText(label).width
        const labelY = y1 > 20 ? y1 - 6 : y1 + 18
        ctx.fillStyle = `hsl(${hue} 90% 45%)`
        ctx.fillRect(x1, labelY - 14, textWidth + 10, 20)
        ctx.fillStyle = '#ffffff'
        ctx.fillText(label, x1 + 5, labelY)
      })
    }
    img.src = objectUrl
  }, [objectUrl, detections, width, height])

  if (loading) {
    return <div className="flex h-64 items-center justify-center rounded-lg bg-slate-100 text-sm text-slate-500">Loading image…</div>
  }
  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
  }
  return (
    <div className="overflow-x-auto">
      <canvas
        ref={canvasRef}
        className="max-w-full rounded-lg border border-slate-200"
        role="img"
        aria-label={`Inspection photo with ${detections.length} detection${detections.length === 1 ? '' : 's'} drawn`}
      />
    </div>
  )
}
