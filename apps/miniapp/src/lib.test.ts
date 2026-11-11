import { describe, expect, it } from 'vitest'
import { departAtForApi, formatDate, formatDateTime, formatPrice, tashkentNowInput, telHref, tgHref } from './format'
import { fitWithin, prepareImage, tooLarge, MAX_UPLOAD_BYTES } from './imageUtil'
import { parseHash, parseLocation } from './router'

describe('format', () => {
  it('groups prices by thousands', () => {
    expect(formatPrice(50000)).toBe('50 000')
    expect(formatPrice(999)).toBe('999')
    expect(formatPrice(1234567)).toBe('1 234 567')
  })

  it('shows times in Tashkent regardless of the device zone', () => {
    expect(formatDateTime('2026-11-10T02:30:00Z', 'en')).toContain('07:30')
    expect(formatDateTime('2026-11-10T19:30:00Z', 'ru')).toContain('00:30') // +5h crosses midnight
    expect(formatDateTime('garbage', 'en')).toBe('garbage') // never throws on bad input
    expect(formatDate('2026-12-31', 'en')).toContain('2026')
  })

  it('computes the Tashkent wall clock for the datetime-local min attribute', () => {
    expect(tashkentNowInput(Date.UTC(2026, 10, 10, 22, 15))).toBe('2026-11-11T03:15')
  })

  it('sends only well-formed local times to the API', () => {
    expect(departAtForApi('2026-11-11T07:30')).toBe('2026-11-11T07:30')
    for (const bad of ['', '2026-11-11', '07:30', 'tomorrow', '2026-11-11T07:30:00Z; DROP']) expect(departAtForApi(bad)).toBeNull()
  })

  it('builds tel: and t.me links only from plausible values', () => {
    expect(telHref('+998 90 123 45 67')).toBe('tel:+998901234567')
    for (const bad of [null, undefined, '', '12', 'javascript:alert(1)', '+998 90 abc']) expect(telHref(bad)).toBeNull()
    expect(tgHref('sardor_u')).toBe('https://t.me/sardor_u')
    for (const bad of [null, '', 'a', 'has space', 'x/../y', "o'reilly"]) expect(tgHref(bad)).toBeNull()
  })
})

describe('router', () => {
  it('parses every screen', () => {
    expect(parseHash('')).toEqual({ name: 'home', params: {} })
    expect(parseHash('#/')).toEqual({ name: 'home', params: {} })
    expect(parseHash('#/offers/12')).toEqual({ name: 'offers', params: { id: '12' } })
    expect(parseHash('#/trip/3').params.id).toBe('3')
    expect(parseHash('#/trips').name).toBe('trips')
    expect(parseHash('#/profile').name).toBe('profile')
    expect(parseHash('#/driver').name).toBe('driver')
    expect(parseHash('#/subscription').name).toBe('subscription')
    expect(parseHash('#/userbot/login').name).toBe('userbot')
    expect(parseHash('#/share/AbC-_123xyz')).toEqual({ name: 'share', params: { token: 'AbC-_123xyz' } })
    expect(parseHash('#/offers/12?x=1').params.id).toBe('12') // query part ignored
  })

  it('rejects malformed routes instead of guessing', () => {
    for (const bad of ['#/offers/abc', '#/offers/', '#/trip/1/2', '#/share/short', '#/share/has space!!', '#/share/' + 'a'.repeat(65), '#/nope', '#//profile', '#/userbot']) {
      expect(parseHash(bad).name, bad).toBe('notfound')
    }
  })
})

describe('parseLocation', () => {
  it('routes the bot link ?page=userbot to the login screen', () => {
    expect(parseLocation('', '?page=userbot').name).toBe('userbot')
    expect(parseLocation('#', '?page=userbot').name).toBe('userbot')
  })
  it('routes the bot link ?page=feed to the filter screen, and #/feed too', () => {
    expect(parseLocation('', '?page=feed').name).toBe('feed')
    expect(parseLocation('#', '?page=feed').name).toBe('feed')
    expect(parseLocation('#/feed', '').name).toBe('feed')
    expect(parseLocation('#/trips', '?page=feed').name).toBe('trips') // an in-app route wins
  })
  it('does not route look-alike or unknown pages to the feed (negative)', () => {
    for (const q of ['?page=feed2', '?page=Feed', '?page=feeds', '?page=constructor', '?page=__proto__', '?feed=1', '?page=']) {
      expect(parseLocation('', q).name, q).toBe('home')
    }
    expect(parseHash('#/feed/1').name).toBe('notfound')
    expect(parseHash('#/feeds').name).toBe('notfound')
  })
  it('lets an in-app route win and ignores other pages', () => {
    expect(parseLocation('#/trips', '?page=userbot').name).toBe('trips')
    expect(parseLocation('', '?page=admin').name).toBe('home')
    expect(parseLocation('', '').name).toBe('home')
    expect(parseLocation('', '?page=userbot2').name).toBe('home')
  })
})

describe('imageUtil', () => {
  it('scales down to the longest side and never up', () => {
    expect(fitWithin(4000, 3000, 1600)).toEqual({ w: 1600, h: 1200 })
    expect(fitWithin(800, 600, 1600)).toEqual({ w: 800, h: 600 })
    expect(fitWithin(1, 5000, 1600).w).toBeGreaterThanOrEqual(1)
  })

  it('passes PDFs and undecodable files through untouched', async () => {
    const pdf = new File(['%PDF-1.7'], 'a.pdf', { type: 'application/pdf' })
    expect(await prepareImage(pdf)).toBe(pdf)
    const broken = new File(['not an image'], 'a.jpg', { type: 'image/jpeg' })
    expect(await prepareImage(broken)).toBe(broken) // jsdom cannot decode: the original is kept
  })

  it('flags files above the API limit', () => {
    expect(tooLarge(new File([new Uint8Array(MAX_UPLOAD_BYTES + 1)], 'big.jpg'))).toBe(true)
    expect(tooLarge(new File([new Uint8Array(1000)], 'ok.jpg'))).toBe(false)
  })
})
