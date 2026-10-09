import { api } from './apiClient'
import type { AuditEvent, HealthReport, Review, ReviewQueueItem, Stats, User } from '../types/api'

export function listUsers(): Promise<User[]> {
  return api.get<User[]>('/api/admin/users')
}

export interface UserCreatePayload {
  username: string
  password: string
  role: 'ADMIN' | 'AGENT' | 'OPERATOR'
  full_name?: string
  phone?: string
  phone_verified?: boolean
}

export function createUser(payload: UserCreatePayload): Promise<User> {
  return api.post<User>('/api/admin/users', payload)
}

export function updateUser(
  userId: string,
  payload: Partial<Omit<UserCreatePayload, 'username' | 'role'>> & { is_active?: boolean },
): Promise<User> {
  return api.put<User>(`/api/admin/users/${userId}`, payload)
}

export function getReviewQueue(): Promise<ReviewQueueItem[]> {
  return api.get<ReviewQueueItem[]>('/api/review-queue')
}

export function resolveReview(inspectionId: string, outcome: 'APPROVE' | 'REJECT', reason: string): Promise<Review> {
  return api.post<Review>(`/api/inspections/${inspectionId}/resolve`, { outcome, reason })
}

export function getAudit(params?: { entity_type?: string; entity_id?: string; action?: string; limit?: number; offset?: number }): Promise<AuditEvent[]> {
  const query = new URLSearchParams()
  if (params?.entity_type) query.set('entity_type', params.entity_type)
  if (params?.entity_id) query.set('entity_id', params.entity_id)
  if (params?.action) query.set('action', params.action)
  query.set('limit', String(params?.limit ?? 100))
  query.set('offset', String(params?.offset ?? 0))
  return api.get<AuditEvent[]>(`/api/audit?${query.toString()}`)
}

export function getStats(): Promise<Stats> {
  return api.get<Stats>('/api/stats')
}

export function getHealth(): Promise<HealthReport> {
  return api.get<HealthReport>('/api/health', { auth: false })
}
