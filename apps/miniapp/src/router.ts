import { useEffect, useState } from 'react'

// Hash routing: the Mini App is static files at /app, so no server rewrites are needed and share links work as
// https://tulporgo.uz/app/#/share/<token>.
export type RouteName =
  | 'home'
  | 'offers'
  | 'trips'
  | 'trip'
  | 'profile'
  | 'driver'
  | 'subscription'
  | 'userbot'
  | 'feed'
  | 'share'
  | 'notfound'

export interface Route {
  name: RouteName
  params: Record<string, string>
}

const TABLE: [RegExp, RouteName, string[]][] = [
  [/^\/?$/, 'home', []],
  [/^\/offers\/(\d+)$/, 'offers', ['id']],
  [/^\/trips$/, 'trips', []],
  [/^\/trip\/(\d+)$/, 'trip', ['id']],
  [/^\/profile$/, 'profile', []],
  [/^\/driver$/, 'driver', []],
  [/^\/subscription$/, 'subscription', []],
  [/^\/userbot\/login$/, 'userbot', []],
  [/^\/feed$/, 'feed', []],
  [/^\/share\/([A-Za-z0-9_-]{8,64})$/, 'share', ['token']],
]

/** Pages the bot opens as `<miniapp_url>?page=<name>` (no hash). */
const BOT_PAGES: Record<string, RouteName> = { userbot: 'userbot', feed: 'feed' }

/** An in-app hash route wins over the bot's `?page=` link. */
export function parseLocation(hash: string, search = ''): Route {
  const path = hash.replace(/^#/, '').split('?')[0]
  const page = new URLSearchParams(search).get('page')
  if (!path && page && Object.hasOwn(BOT_PAGES, page)) return { name: BOT_PAGES[page], params: {} }
  return parseHash(hash)
}

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#/, '').split('?')[0] || '/'
  for (const [rx, name, keys] of TABLE) {
    const m = rx.exec(path)
    if (m) return { name, params: Object.fromEntries(keys.map((k, i) => [k, m[i + 1]])) }
  }
  return { name: 'notfound', params: {} }
}

export const href = (path: string): string => `#${path}`
export const navigate = (path: string): void => {
  window.location.hash = path
}
export const goBack = (): void => {
  if (window.history.length > 1) window.history.back()
  else navigate('/')
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseLocation(window.location.hash, window.location.search))
  useEffect(() => {
    const on = () => setRoute(parseLocation(window.location.hash, window.location.search))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}
