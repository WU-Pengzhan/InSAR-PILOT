const fragment = new URLSearchParams(location.hash.slice(1))
if (fragment.has('token')) {
  sessionStorage.setItem('pilot-token', fragment.get('token')!)
  history.replaceState(null, '', location.pathname)
}
export const token = () => sessionStorage.getItem('pilot-token') || ''

export async function api<T = any>(path: string, body?: unknown, method?: string, signal?: AbortSignal): Promise<T> {
  const credential = token()
  const options: RequestInit = {
    signal,
    method: method || (body === undefined ? 'GET' : 'POST'),
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(credential ? { Authorization: `Bearer ${credential}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  }
  let response = await fetch(`/api/v1${path}`, options)
  if (response.status === 401 && credential) {
    // A stale tab token must not shadow a newer HttpOnly session cookie.
    // A 401 is rejected by middleware before an operation can execute.
    if (token() === credential) sessionStorage.removeItem('pilot-token')
    response = await fetch(`/api/v1${path}`, { ...options, headers: { 'Content-Type': 'application/json' } })
  }
  if (!response.ok) {
    const result = await response.json().catch(() => ({ detail: response.statusText }))
    throw Object.assign(new Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail)), { status: response.status })
  }
  return response.json()
}

export function connectEvents(projectId: string, after: number, receive: (events: StateEvent[]) => void, sessionLost = () => {}): () => void {
  let stopped = false
  let socket: WebSocket | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  const connect = () => {
    if (stopped) return
    const credential = token()
    socket = new WebSocket(`ws://${location.host}/api/v1/projects/${projectId}/events/ws?after=${after}`, credential ? ['pilot', credential] : ['pilot'])
    socket.onmessage = event => {
      const rows = JSON.parse(event.data) as StateEvent[]
      const fresh = rows.filter(row => row.sequence > after)
      if (fresh.length) { after = fresh.at(-1)!.sequence; receive(fresh) }
    }
    socket.onclose = async event => {
      if (stopped) return
      if (event.code === 1008) { stopped = true; sessionLost(); return }
      // A rejected HTTP upgrade is reported as 1006 by browsers, not 1008.
      try { await api('/health') }
      catch (e) {
        if (!stopped && (e as {status?: number}).status === 401) { stopped = true; sessionLost(); return }
      }
      if (!stopped) timer = setTimeout(connect, 1500)
    }
  }
  connect()
  return () => { stopped = true; clearTimeout(timer); socket?.close() }
}
import type { components } from './api-schema'
import type { StateEvent } from './event-cursor'
export type NewProjectRequest = components['schemas']['NewProject']
export type NewPipelineRequest = components['schemas']['NewPipeline']
export type ProjectSelectionRequest = components['schemas']['ProjectSelection']
