import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, request } from './api'
import { installTelegram } from './test/utils'

function mockFetch(status: number, body: unknown, raw = false) {
  const fn = vi.fn().mockResolvedValue(new Response(raw ? (body as string) : JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fn)
  return fn
}
const headersOf = (fn: ReturnType<typeof vi.fn>) => (fn.mock.calls[0][1] as RequestInit).headers as Record<string, string>

afterEach(() => vi.unstubAllGlobals())

describe('request', () => {
  it('sends the Telegram initData as "tma <initData>"', async () => {
    installTelegram()
    const fetch = mockFetch(200, { id: 1 })
    await api.me()
    expect(fetch.mock.calls[0][0]).toBe('/api/me')
    expect(headersOf(fetch).Authorization).toBe('tma query_id=AAE&user=%7B%22id%22%3A1%7D&hash=abc')
  })

  it('sends no Authorization header for the public share page', async () => {
    installTelegram() // even inside Telegram the public endpoint is called anonymously
    const fetch = mockFetch(200, { status: 'confirmed' })
    await api.shared('tok_abcdefgh12')
    expect(fetch.mock.calls[0][0]).toBe('/api/share/tok_abcdefgh12')
    expect(headersOf(fetch).Authorization).toBeUndefined()
  })

  it('sends no Authorization header outside Telegram instead of a broken one', async () => {
    const fetch = mockFetch(200, {})
    await api.plans()
    expect(headersOf(fetch).Authorization).toBeUndefined()
  })

  it('encodes JSON bodies and form data differently', async () => {
    const fetch = mockFetch(201, { id: 5 })
    await api.createRequest({ seats: 2, from_text: 'A', to_text: 'B' })
    expect(headersOf(fetch)['Content-Type']).toBe('application/json')
    expect(JSON.parse((fetch.mock.calls[0][1] as RequestInit).body as string)).toMatchObject({ seats: 2 })

    const upload = mockFetch(200, {})
    const form = new FormData()
    form.append('license', new File(['x'], 'l.jpg'))
    await api.uploadDocuments(form)
    expect((upload.mock.calls[0][1] as RequestInit).body).toBe(form)
    expect(headersOf(upload)['Content-Type']).toBeUndefined() // the browser must set the multipart boundary itself
  })

  it('sends the feed filter calls with the right method, path and body', async () => {
    const body = {
      name: 'A', enabled: true, routes: [{ from: 3, to: null, on_way: false }], time_from: null, time_to: null, include_asap: true,
      include_tomorrow: true, weekdays: [], seats_min: null, seats_max: null, kinds: [], group_chat_ids: [],
    }
    const calls: [string, string, unknown][] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
      calls.push([init.method ?? 'GET', url, init.body ? JSON.parse(init.body as string) : undefined])
      return new Response(JSON.stringify({}))
    }))
    await api.feed()
    await api.feedCreate(body)
    await api.feedUpdate(7, body)
    await api.feedDelete(7)
    await api.feedPause(true)
    expect(calls).toEqual([
      ['GET', '/api/userbot/feed', undefined],
      ['POST', '/api/userbot/feed/filters', body],
      ['PUT', '/api/userbot/feed/filters/7', body],
      ['DELETE', '/api/userbot/feed/filters/7', undefined],
      ['POST', '/api/userbot/feed/pause', { paused: true }],
    ])
  })

  it('url-encodes search text and share tokens', async () => {
    const fetch = mockFetch(200, { items: [] })
    await api.searchPlaces("Qo'shrabot & co")
    expect(fetch.mock.calls[0][0]).toBe("/api/places?q=Qo'shrabot%20%26%20co")
    const f2 = mockFetch(200, {})
    await api.shared('a/b?c')
    expect(f2.mock.calls[0][0]).toBe('/api/share/a%2Fb%3Fc')
  })
})

describe('errors', () => {
  it('maps the API error body to an ApiError with the stable code', async () => {
    mockFetch(409, { error: 'request_not_open', detail: 'request_not_open' })
    await expect(api.cancelRequest(1)).rejects.toMatchObject({ code: 'request_not_open', status: 409 })
  })

  it('treats any 401 as unauthorized', async () => {
    mockFetch(401, { detail: 'invalid Mini App auth: bad hash' })
    await expect(api.me()).rejects.toMatchObject({ code: 'unauthorized', status: 401 })
  })

  it('does not trust a non-string error field', async () => {
    mockFetch(500, { error: { nested: true } })
    await expect(api.me()).rejects.toMatchObject({ code: 'generic' })
  })

  it('survives non-JSON error pages (proxy 502)', async () => {
    mockFetch(502, '<html>Bad gateway</html>', true)
    await expect(api.me()).rejects.toMatchObject({ code: 'generic', status: 502 })
  })

  it('reports a dead connection as "network"', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const err = (await request('/me').catch((e: unknown) => e)) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.code).toBe('network')
  })

  it('lets an aborted request propagate as an abort, not as an error message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError')))
    await expect(request('/me')).rejects.toMatchObject({ name: 'AbortError' })
  })
})
