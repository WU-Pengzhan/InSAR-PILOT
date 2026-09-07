// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api, connectEvents } from './api'
import {setWindowOwner} from './window-session'

beforeEach(() => {sessionStorage.clear();setWindowOwner('')})
afterEach(() => vi.unstubAllGlobals())

it('omits the authorization header when using an existing cookie in a new tab', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response('{}'))
  vi.stubGlobal('fetch', fetcher)
  await api('/health')
  const options = fetcher.mock.calls[0][1]
  expect(options.headers).not.toHaveProperty('Authorization')
  expect(options.credentials).toBe('same-origin')
})

it('recovers from an expired tab token using the existing browser cookie', async () => {
  sessionStorage.setItem('pilot-token', 'expired-fixture')
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{}', { status: 401 })).mockResolvedValueOnce(new Response('{}'))
  vi.stubGlobal('fetch', fetcher)
  await api('/health')
  expect(fetcher.mock.calls[0][1].headers.Authorization).toBe('Bearer expired-fixture')
  expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty('Authorization')
  expect(sessionStorage.getItem('pilot-token')).toBeNull()
})

it('exposes an authentication failure without retrying an unauthenticated request forever', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response('{"detail":"Local session required."}', { status: 401 }))
  vi.stubGlobal('fetch', fetcher)
  await expect(api('/health')).rejects.toMatchObject({ status: 401 })
  expect(fetcher).toHaveBeenCalledTimes(2)
})

it('never retries a failed operation after an ambiguous server error', async () => {
  sessionStorage.setItem('pilot-token', 'fixture')
  const fetcher = vi.fn().mockResolvedValue(new Response('{}', { status: 500 }))
  vi.stubGlobal('fetch', fetcher)
  await expect(api('/projects', {})).rejects.toMatchObject({ status: 500 })
  expect(fetcher).toHaveBeenCalledTimes(1)
})

it('connects a cookie-authenticated WebSocket without an invalid empty protocol', () => {
  const calls: string[][] = []
  vi.stubGlobal('WebSocket', class {
    constructor(_url: string, protocols: string[]) { calls.push(protocols) }
    close() {}
  })
  const stop = connectEvents('project', 0, () => {})
  expect(calls).toEqual([['pilot']])
  stop()
})


it('establishes a local session and retries an authorization-rejected operation once', async () => {
  const fetcher=vi.fn()
    .mockResolvedValueOnce(new Response('{}',{status:401}))
    .mockResolvedValueOnce(new Response('{"connected":true}'))
    .mockResolvedValueOnce(new Response('{"project_id":"created"}'))
  vi.stubGlobal('fetch',fetcher)
  expect(await api('/projects',{name:'Example'})).toEqual({project_id:'created'})
  expect(fetcher.mock.calls[1][0]).toBe('/api/v1/session')
  expect(fetcher.mock.calls[1][1].headers['X-Pilot-Workbench']).toBe('1')
  expect(fetcher.mock.calls[2][1].body).toBe(fetcher.mock.calls[0][1].body)
  expect(sessionStorage.getItem('pilot-token')).toBeNull()
})

it('shares the initial local connection between simultaneous requests', async () => {
  let finish!:(r:Response)=>void
  const pending=new Promise<Response>(resolve=>{finish=resolve})
  let sessionCalls=0,requests=0
  const fetcher=vi.fn((url:string)=>{
    if(url==='/api/v1/session'){sessionCalls++;return pending}
    requests++
    return Promise.resolve(new Response('{}',{status:requests<=2?401:200}))
  })
  vi.stubGlobal('fetch',fetcher)
  const both=Promise.all([api('/projects'),api('/compute')])
  await vi.waitFor(()=>expect(sessionCalls).toBe(1))
  finish(new Response('{"connected":true}'))
  await both
  expect(sessionCalls).toBe(1)
})


it('keeps the original window claim when a delayed authentication retry completes', async () => {
  setWindowOwner('old-window')
  let finish!:(response:Response)=>void
  const pending=new Promise<Response>(resolve=>{finish=resolve})
  const fetcher=vi.fn().mockReturnValueOnce(pending)
    .mockResolvedValueOnce(new Response('{"connected":true}'))
    .mockResolvedValueOnce(new Response('{}',{status:423}))
  const lost=vi.fn()
  window.addEventListener('pilot-window-lost',lost)
  vi.stubGlobal('fetch',fetcher)
  try {
    const request=api('/projects',{name:'Old request'})
    setWindowOwner('new-window')
    finish(new Response('{}',{status:401}))
    await expect(request).rejects.toMatchObject({status:423})
    expect(fetcher.mock.calls[2][1].headers['X-Pilot-Window']).toBe('old-window')
    expect(lost).not.toHaveBeenCalled()
  } finally {window.removeEventListener('pilot-window-lost',lost)}
})

it('drops the current window on a definite ownership rejection without retrying the operation', async () => {
  setWindowOwner('current-window')
  const lost=vi.fn()
  window.addEventListener('pilot-window-lost',lost)
  const fetcher=vi.fn().mockResolvedValue(new Response('{}',{status:423}))
  vi.stubGlobal('fetch',fetcher)
  try {
    await expect(api('/projects',{name:'Blocked'})).rejects.toMatchObject({status:423})
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(lost).toHaveBeenCalledTimes(1)
  } finally {window.removeEventListener('pilot-window-lost',lost)}
})
