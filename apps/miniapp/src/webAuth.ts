// "Login with Telegram" for the site opened OUTSIDE Telegram. The API redirects back to the app with a short web
// session token in the URL fragment (`#tgweb=<token>[&route=/path]` or `#login_error=<code>`); it is kept in
// sessionStorage only (gone when the tab closes) and sent as `Authorization: tgweb <token>`. Inside Telegram none
// of this is used: initData auth is unchanged.
const KEY = 'tulporgo.webToken'
const ERROR_KEY = 'tulporgo.loginError'

function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null // storage blocked (private mode, embedded views): the login simply does not persist
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) sessionStorage.removeItem(key)
    else sessionStorage.setItem(key, value)
  } catch {
    /* see read() */
  }
}

export const getWebToken = (): string | null => read(KEY)
export const setWebToken = (token: string): void => write(KEY, token)
export const clearWebToken = (): void => write(KEY, null)
export const hasWebToken = (): boolean => Boolean(getWebToken())

/** The last failed login (an API error code such as `denied`), shown once on the sign-in screen. */
export const takeLoginError = (): string | null => {
  const e = read(ERROR_KEY)
  if (e) write(ERROR_KEY, null)
  return e
}

/** Where the "Telegram orqali kirish" button goes: the API starts the flow and brings the user back here. */
export function loginStartUrl(base = '/api', here: Pick<Location, 'pathname' | 'hash'> = window.location): string {
  const back = `${here.pathname}${here.hash.startsWith('#/') ? here.hash : ''}`
  return `${base.replace(/\/$/, '')}/auth/telegram/start?return_to=${encodeURIComponent(back)}`
}

/**
 * Call once at startup. When the URL fragment carries a login result, store it and clean the address bar
 * (the token must not linger in the URL or the history); `route` restores the hash route the user came from.
 * Returns true when a token was taken.
 */
export function captureLoginFromHash(loc: Location = window.location): boolean {
  const raw = loc.hash.replace(/^#/, '')
  if (!raw.includes('tgweb=') && !raw.includes('login_error=')) return false
  const p = new URLSearchParams(raw)
  const token = p.get('tgweb')
  const error = p.get('login_error')
  if (token) {
    setWebToken(token)
    write(ERROR_KEY, null)
  } else if (error) write(ERROR_KEY, error)
  else return false
  const route = p.get('route')
  const next = route?.startsWith('/') ? `#${route}` : ''
  try {
    history.replaceState(null, '', `${loc.pathname}${loc.search}${next}`)
  } catch {
    loc.hash = next
  }
  return Boolean(token)
}

export interface LoginConfig {
  enabled: boolean
  client_id: string | null
}
