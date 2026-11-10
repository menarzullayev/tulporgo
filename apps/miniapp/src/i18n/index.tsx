// UI texts come from tulporgo_core (npm run i18n writes ./*.json); only the language self-names live here
// because they must never be translated or converted.
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import en from './en.json'
import ru from './ru.json'
import uz_cyrl from './uz_cyrl.json'
import uz_latn from './uz_latn.json'
import uz_new from './uz_new.json'
import type { LangCode } from '../types'

export const DICTS: Record<LangCode, Record<string, string>> = { uz_new, uz_latn, uz_cyrl, ru, en }

export const LANGS: { code: LangCode; name: string }[] = [
  { code: 'uz_new', name: 'Özbekça' },
  { code: 'uz_latn', name: "O'zbekcha" },
  { code: 'uz_cyrl', name: 'Ўзбекча' },
  { code: 'ru', name: 'Русский' },
  { code: 'en', name: 'English' },
]

export const DEFAULT_LANG: LangCode = 'uz_new' // decision 29: the new alphabet is the default Uzbek

/** A stored choice or a Telegram language_code -> one of the five languages. */
export function resolveLang(code: string | null | undefined): LangCode {
  if (code && Object.hasOwn(DICTS, code)) return code as LangCode
  const short = (code ?? '').slice(0, 2).toLowerCase()
  if (short === 'ru') return 'ru'
  if (short === 'en') return 'en'
  return DEFAULT_LANG
}

export type Params = Record<string, string | number>

export function translate(lang: LangCode, key: string, params?: Params): string {
  const text = Object.hasOwn(DICTS[lang], key) ? DICTS[lang][key] : Object.hasOwn(DICTS[DEFAULT_LANG], key) ? DICTS[DEFAULT_LANG][key] : undefined
  if (text === undefined) return key // visible in the UI and caught by tests, never a crash
  return params ? text.replace(/\{(\w+)\}/g, (m, name: string) => (Object.hasOwn(params, name) ? String(params[name]) : m)) : text
}

/** Values the API's error texts use as {placeholders} (kept out of the dictionaries on purpose). */
export const ERROR_PARAMS: Params = { example: '30 A 123 BC' }

export function errorText(lang: LangCode, code: string): string {
  const key = `err.${code}`
  const text = translate(lang, key, ERROR_PARAMS)
  return text === key ? translate(lang, 'err.generic') : text
}

interface Ctx {
  lang: LangCode
  setLang(l: LangCode): void
  t(key: string, params?: Params): string
  err(code: string): string
}

const I18nContext = createContext<Ctx | null>(null)

export function I18nProvider({ initial, children }: { initial: string | null | undefined; children: ReactNode }) {
  const [lang, setLang] = useState<LangCode>(() => resolveLang(initial))
  const value = useMemo<Ctx>(
    () => ({ lang, setLang, t: (k, p) => translate(lang, k, p), err: (c) => errorText(lang, c) }),
    [lang],
  )
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): Ctx {
  const c = useContext(I18nContext)
  if (!c) throw new Error('useI18n outside I18nProvider')
  return c
}
