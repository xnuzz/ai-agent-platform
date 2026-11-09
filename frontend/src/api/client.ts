/**
 * HTTP client for the Django API (docs/API_CONTRACTS.md).
 * - JWT bearer auth with one transparent refresh on 401.
 * - X-Workspace-ID header on every workspace-scoped call.
 * - Error envelope {"error": {code, message, details}} -> ApiError.
 */
const BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '') + '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: unknown = {}) {
    super(message)
  }
}

// Access token lives in memory only; the refresh token is an httpOnly cookie the browser sends to
// /api/v1/auth/* (ADR-014). A page reload restores the session via refresh().
let access: string | null = null
let workspaceId: string | null = null
let onUnauthorized: () => void = () => {}
try { sessionStorage.removeItem('platform.auth') } catch { /* legacy storage from v1 */ }

export const session = {
  setAccess(t: string | null) { access = t },
  hasAccess: () => access !== null,
  setWorkspace(id: string | null) { workspaceId = id },
  onUnauthorized(cb: () => void) { onUnauthorized = cb },
}

let refreshing: Promise<boolean> | null = null
/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refresh(): Promise<boolean> {
  refreshing ??= fetch(`${BASE}/auth/token/refresh/`, { method: 'POST', credentials: 'include' })
    .then(async (r) => {
      if (!r.ok) { access = null; return false }
      access = (await r.json()).access
      return true
    })
    .catch(() => false)
    .finally(() => { refreshing = null })
  return refreshing
}

type Opts = { auth?: boolean; query?: Record<string, string | number | undefined | null> }

export async function request<T>(method: string, path: string, body?: unknown, opts: Opts = {}, retry = true): Promise<T> {
  const auth = opts.auth ?? true
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && access) headers.Authorization = `Bearer ${access}`
  if (auth && workspaceId) headers['X-Workspace-ID'] = workspaceId
  const qs = opts.query
    ? '?' + new URLSearchParams(Object.entries(opts.query).filter(([, v]) => v != null && v !== '').map(([k, v]) => [k, String(v)])).toString()
    : ''
  const r = await fetch(`${BASE}/${path.replace(/^\//, '')}${qs}`, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined, credentials: 'include',
  })
  if (r.status === 401 && auth && retry && (await refresh())) return request<T>(method, path, body, opts, false)
  if (r.status === 401 && auth) { access = null; onUnauthorized() }
  if (!r.ok) {
    let err: { code?: string; message?: string; details?: unknown } = {}
    try { err = (await r.json()).error ?? {} } catch { /* non-JSON */ }
    throw new ApiError(r.status, err.code ?? 'error', err.message ?? r.statusText, err.details)
  }
  const text = await r.text() // 202/204 and other empty bodies are valid
  return (text ? JSON.parse(text) : undefined) as T
}

export const api = {
  get: <T>(path: string, query?: Opts['query']) => request<T>('GET', path, undefined, { query }),
  post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: (path: string) => request<void>('DELETE', path),
  public: {
    get: <T>(path: string) => request<T>('GET', path, undefined, { auth: false }),
    post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body, { auth: false }),
  },
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const reasons = (e.details as { reasons?: string[] })?.reasons
    return reasons?.length ? `${e.message} (${reasons.join(', ')})` : e.message
  }
  return e instanceof Error ? e.message : String(e)
}
