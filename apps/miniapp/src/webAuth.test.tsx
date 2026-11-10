import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { api, ApiError } from './api'
import { LogoutButton, WebLogin } from './components/WebLogin'
import { I18nProvider } from './i18n'
import { baseMe, installTelegram } from './test/utils'
import { captureLoginFromHash, getWebToken, hasWebToken, loginStartUrl, setWebToken, takeLoginError } from './webAuth'

const withI18n = (ui: React.ReactElement) => render(<I18nProvider initial="en">{ui}</I18nProvider>)

afterEach(() => {
  vi.unstubAllGlobals()
  history.replaceState(null, '', '/')
})

describe('capturing the login result from the URL fragment', () => {
  it('stores the token, restores the route and removes the token from the address bar', () => {
    window.location.hash = '#tgweb=abc.def&route=%2Fprofile'
    expect(captureLoginFromHash()).toBe(true)
    expect(getWebToken()).toBe('abc.def')
    expect(window.location.hash).toBe('#/profile')
    expect(window.location.href).not.toContain('tgweb')
  })

  it('keeps a normal hash route untouched and stores nothing', () => {
    window.location.hash = '#/trips'
    expect(captureLoginFromHash()).toBe(false)
    expect(hasWebToken()).toBe(false)
    expect(window.location.hash).toBe('#/trips')
  })

  it('remembers a failed login once and stores no token', () => {
    window.location.hash = '#login_error=denied'
    expect(captureLoginFromHash()).toBe(false)
    expect(hasWebToken()).toBe(false)
    expect(takeLoginError()).toBe('denied')
    expect(takeLoginError()).toBeNull()
  })

  it('does not break when sessionStorage is blocked', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    window.location.hash = '#tgweb=abc.def'
    expect(() => captureLoginFromHash()).not.toThrow()
    expect(getWebToken()).toBeNull()
  })

  it('builds the start URL from the current page and keeps the hash route', () => {
    expect(loginStartUrl('/api', { pathname: '/app/', hash: '#/profile' })).toBe('/api/auth/telegram/start?return_to=%2Fapp%2F%23%2Fprofile')
    expect(loginStartUrl('/api/', { pathname: '/app/', hash: '' })).toBe('/api/auth/telegram/start?return_to=%2Fapp%2F')
  })
})

describe('the sign-in button', () => {
  it('shows outside Telegram when the server enabled it', async () => {
    vi.spyOn(api, 'loginConfig').mockResolvedValue({ enabled: true, client_id: '123' })
    withI18n(<WebLogin />)
    const link = await screen.findByRole('link', { name: 'Log in with Telegram' })
    expect(link.getAttribute('href')).toMatch(/^\/api\/auth\/telegram\/start\?return_to=/)
  })

  it('is hidden when the server has it switched off', async () => {
    const cfg = vi.spyOn(api, 'loginConfig').mockResolvedValue({ enabled: false, client_id: null })
    withI18n(<WebLogin />)
    await waitFor(() => expect(cfg).toHaveBeenCalled())
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('is hidden inside Telegram, which does not even ask the server', () => {
    installTelegram()
    const cfg = vi.spyOn(api, 'loginConfig').mockResolvedValue({ enabled: true, client_id: '123' })
    withI18n(<WebLogin />)
    expect(screen.queryByRole('link')).toBeNull()
    expect(cfg).not.toHaveBeenCalled()
  })

  it('treats a missing endpoint (404, network) as disabled', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"error":"login_disabled"}', { status: 404 })))
    await expect(api.loginConfig()).resolves.toEqual({ enabled: false, client_id: null })
  })

  it('says so when the login was cancelled', async () => {
    window.location.hash = '#login_error=denied'
    captureLoginFromHash()
    vi.spyOn(api, 'loginConfig').mockResolvedValue({ enabled: true, client_id: '123' })
    withI18n(<WebLogin />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Login was cancelled.')
  })

  it('is part of the signed-out screen outside Telegram', async () => {
    vi.spyOn(api, 'me').mockRejectedValue(new ApiError('unauthorized', 401))
    vi.spyOn(api, 'loginConfig').mockResolvedValue({ enabled: true, client_id: '123' })
    render(<App />)
    expect(await screen.findByRole('link', { name: 'Log in with Telegram' })).toBeInTheDocument()
  })
})

describe('web session token', () => {
  it('is sent as "tgweb <token>" outside Telegram and cleared when the API answers 401', async () => {
    setWebToken('abc.def')
    const fetch = vi.fn().mockResolvedValue(new Response('{}', { status: 401 }))
    vi.stubGlobal('fetch', fetch)
    await expect(api.me()).rejects.toMatchObject({ code: 'unauthorized' })
    expect((fetch.mock.calls[0][1] as RequestInit).headers).toMatchObject({ Authorization: 'tgweb abc.def' })
    expect(hasWebToken()).toBe(false)
  })

  it('never replaces Telegram initData', async () => {
    installTelegram()
    setWebToken('abc.def')
    const fetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    await api.me()
    expect((fetch.mock.calls[0][1] as RequestInit).headers).toMatchObject({ Authorization: expect.stringMatching(/^tma /) })
  })

  it('is not attached to the public config call', async () => {
    setWebToken('abc.def')
    const fetch = vi.fn().mockResolvedValue(new Response('{"enabled":true,"client_id":"1"}', { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    await api.loginConfig()
    expect((fetch.mock.calls[0][1] as RequestInit).headers).not.toHaveProperty('Authorization')
  })

  it('offers logout only to a signed-in browser session, and logout drops the token', async () => {
    const reload = vi.fn()
    vi.stubGlobal('location', { ...window.location, reload })
    const { unmount } = withI18n(<LogoutButton />)
    expect(screen.queryByRole('button')).toBeNull()
    unmount()
    setWebToken('abc.def')
    withI18n(<LogoutButton />)
    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
    expect(hasWebToken()).toBe(false)
    expect(reload).toHaveBeenCalled()
  })

  it('shows no logout inside Telegram', () => {
    installTelegram()
    setWebToken('abc.def')
    withI18n(<LogoutButton />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('opens the app for a signed-in browser session', async () => {
    setWebToken('abc.def')
    vi.spyOn(api, 'me').mockResolvedValue(baseMe)
    vi.spyOn(api, 'myRequests').mockResolvedValue({ items: [] })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Where to?' })).toBeInTheDocument()
  })
})
