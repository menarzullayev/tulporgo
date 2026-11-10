import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api'
import type { Me } from '../types'
import { baseMe, driverMe, installTelegram, renderApp } from '../test/utils'
import Driver, { checkDriverForm } from './Driver'
import Profile, { subscriptionLine } from './Profile'
import Subscription, { checkoutTarget } from './Subscription'

const t = (k: string, p?: Record<string, string | number>) => `${k}${p ? JSON.stringify(p) : ''}`

describe('subscriptionLine', () => {
  it('shows the free period while it lasts', () => {
    expect(subscriptionLine({ ...baseMe, free_period: true, free_period_until: '2026-12-31' }, t, 'en')).toContain('profile.sub_free')
    expect(subscriptionLine({ ...baseMe, free_period: true, free_period_until: null }, t, 'en')).toBe('profile.sub_free_open')
  })
  it('shows the paid-until date, or "no subscription"', () => {
    const paid = { ...driverMe, free_period: false, driver: { ...driverMe.driver!, subscription_active: true, subscription_until: '2027-01-05T10:00:00+00:00' } }
    expect(subscriptionLine(paid, t, 'en')).toContain('profile.sub_until')
    expect(subscriptionLine({ ...paid, driver: { ...paid.driver, subscription_active: false } }, t, 'en')).toBe('profile.sub_none')
    expect(subscriptionLine({ ...baseMe, free_period: false }, t, 'en')).toBe('profile.sub_none')
  })
})

describe('Profile', () => {
  it('switches the language at once and stores it', async () => {
    const patch = vi.spyOn(api, 'patchMe').mockResolvedValue({ ...baseMe, lang: 'ru' })
    const setMe = vi.fn()
    renderApp(<Profile />, { setMe })
    await userEvent.click(screen.getByRole('radio', { name: 'Русский' }))
    expect(patch).toHaveBeenCalledWith({ lang: 'ru' })
    expect(await screen.findByText('Язык')).toBeInTheDocument() // texts are Russian immediately
    await waitFor(() => expect(setMe).toHaveBeenCalled())
  })

  it('offers all five languages', () => {
    renderApp(<Profile />)
    expect(screen.getAllByRole('radio').map((r) => r.textContent)).toEqual(['Özbekça', "O'zbekcha", 'Ўзбекча', 'Русский', 'English'])
  })

  it('toggles the women passenger marker through the API', async () => {
    const patch = vi.spyOn(api, 'patchMe').mockResolvedValue({ ...baseMe, is_woman: true })
    renderApp(<Profile />)
    await userEvent.click(screen.getByRole('switch'))
    expect(patch).toHaveBeenCalledWith({ is_woman: true })
  })

  it('shows an API error from saving', async () => {
    vi.spyOn(api, 'patchMe').mockRejectedValue(new ApiError('bad_lang', 422))
    renderApp(<Profile />)
    await userEvent.click(screen.getByRole('radio', { name: 'English' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Unknown language.')
  })

  it('invites a passenger to become a driver and hides driver-only blocks', () => {
    renderApp(<Profile />)
    expect(screen.getByRole('link', { name: 'Become a driver' })).toHaveAttribute('href', '#/driver')
    expect(screen.queryByTestId('referral-link')).toBeNull()
    expect(screen.queryByRole('link', { name: 'Connect an account' })).toBeNull()
  })

  it('shows the driver card, referral link and userbot entry for a driver', () => {
    const tg = installTelegram()
    renderApp(<Profile />, { me: driverMe })
    expect(screen.getByText('30A123BC')).toBeInTheDocument()
    expect(screen.getByTestId('referral-link')).toHaveTextContent('https://t.me/tulporgobot?start=ref_ABC234')
    expect(screen.getByText(/\+7 free days/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Connect an account' })).toHaveAttribute('href', '#/userbot/login')
    expect(screen.getByText(/No documents yet/)).toBeInTheDocument()
    expect(screen.getByTestId('sub-line')).toHaveTextContent('Free for everyone right now')
    expect(tg.openTelegramLink).not.toHaveBeenCalled()
  })

  it('shares the referral link through Telegram', async () => {
    const tg = installTelegram()
    renderApp(<Profile />, { me: driverMe })
    await userEvent.click(screen.getByRole('button', { name: 'Share' }))
    expect(String(tg.openTelegramLink.mock.calls[0][0])).toContain(encodeURIComponent('https://t.me/tulporgobot?start=ref_ABC234'))
  })

  it('shows the Verified badge only for verified drivers', () => {
    const verified: Me = { ...driverMe, driver: { ...driverMe.driver!, verified: true, has_documents: true } }
    renderApp(<Profile />, { me: verified })
    expect(screen.getByText('Verified')).toBeInTheDocument()
  })
})

describe('checkDriverForm', () => {
  const ok = { phone: '+998 90 123 45 67', car_make: 'Cobalt', car_color: 'white', car_plate: '30 A 123 BC', seats: 4, needPhone: true }
  it('accepts a good form', () => {
    expect(checkDriverForm(ok)).toBeNull()
    expect(checkDriverForm({ ...ok, car_plate: '01123abc' })).toBeNull() // company plate, any case
    expect(checkDriverForm({ ...ok, needPhone: false, phone: '' })).toBeNull()
  })
  it('catches what the API rejects', () => {
    expect(checkDriverForm({ ...ok, phone: '12' })).toBe('bad_phone')
    expect(checkDriverForm({ ...ok, phone: '' })).toBe('bad_phone')
    expect(checkDriverForm({ ...ok, car_plate: '99 ZZ 999 99' })).toBe('bad_plate')
    expect(checkDriverForm({ ...ok, car_plate: '' })).toBe('bad_plate')
    expect(checkDriverForm({ ...ok, seats: 0 })).toBe('bad_seats')
    expect(checkDriverForm({ ...ok, seats: 9 })).toBe('bad_seats')
    expect(checkDriverForm({ ...ok, car_make: ' ' })).toBe('generic')
  })
})

describe('Driver screen', () => {
  const fill = async () => {
    const boxes = screen.getAllByRole('textbox')
    await userEvent.type(boxes[0], 'Cobalt')
    await userEvent.type(boxes[1], 'white')
    await userEvent.type(boxes[2], '30 A 123 BC')
  }

  it('registers a driver whose phone is already known (no phone field)', async () => {
    const reg = vi.spyOn(api, 'registerDriver').mockResolvedValue(driverMe)
    const setMe = vi.fn()
    renderApp(<Driver />, { setMe })
    expect(screen.queryByPlaceholderText('+998 90 123 45 67')).toBeNull()
    await fill()
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))
    expect(reg).toHaveBeenCalledWith({ phone: undefined, car_make: 'Cobalt', car_color: 'white', car_plate: '30 A 123 BC', seats: 4 })
    await waitFor(() => expect(setMe).toHaveBeenCalledWith(driverMe))
  })

  it('asks for the phone when none is on file', async () => {
    const reg = vi.spyOn(api, 'registerDriver').mockResolvedValue(driverMe)
    renderApp(<Driver />, { me: { ...baseMe, phone_set: false } })
    await userEvent.type(screen.getByPlaceholderText('+998 90 123 45 67'), '+998 90 123 45 67')
    const boxes = screen.getAllByRole('textbox')
    await userEvent.type(boxes[1], 'Cobalt')
    await userEvent.type(boxes[2], 'white')
    await userEvent.type(boxes[3], '30A123BC')
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))
    expect(reg.mock.calls[0][0]).toMatchObject({ phone: '+998 90 123 45 67' })
  })

  it('stops at an invalid plate without calling the API', async () => {
    const reg = vi.spyOn(api, 'registerDriver')
    renderApp(<Driver />)
    const boxes = screen.getAllByRole('textbox')
    await userEvent.type(boxes[0], 'Cobalt')
    await userEvent.type(boxes[1], 'white')
    await userEvent.type(boxes[2], 'ABC')
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))
    expect(reg).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid plate number. Example: 30 A 123 BC.')
  })

  it('shows the API error for a taken plate', async () => {
    vi.spyOn(api, 'registerDriver').mockRejectedValue(new ApiError('plate_taken', 409))
    renderApp(<Driver />)
    await fill()
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('This plate number is already registered.')
  })

  describe('documents', () => {
    const jpg = (name: string) => new File([new Uint8Array([0xff, 0xd8, 0xff, 1, 2, 3])], name, { type: 'image/jpeg' })

    it('uploads licence and registration as multipart form data', async () => {
      const upload = vi.spyOn(api, 'uploadDocuments').mockResolvedValue({ ...driverMe, driver: { ...driverMe.driver!, has_documents: true } })
      const setMe = vi.fn()
      const { container } = renderApp(<Driver />, { me: driverMe, setMe })
      const inputs = container.querySelectorAll<HTMLInputElement>('input[type=file]')
      expect(inputs).toHaveLength(3)
      for (const i of inputs) expect(i.accept).toBe('image/*,application/pdf')
      await userEvent.upload(inputs[0], jpg('licence.jpg'))
      await userEvent.upload(inputs[1], jpg('techpass.jpg'))
      await userEvent.click(screen.getByRole('button', { name: 'Send' }))
      await waitFor(() => expect(upload).toHaveBeenCalledTimes(1))
      const form = upload.mock.calls[0][0] as FormData
      expect([...form.keys()].sort()).toEqual(['license', 'techpass'])
      expect(await screen.findByText('Documents sent.')).toBeInTheDocument()
      expect(setMe).toHaveBeenCalled()
    })

    it('does not upload with a missing document', async () => {
      const upload = vi.spyOn(api, 'uploadDocuments')
      const { container } = renderApp(<Driver />, { me: driverMe })
      await userEvent.upload(container.querySelectorAll<HTMLInputElement>('input[type=file]')[0], jpg('licence.jpg'))
      await userEvent.click(screen.getByRole('button', { name: 'Send' }))
      expect(upload).not.toHaveBeenCalled()
      expect(screen.getByRole('alert')).toHaveTextContent('Send photos of your licence and vehicle registration.')
    })

    it('refuses a file above the 8 MB limit before uploading', async () => {
      const upload = vi.spyOn(api, 'uploadDocuments')
      const { container } = renderApp(<Driver />, { me: driverMe })
      const inputs = container.querySelectorAll<HTMLInputElement>('input[type=file]')
      const big = new File([new Uint8Array(8 * 1024 * 1024 + 1)], 'big.pdf', { type: 'application/pdf' })
      await userEvent.upload(inputs[0], big)
      await userEvent.upload(inputs[1], jpg('techpass.jpg'))
      await userEvent.click(screen.getByRole('button', { name: 'Send' }))
      expect(upload).not.toHaveBeenCalled()
      expect(screen.getByRole('alert')).toHaveTextContent('The file is too large')
    })

    it('shows a server rejection (wrong file type)', async () => {
      vi.spyOn(api, 'uploadDocuments').mockRejectedValue(new ApiError('bad_file_type', 422))
      const { container } = renderApp(<Driver />, { me: driverMe })
      const inputs = container.querySelectorAll<HTMLInputElement>('input[type=file]')
      await userEvent.upload(inputs[0], jpg('a.jpg'))
      await userEvent.upload(inputs[1], jpg('b.jpg'))
      await userEvent.click(screen.getByRole('button', { name: 'Send' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Unsupported file type.')
    })

    it('tells the driver the documents are optional and kept private', () => {
      renderApp(<Driver />, { me: driverMe })
      expect(screen.getByText(/Documents are optional/)).toBeInTheDocument()
      expect(screen.getByText(/private chat/)).toBeInTheDocument()
    })
  })
})

describe('checkoutTarget', () => {
  it('follows only https URLs', () => {
    expect(checkoutTarget({ url: 'https://my.click.uz/pay?x=1' })).toEqual({ url: 'https://my.click.uz/pay?x=1' })
    expect(checkoutTarget({ pay_url: 'https://checkout.paycom.uz/abc' })).toEqual({ url: 'https://checkout.paycom.uz/abc' })
  })
  it('refuses javascript:, http: and data: targets', () => {
    for (const url of ['javascript:alert(1)', 'http://evil.example', 'data:text/html,x', '//evil.example', '']) expect(checkoutTarget({ url }), url).toBeNull()
  })
  it('falls back to showing instructions text', () => {
    expect(checkoutTarget({ instructions: 'Send to card 8600 ...' })).toEqual({ text: 'Send to card 8600 ...' })
    expect(checkoutTarget({ instructions: 42 })).toBeNull()
    expect(checkoutTarget(undefined)).toBeNull()
  })
})

describe('Subscription page', () => {
  const plans = {
    free_period: true,
    free_period_until: '2026-12-31',
    trial_days: 7,
    plans: [
      { plan: 'basic' as const, price_uzs: 29000, max_groups: 0, autopost: false, priority: false },
      { plan: 'pro' as const, price_uzs: 59000, max_groups: 15, autopost: true, priority: false },
      { plan: 'business' as const, price_uzs: 99000, max_groups: null, autopost: true, priority: true },
    ],
  }

  it('lists the plans with the prices from the API and the free period', async () => {
    vi.spyOn(api, 'plans').mockResolvedValue(plans)
    renderApp(<Subscription />)
    expect(await screen.findByText(/29.000 UZS \/ month/)).toBeInTheDocument()
    expect(screen.getByText(/59.000 UZS/)).toBeInTheDocument()
    expect(screen.getByText(/99.000 UZS/)).toBeInTheDocument()
    expect(screen.getByText(/Everything is free for now/)).toBeInTheDocument()
    expect(screen.getByText('7-day free trial')).toBeInTheDocument()
  })

  it('opens the provider page for a checkout URL', async () => {
    const tg = installTelegram()
    vi.spyOn(api, 'plans').mockResolvedValue(plans)
    const checkout = vi.spyOn(api, 'checkout').mockResolvedValue({ url: 'https://my.click.uz/pay' })
    renderApp(<Subscription />)
    await userEvent.click((await screen.findAllByRole('button', { name: 'Pay' }))[1])
    expect(checkout).toHaveBeenCalledWith('pro')
    expect(tg.openLink).toHaveBeenCalledWith('https://my.click.uz/pay')
  })

  it('does not open an unsafe URL from the server', async () => {
    const tg = installTelegram()
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    vi.spyOn(api, 'plans').mockResolvedValue(plans)
    vi.spyOn(api, 'checkout').mockResolvedValue({ url: 'javascript:alert(1)' })
    renderApp(<Subscription />)
    await userEvent.click((await screen.findAllByRole('button', { name: 'Pay' }))[0])
    expect(tg.openLink).not.toHaveBeenCalled()
    expect(open).not.toHaveBeenCalled()
    expect(await screen.findByText('Payments will be available soon.')).toBeInTheDocument()
  })

  it('says payments are coming when checkout is not deployed', async () => {
    vi.spyOn(api, 'plans').mockResolvedValue(plans)
    vi.spyOn(api, 'checkout').mockRejectedValue(new ApiError('generic', 404))
    renderApp(<Subscription />)
    await userEvent.click((await screen.findAllByRole('button', { name: 'Pay' }))[0])
    expect(await screen.findByText('Payments will be available soon.')).toBeInTheDocument()
  })

  it('shows a real checkout error as an error', async () => {
    vi.spyOn(api, 'plans').mockResolvedValue(plans)
    vi.spyOn(api, 'checkout').mockRejectedValue(new ApiError('not_a_driver', 403))
    renderApp(<Subscription />)
    await userEvent.click((await screen.findAllByRole('button', { name: 'Pay' }))[0])
    expect(await screen.findByRole('alert')).toHaveTextContent('Register as a driver first.')
  })
})
