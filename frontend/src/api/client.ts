import axios from 'axios'

const apiRoot = import.meta.env.PROD ? import.meta.env.VITE_API_URL || '/api' : '/api'

export const api = axios.create({
  baseURL: `${apiRoot.replace(/\/$/, '')}/v1`,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

export function requestErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return 'Request failed. Check your connection and try again.'

  const detail: unknown = error.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (!error.response)
    return 'The service could not be reached. Check your connection and try again.'
  if (error.response.status === 401)
    return 'Your session could not be verified. Sign in and try again.'
  if (error.response.status === 403) return 'You do not have access to this action.'
  return 'Request failed. Check your values and access, then try again.'
}
