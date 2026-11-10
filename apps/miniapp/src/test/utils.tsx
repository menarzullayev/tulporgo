import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'
import { MeContext } from '../app-context'
import { I18nProvider } from '../i18n'
import type { LangCode, Me, Offer, RideRequest, Trip } from '../types'

export const baseMe: Me = {
  id: 1,
  first_name: 'Ali',
  username: null,
  lang: 'en',
  is_woman: false,
  phone_set: true,
  is_admin: false,
  driver: null,
  free_period: true,
  free_period_until: '2026-12-31',
  referral_link: null,
}

export const driverMe: Me = {
  ...baseMe,
  driver: {
    id: 7,
    status: 'active',
    verified: false,
    car_make: 'Cobalt',
    car_color: 'white',
    car_plate: '30A123BC',
    seats: 4,
    has_photo: false,
    has_documents: false,
    rating: 4.5,
    rating_count: 2,
    ambassador: false,
    plan: null,
    subscription_until: null,
    subscription_active: true,
    effective_plan: 'business',
  },
  referral_link: 'https://t.me/tulporgobot?start=ref_ABC234',
}

export function renderApp(ui: ReactElement, opts: { me?: Me; lang?: LangCode; setMe?: (m: Me) => void } = {}) {
  const me = opts.me ?? baseMe
  return render(
    <I18nProvider initial={opts.lang ?? 'en'}>
      <MeContext.Provider value={{ me, setMe: opts.setMe ?? vi.fn(), reloadMe: vi.fn() }}>{ui}</MeContext.Provider>
    </I18nProvider>,
  )
}

export const request = (over: Partial<RideRequest> = {}): RideRequest => ({
  id: 5,
  status: 'open',
  from_text: "Qo'shrabot",
  to_text: 'Samarqand',
  from_place_id: 3,
  to_place_id: 4,
  depart_at: null,
  seats: 1,
  women_only: false,
  note: null,
  price_hint: null,
  created_at: '2026-11-10T08:00:00+00:00',
  expires_at: null,
  offers_count: 0,
  ...over,
})

export const offer = (over: Partial<Offer> = {}): Offer => ({
  id: 11,
  request_id: 5,
  status: 'sent',
  price: 50000,
  counter_price: null,
  message: null,
  created_at: '2026-11-10T08:05:00+00:00',
  driver: { first_name: 'Sardor', car_make: 'Cobalt', car_color: 'white', rating: 4.5, rating_count: 2, verified: true },
  ...over,
})

export const trip = (over: Partial<Trip> = {}): Trip => ({
  id: 21,
  request_id: 5,
  status: 'confirmed',
  price: 50000,
  role: 'passenger',
  from_text: "Qo'shrabot",
  to_text: 'Samarqand',
  depart_at: '2026-11-11T07:30+05:00',
  seats: 1,
  women_only: false,
  created_at: '2026-11-10T08:10:00+00:00',
  completed_at: null,
  share_token: 'tok_abcdefgh12',
  share_url: 'https://tulporgo.uz/app/#/share/tok_abcdefgh12',
  car: { make: 'Cobalt', color: 'white', plate: '30A123BC' },
  driver_verified: true,
  driver_rating: 4.5,
  counterparty: { first_name: 'Sardor', username: 'sardor_u', phone: '+998901234567' },
  rated: false,
  ...over,
})

/** Install a fake Telegram WebApp; returns the spies. */
export function installTelegram(extra: Record<string, unknown> = {}) {
  const spies = {
    openTelegramLink: vi.fn(),
    openLink: vi.fn(),
    ready: vi.fn(),
    expand: vi.fn(),
    haptic: { impactOccurred: vi.fn(), notificationOccurred: vi.fn(), selectionChanged: vi.fn() },
    main: { setText: vi.fn(), show: vi.fn(), hide: vi.fn(), enable: vi.fn(), disable: vi.fn(), onClick: vi.fn(), offClick: vi.fn() },
    back: { show: vi.fn(), hide: vi.fn(), enable: vi.fn(), disable: vi.fn(), onClick: vi.fn(), offClick: vi.fn() },
  }
  window.Telegram = {
    WebApp: {
      initData: 'query_id=AAE&user=%7B%22id%22%3A1%7D&hash=abc',
      themeParams: { bg_color: '#212121', text_color: '#ffffff', hint_color: '#aaaaaa', secondary_bg_color: '#303030' },
      colorScheme: 'dark',
      ready: spies.ready,
      expand: spies.expand,
      openTelegramLink: spies.openTelegramLink,
      openLink: spies.openLink,
      HapticFeedback: spies.haptic,
      MainButton: spies.main,
      BackButton: spies.back,
      ...extra,
    },
  }
  return spies
}
