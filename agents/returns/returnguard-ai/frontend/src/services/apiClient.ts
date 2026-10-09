/**
 * Minimal typed fetch client.
 *
 * - The access token is kept in memory (module variable); OTPs, scan tokens and
 *   inspection tokens are NEVER written to localStorage or sessionStorage.
 * - Backend error envelopes are normalized into ApiError.
 * - Every function maps to a real backend route; nothing is fabricated.
 */

export class ApiError extends Error {
  status: number
  code: string
  details?: { field: string; message: string }[]

  constructor(status: number, code: string, message: string, details?: { field: string; message: string }[]) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

let accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

interface RequestOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  auth?: boolean
  formData?: FormData
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers ?? {}) }
  if (options.auth !== false && accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }
  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  const response = await fetch(path, { method: options.method ?? 'GET', headers, body })

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type') ?? ''
  const isJson = contentType.includes('application/json')
  const payload = isJson ? await response.json().catch(() => null) : null

  if (!response.ok) {
    const envelope = (payload as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error
    throw new ApiError(
      response.status,
      envelope?.code ?? 'http_error',
      envelope?.message ?? `Request failed with status ${response.status}`,
      envelope?.details as { field: string; message: string }[] | undefined,
    )
  }
  return payload as T
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  upload: <T>(path: string, formData: FormData, token?: string) =>
    request<T>(path, {
      method: 'POST',
      formData,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      auth: token ? false : undefined,
    }),
}
