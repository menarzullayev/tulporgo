// Thin wrapper over window.Telegram.WebApp (the official Mini App SDK script is loaded in index.html).
// Every call is safe outside Telegram (plain browser, tests, the public share page): it just does nothing.
import { useEffect, useRef } from 'react'

export interface ThemeParams {
  bg_color?: string
  text_color?: string
  hint_color?: string
  link_color?: string
  button_color?: string
  button_text_color?: string
  secondary_bg_color?: string
}

interface Button {
  setText(text: string): void
  show(): void
  hide(): void
  enable(): void
  disable(): void
  showProgress?(leaveActive?: boolean): void
  hideProgress?(): void
  onClick(cb: () => void): void
  offClick(cb: () => void): void
  setParams?(p: Record<string, unknown>): void
}

export interface WebApp {
  initData: string
  initDataUnsafe?: { user?: { id: number; language_code?: string; first_name?: string } }
  themeParams: ThemeParams
  colorScheme?: 'light' | 'dark'
  ready(): void
  expand(): void
  close?(): void
  MainButton?: Button
  BackButton?: Omit<Button, 'setText'>
  HapticFeedback?: {
    impactOccurred(style: 'light' | 'medium' | 'heavy'): void
    notificationOccurred(type: 'error' | 'success' | 'warning'): void
    selectionChanged(): void
  }
  openTelegramLink?(url: string): void
  openLink?(url: string): void
  openInvoice?(url: string, cb?: (status: InvoiceStatus) => void): void
  onEvent?(event: string, cb: () => void): void
  offEvent?(event: string, cb: () => void): void
  setHeaderColor?(color: string): void
  setBackgroundColor?(color: string): void
  showConfirm?(message: string, cb: (ok: boolean) => void): void
}

declare global {
  interface Window {
    Telegram?: { WebApp?: WebApp }
  }
}

export const webApp = (): WebApp | undefined => window.Telegram?.WebApp

/** The signed initData string the API verifies; VITE_DEV_INIT_DATA lets a developer test in a plain browser. */
export function initData(): string {
  return webApp()?.initData || (import.meta.env.VITE_DEV_INIT_DATA as string | undefined) || ''
}

export const inTelegram = (): boolean => Boolean(webApp()?.initData)
export const telegramLang = (): string | undefined => webApp()?.initDataUnsafe?.user?.language_code

const THEME_VARS: Record<keyof ThemeParams, string> = {
  bg_color: '--tg-bg',
  text_color: '--tg-text',
  hint_color: '--tg-hint',
  link_color: '--tg-link',
  button_color: '--tg-button',
  button_text_color: '--tg-button-text',
  secondary_bg_color: '--tg-surface',
}

/** Telegram theme -> CSS variables (light and dark); the brand yellow stays the accent either way. */
export function applyTheme(app: WebApp | undefined = webApp(), root: HTMLElement = document.documentElement): void {
  if (!app) return
  for (const [k, v] of Object.entries(app.themeParams ?? {})) {
    const name = THEME_VARS[k as keyof ThemeParams]
    if (name && typeof v === 'string') root.style.setProperty(name, v)
  }
  if (app.colorScheme) root.dataset.scheme = app.colorScheme
}

export function startApp(): void {
  const app = webApp()
  if (!app) return
  app.ready()
  app.expand()
  applyTheme(app)
  app.onEvent?.('themeChanged', () => applyTheme(app))
}

export type HapticKind = 'light' | 'select' | 'success' | 'error'
export function haptic(kind: HapticKind): void {
  const h = webApp()?.HapticFeedback
  if (!h) return
  if (kind === 'success' || kind === 'error') h.notificationOccurred(kind)
  else if (kind === 'select') h.selectionChanged()
  else h.impactOccurred('light')
}

/** Telegram's own back button while a sub-screen is open. */
export function useBackButton(visible: boolean, onClick: () => void): void {
  useEffect(() => {
    const b = webApp()?.BackButton
    if (!b) return
    if (!visible) {
      b.hide()
      return
    }
    b.onClick(onClick)
    b.show()
    return () => {
      b.offClick(onClick)
      b.hide()
    }
  }, [visible, onClick])
}

/** Mirrors an action onto Telegram's bottom MainButton. Returns true when the native button is active. */
export function useMainButton(text: string, onClick: () => void, opts: { enabled: boolean; busy: boolean; show: boolean }): boolean {
  const b = webApp()?.MainButton
  const native = Boolean(b && inTelegram())
  const latest = useRef(onClick)
  latest.current = onClick // the registered handler stays stable while the closure it calls is always fresh
  useEffect(() => {
    if (!b || !native || !opts.show) return
    const handler = () => latest.current()
    b.setText(text)
    b.onClick(handler)
    b.show()
    return () => {
      b.offClick(handler)
      b.hide()
    }
  }, [b, native, text, opts.show])
  useEffect(() => {
    if (!b || !native || !opts.show) return
    if (opts.enabled && !opts.busy) b.enable()
    else b.disable()
    if (opts.busy) b.showProgress?.(false)
    else b.hideProgress?.()
  }, [b, native, opts.enabled, opts.busy, opts.show])
  return native && opts.show
}

export function shareUrl(url: string, text: string): string {
  return `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`
}

/** Open Telegram's share sheet for a link; falls back to the Web Share API or a new tab outside Telegram. */
export function shareLink(url: string, text: string): void {
  const app = webApp()
  const link = shareUrl(url, text)
  if (app?.openTelegramLink) app.openTelegramLink(link)
  else if (typeof navigator !== 'undefined' && 'share' in navigator) void navigator.share({ url, text }).catch(() => undefined)
  else window.open(link, '_blank', 'noopener')
}

export function openTelegram(url: string): void {
  const app = webApp()
  if (app?.openTelegramLink) app.openTelegramLink(url)
  else window.open(url, '_blank', 'noopener')
}

export type InvoiceStatus = 'paid' | 'cancelled' | 'failed' | 'pending'

/** Telegram Stars invoice inside the Mini App; outside Telegram the invoice link opens in Telegram instead. */
export function openInvoice(url: string): Promise<InvoiceStatus> {
  const app = webApp()
  if (app?.openInvoice) return new Promise((resolve) => app.openInvoice?.(url, resolve))
  openTelegram(url)
  return Promise.resolve('pending')
}

export function confirmDialog(message: string): Promise<boolean> {
  const app = webApp()
  if (app?.showConfirm) return new Promise((resolve) => app.showConfirm?.(message, resolve))
  return Promise.resolve(window.confirm(message))
}
