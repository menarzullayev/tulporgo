import { describe, expect, it } from 'vitest'
import { DICTS, errorText, LANGS, resolveLang, translate } from './index'

const CODES = [
  'already_driver', 'already_matched', 'already_rated', 'bad_file_type', 'bad_lang', 'bad_phone', 'bad_plate', 'bad_price',
  'bad_seats', 'bad_stars', 'blocked', 'counter_must_be_lower', 'depart_in_past', 'documents_required', 'driver_not_active',
  'file_too_large', 'network', 'no_counter', 'not_a_driver', 'not_enough_seats', 'not_your_offer', 'not_your_request',
  'not_your_trip', 'offer_closed', 'offer_not_found', 'offer_not_open', 'own_request', 'phone_required', 'place_not_found',
  'plate_taken', 'request_not_found', 'request_not_open', 'route_required', 'same_place', 'self_referral',
  'storage_not_configured', 'subscription_required', 'too_many_open_requests', 'trip_not_active', 'trip_not_cancellable',
  'consent_required', 'no_pending_login', 'login_expired', 'login_cooldown', 'flood_wait', 'too_many_attempts', 'bad_code', 'code_expired', 'bad_password', 'phone_banned', 'password_not_requested', 'telegram_api_missing', 'userbot_key_missing',
  'trip_not_completed', 'trip_not_confirmed', 'trip_not_found', 'unauthorized', 'upload_failed', 'generic',
]

describe('dictionaries', () => {
  it('has the same keys in all five languages', () => {
    const [first, ...rest] = Object.values(DICTS)
    for (const d of rest) expect(Object.keys(d).sort()).toEqual(Object.keys(first).sort())
    expect(Object.keys(DICTS).sort()).toEqual(LANGS.map((l) => l.code).sort())
  })

  it('has no empty texts and keeps {placeholders} identical across languages', () => {
    const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join()
    for (const key of Object.keys(DICTS.en)) {
      for (const d of Object.values(DICTS)) expect(d[key].trim(), key).not.toBe('')
      expect(new Set(Object.values(DICTS).map((d) => ph(d[key]))).size, key).toBe(1)
    }
  })

  it('does not ship the api. prefix or untranslated key names', () => {
    for (const d of Object.values(DICTS)) for (const [k, v] of Object.entries(d)) expect(v).not.toBe(`api.${k}`)
    expect(Object.keys(DICTS.en).some((k) => k.startsWith('api.'))).toBe(false)
  })

  it('has a text for every error code the API can return', () => {
    for (const c of CODES) expect(DICTS.en[`err.${c}`], c).toBeTruthy()
  })

  it('converts the Uzbek script variants (not just copies them)', () => {
    expect(DICTS.uz_cyrl['home.title']).toBe('Қаерга борамиз?')
    expect(DICTS.uz_new['home.title']).toBe('Qayerga boramiz?')
    expect(DICTS.uz_cyrl['home.when_now']).not.toBe(DICTS.uz_latn['home.when_now'])
  })
})

describe('translate', () => {
  it('fills {placeholders} and leaves unknown ones visible', () => {
    expect(translate('en', 'home.offers_count', { n: 3 })).toBe('3 offers')
    expect(translate('ru', 'home.offers_count', { n: 3 })).toContain('3')
    expect(translate('en', 'home.offers_count')).toBe('{n} offers')
    expect(translate('en', 'home.offers_count', { x: 1 })).toBe('{n} offers')
  })

  it('shows the key for a missing text instead of crashing', () => {
    expect(translate('en', 'no.such.key')).toBe('no.such.key')
    for (const k of ['constructor', '__proto__', 'toString']) expect(translate('en', k)).toBe(k) // prototype names are not texts
  })

  it('maps API error codes to texts and falls back to the generic message', () => {
    expect(errorText('en', 'not_your_request')).toBe('This is not your request.')
    expect(errorText('en', 'something_new')).toBe(DICTS.en['err.generic'])
    expect(errorText('ru', 'bad_plate')).toContain('30 A 123 BC') // {example} filled in
    expect(errorText('uz_cyrl', 'bad_plate')).toContain('30 A 123 BC') // Latin letters survive the Cyrillic text
  })
})

describe('resolveLang', () => {
  it('accepts stored choices and Telegram codes', () => {
    expect(resolveLang('uz_cyrl')).toBe('uz_cyrl')
    expect(resolveLang('ru')).toBe('ru')
    expect(resolveLang('ru-RU')).toBe('ru')
    expect(resolveLang('en-US')).toBe('en')
    expect(resolveLang('uz')).toBe('uz_new')
  })

  it('defaults to the new Uzbek alphabet (decision 29) for anything else', () => {
    for (const x of [undefined, null, '', 'de', 'klingon', 'constructor', '__proto__']) expect(resolveLang(x)).toBe('uz_new')
  })
})
