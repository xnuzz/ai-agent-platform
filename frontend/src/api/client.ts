/**
 * HTTP client for the Django API (docs/API_CONTRACTS.md).
 * - JWT bearer auth with one transparent refresh on 401.
 * - X-Workspace-ID header on every workspace-scoped call.
 * - Error envelope {"error": {code, message, details}} -> ApiError.
 */
const BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '') + '/api/v1'
const STORAGE_KEY = 'platform.auth'

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: unknown = {}) {
    super(message)
  }
}

type Tokens = { access: string; refresh: string }
let tokens: Tokens | null = (() => {
  try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? 'null') } catch { return null }
})()
let workspaceId: string | null = null
let onUnauthorized: () => void = () => {}

export const session = {
  setTokens(t: Tokens | null) {
    tokens = t
    if (t) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(t))
    else sessionStorage.removeItem(STORAGE_KEY)
  },
  hasTokens: () => tokens !== null,
  setWorkspace(id: string | null) { workspaceId = id },
  onUnauthorized(cb: () => void) { onUnauthorized = cb },
}

async function refresh(): Promise<boolean> {
  if (!tokens) return false
  const r = await fetch(`${BASE}/auth/token/refresh/`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: tokens.refresh }),
  })
  if (!r.ok) return false
  const data = await r.json()
  session.setTokens({ access: data.access, refresh: data.refresh ?? tokens.refresh })
  return true
}

type Opts = { auth?: boolean; query?: Record<string, string | number | undefined | null> }

export async function request<T>(method: string, path: string, body?: unknown, opts: Opts = {}, retry = true): Promise<T> {
  const auth = opts.auth ?? true
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && tokens) headers.Authorization = `Bearer ${tokens.access}`
  if (auth && workspaceId) headers['X-Workspace-ID'] = workspaceId
  const qs = opts.query
    ? '?' + new URLSearchParams(Object.entries(opts.query).filter(([, v]) => v != null && v !== '').map(([k, v]) => [k, String(v)])).toString()
    : ''
  const r = await fetch(`${BASE}/${path.replace(/^\//, '')}${qs}`, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (r.status === 401 && auth && retry && (await refresh())) return request<T>(method, path, body, opts, false)
  if (r.status === 401 && auth) { session.setTokens(null); onUnauthorized() }
  if (!r.ok) {
    let err: { code?: string; message?: string; details?: unknown } = {}
    try { err = (await r.json()).error ?? {} } catch { /* non-JSON */ }
    throw new ApiError(r.status, err.code ?? 'error', err.message ?? r.statusText, err.details)
  }
  return (r.status === 204 ? undefined : await r.json()) as T
}

export const api = {
  get: <T>(path: string, query?: Opts['query']) => request<T>('GET', path, undefined, { query }),
  post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: (path: string) => request<void>('DELETE', path),
  public: {
    get: <T>(path: string) => request<T>('GET', path, undefined, { auth: false }),
    post: <T>(path: string) => request<T>('POST', path, {}, { auth: false }),
  },
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const reasons = (e.details as { reasons?: string[] })?.reasons
    return reasons?.length ? `${e.message} (${reasons.join(', ')})` : e.message
  }
  return e instanceof Error ? e.message : String(e)
}
