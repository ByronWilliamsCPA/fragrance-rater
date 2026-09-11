import axios from 'axios'

export function apiV1BaseUrl(configuredRoot: string): string {
  const root = configuredRoot.replace(/\/$/, '')
  if (root.endsWith('/api/v1')) return root
  if (root.endsWith('/api')) return `${root}/v1`
  return `${root}/api/v1`
}

const apiRoot = import.meta.env.PROD ? import.meta.env.VITE_API_URL || '/api' : '/api'

export const api = axios.create({
  baseURL: apiV1BaseUrl(apiRoot),
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

export function requestErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return 'Request failed. Check your connection and try again.'

  const detail: unknown = error.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (typeof detail === 'object' && detail !== null && 'message' in detail) {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string' && message.trim()) return message
  }
  if (!error.response)
    return 'The service could not be reached. Check your connection and try again.'
  if (error.response.status === 401)
    return 'Your session could not be verified. Sign in and try again.'
  if (error.response.status === 403) return 'You do not have access to this action.'
  return 'Request failed. Check your values and access, then try again.'
}
