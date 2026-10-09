import { api } from './apiClient'
import type {
  ExpectedComponentInput,
  QRAuth,
  QRGenerateResponse,
  ReturnDetail,
  ReturnRecord,
} from '../types/api'

export function listReturns(): Promise<ReturnRecord[]> {
  return api.get<ReturnRecord[]>('/api/returns')
}

export function getReturn(id: string): Promise<ReturnDetail> {
  return api.get<ReturnDetail>(`/api/returns/${id}`)
}

export function listAssignedReturns(): Promise<ReturnRecord[]> {
  return api.get<ReturnRecord[]>('/api/returns/me/assigned')
}

export interface ReturnCreatePayload {
  order_reference: string
  expected_sku: string
  product_description: string
  expected_components: ExpectedComponentInput[]
  assigned_agent_id: string | null
  catalogue_product_id?: string | null
}

export function createReturn(payload: ReturnCreatePayload): Promise<ReturnRecord> {
  return api.post<ReturnRecord>('/api/returns', payload)
}

export function updateReturn(
  id: string,
  payload: Partial<Pick<ReturnCreatePayload, 'product_description' | 'assigned_agent_id' | 'expected_components'>>,
): Promise<ReturnRecord> {
  return api.put<ReturnRecord>(`/api/returns/${id}`, payload)
}

export function cancelReturn(id: string): Promise<ReturnRecord> {
  return api.post<ReturnRecord>(`/api/returns/${id}/cancel`)
}

export function generateQR(returnId: string): Promise<QRGenerateResponse> {
  return api.post<QRGenerateResponse>(`/api/returns/${returnId}/qr`)
}

export function listQR(returnId: string): Promise<QRAuth[]> {
  return api.get<QRAuth[]>(`/api/returns/${returnId}/qr`)
}

export function revokeQR(qrId: string): Promise<QRAuth> {
  return api.post<QRAuth>(`/api/qr/${qrId}/revoke`)
}
