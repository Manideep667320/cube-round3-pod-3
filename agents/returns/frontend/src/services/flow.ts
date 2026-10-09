import { api } from './apiClient'
import type { InspectionDetail, OTPRequestOut, OTPVerifyResponse, QRScanResponse } from '../types/api'

export function scanQR(token: string): Promise<QRScanResponse> {
  return api.post<QRScanResponse>('/api/qr/scan', { token })
}

export function requestOTP(scanToken: string): Promise<OTPRequestOut> {
  return api.post<OTPRequestOut>('/api/otp/request', {}, { headers: { Authorization: `Bearer ${scanToken}` }, auth: false })
}

export function verifyOTP(scanToken: string, code: string): Promise<OTPVerifyResponse> {
  return api.post<OTPVerifyResponse>('/api/otp/verify', { scan_token: scanToken, code })
}

export function uploadInspectionImage(
  inspectionToken: string,
  file: File,
  viewType: 'STANDARD' | 'CONTENTS_LAYOUT' = 'STANDARD',
): Promise<InspectionDetail> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('view_type', viewType)
  return api.upload<InspectionDetail>('/api/inspections', formData, inspectionToken)
}

export function getInspection(id: string): Promise<InspectionDetail> {
  return api.get<InspectionDetail>(`/api/inspections/${id}`)
}

/** Authenticated image URL: the client fetches bytes with the bearer token. */
export function fetchImageBlob(url: string, bearerToken: string): Promise<Blob> {
  return fetch(url, { headers: { Authorization: `Bearer ${bearerToken}` } }).then((r) => {
    if (!r.ok) throw new Error(`Failed to load image (${r.status})`)
    return r.blob()
  })
}
