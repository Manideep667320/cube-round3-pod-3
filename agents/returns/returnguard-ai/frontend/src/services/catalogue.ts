import { api } from './apiClient'
import type { CatalogueProduct } from '../types/api'

export interface CataloguePayload {
  sku: string
  name: string
  description?: string
  default_components?: { name: string; yolo_class_hints: string[]; ocr_text_hint?: string }[]
  identifying_features?: string[]
}

export function listCatalogue(): Promise<CatalogueProduct[]> {
  return api.get<CatalogueProduct[]>('/api/catalogue')
}

export function createCatalogueProduct(payload: CataloguePayload): Promise<CatalogueProduct> {
  return api.post<CatalogueProduct>('/api/catalogue', payload)
}

export function updateCatalogueProduct(id: string, payload: CataloguePayload): Promise<CatalogueProduct> {
  return api.put<CatalogueProduct>(`/api/catalogue/${id}`, payload)
}
