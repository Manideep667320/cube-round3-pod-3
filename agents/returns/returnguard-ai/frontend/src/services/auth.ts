import { api, setAccessToken } from './apiClient'
import type { TokenResponse, User } from '../types/api'

export async function login(username: string, password: string): Promise<User> {
  const res = await api.post<TokenResponse>('/api/auth/login', { username, password }, { auth: false })
  setAccessToken(res.access_token)
  return res.user
}

export async function fetchMe(): Promise<User> {
  return api.get<User>('/api/auth/me')
}

export function logout(): void {
  setAccessToken(null)
}
