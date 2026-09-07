// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api, connectEvents } from './api'

beforeEach(() => sessionStorage.clear())
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
  expect(fetcher).toHaveBeenCalledTimes(1)
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
