import type { LangCode } from './types'

const LOCALES: Record<LangCode, string> = {
  uz_new: 'uz-Latn-UZ',
  uz_latn: 'uz-Latn-UZ',
  uz_cyrl: 'uz-Cyrl-UZ',
  ru: 'ru-RU',
  en: 'en-GB',
}
const TZ = 'Asia/Tashkent' // UTC+5 all year, no daylight saving time

/** 50000 -> "50 000" (narrow no-break space groups, the way prices are written in Uzbekistan). */
export function formatPrice(n: number): string {
  return Math.round(n)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

export function formatDateTime(iso: string, lang: LangCode): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  try {
    return new Intl.DateTimeFormat(LOCALES[lang], { timeZone: TZ, day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(d)
  } catch {
    return iso.replace('T', ' ').slice(0, 16)
  }
}

export function formatDate(iso: string, lang: LangCode): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00+05:00` : iso)
  if (Number.isNaN(d.getTime())) return iso
  try {
    return new Intl.DateTimeFormat(LOCALES[lang], { timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric' }).format(d)
  } catch {
    return iso.slice(0, 10)
  }
}

/** Current Tashkent wall-clock time as a <input type="datetime-local"> value. */
export function tashkentNowInput(now: number = Date.now()): string {
  return new Date(now + 5 * 3600 * 1000).toISOString().slice(0, 16)
}

/** The API reads a time without an offset as Asia/Tashkent, which is what a datetime-local input holds. */
export function departAtForApi(input: string): string | null {
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(input) ? input : null
}

export function stars(rating: number | null): string {
  return rating === null ? '' : rating.toFixed(1)
}

/** Digits of a phone number for a tel: link; null when it does not look like a number. */
export function telHref(phone: string | null | undefined): string | null {
  const d = (phone ?? '').replace(/[^\d+]/g, '')
  return /^\+?\d{9,15}$/.test(d) ? `tel:${d}` : null
}

export function tgHref(username: string | null | undefined): string | null {
  return username && /^[A-Za-z0-9_]{4,32}$/.test(username) ? `https://t.me/${username}` : null
}
