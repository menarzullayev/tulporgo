import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api'
import { installTelegram, renderApp, trip } from '../test/utils'
import Trip, { tripActions } from './Trip'
import Trips from './Trips'

describe('tripActions', () => {
  const a = (status: 'confirmed' | 'started' | 'completed' | 'cancelled', role: 'passenger' | 'driver', rated = false) =>
    tripActions({ status, role, rated })

  it('confirmed: both may complete or cancel, only the driver starts', () => {
    expect(a('confirmed', 'passenger')).toMatchObject({ start: false, complete: true, cancel: true, share: true, rate: false })
    expect(a('confirmed', 'driver')).toMatchObject({ start: true, complete: true, cancel: true, share: false })
  })
  it('started: no cancelling and no second start', () => {
    expect(a('started', 'driver')).toMatchObject({ start: false, complete: true, cancel: false })
  })
  it('completed: only rating, once', () => {
    expect(a('completed', 'passenger')).toMatchObject({ complete: false, cancel: false, rate: true, share: true })
    expect(a('completed', 'passenger', true).rate).toBe(false)
  })
  it('cancelled: nothing to do and nothing to share', () => {
    expect(a('cancelled', 'passenger')).toEqual({ start: false, complete: false, cancel: false, rate: false, share: false })
  })
})

describe('Trip screen', () => {
  it('shows the trip card with the car, plate and contact links', async () => {
    vi.spyOn(api, 'trip').mockResolvedValue(trip())
    renderApp(<Trip id={21} />)
    expect(await screen.findByText('30A123BC')).toBeInTheDocument()
    expect(screen.getByText('Cobalt, white')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Call' })).toHaveAttribute('href', 'tel:+998901234567')
    expect(screen.getByText('Confirmed')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
  })

  it('shares the public link through Telegram and says what it reveals', async () => {
    const tg = installTelegram()
    vi.spyOn(api, 'trip').mockResolvedValue(trip())
    renderApp(<Trip id={21} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Share with family' }))
    expect(tg.openTelegramLink).toHaveBeenCalledTimes(1)
    const url = String(tg.openTelegramLink.mock.calls[0][0])
    expect(url).toContain(encodeURIComponent('https://tulporgo.uz/app/#/share/tok_abcdefgh12'))
    expect(url).not.toContain('998901234567') // the phone number never goes into the share text
    expect(screen.getByText(/No phone numbers/)).toBeInTheDocument()
  })

  it('does not offer sharing to the driver', async () => {
    vi.spyOn(api, 'trip').mockResolvedValue(trip({ role: 'driver' }))
    renderApp(<Trip id={21} />)
    await screen.findByText('30A123BC')
    expect(screen.queryByRole('button', { name: 'Share with family' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Start the trip' })).toBeInTheDocument()
  })

  it('completes the trip and reloads', async () => {
    const get = vi.spyOn(api, 'trip').mockResolvedValue(trip())
    const complete = vi.spyOn(api, 'completeTrip').mockResolvedValue(trip({ status: 'completed' }))
    renderApp(<Trip id={21} />)
    get.mockResolvedValue(trip({ status: 'completed' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Trip completed' }))
    expect(complete).toHaveBeenCalledWith(21)
    expect(await screen.findByText('Rate this trip')).toBeInTheDocument()
  })

  it('cancels only after confirmation', async () => {
    vi.spyOn(api, 'trip').mockResolvedValue(trip())
    const cancel = vi.spyOn(api, 'cancelTrip').mockResolvedValue(trip({ status: 'cancelled' }))
    const confirm = vi.spyOn(window, 'confirm')
    renderApp(<Trip id={21} />)
    const button = await screen.findByRole('button', { name: 'Cancel the trip' })
    confirm.mockReturnValueOnce(false)
    await userEvent.click(button)
    expect(cancel).not.toHaveBeenCalled()
    confirm.mockReturnValueOnce(true)
    await userEvent.click(button)
    await waitFor(() => expect(cancel).toHaveBeenCalledWith(21))
  })

  it('rates the driver: needs stars first, sends stars and comment', async () => {
    vi.spyOn(api, 'trip').mockResolvedValue(trip({ status: 'completed' }))
    const rate = vi.spyOn(api, 'rateTrip').mockResolvedValue({ ok: true, stars: 4 })
    renderApp(<Trip id={21} />)
    const send = await screen.findByRole('button', { name: 'Send rating' })
    expect(send).toBeDisabled()
    await userEvent.click(screen.getByRole('radio', { name: '4 stars' }))
    expect(screen.getByRole('radio', { name: '4 stars' })).toHaveAttribute('aria-checked', 'true')
    await userEvent.type(screen.getByLabelText('Comment (optional)'), 'Polite')
    await userEvent.click(send)
    expect(rate).toHaveBeenCalledWith(21, 4, 'Polite')
  })

  it('shows thanks instead of the form once rated', async () => {
    vi.spyOn(api, 'trip').mockResolvedValue(trip({ status: 'completed', rated: true }))
    renderApp(<Trip id={21} />)
    expect(await screen.findByText(/Your rating was saved/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send rating' })).toBeNull()
  })

  it('shows the API error for a forbidden trip', async () => {
    vi.spyOn(api, 'trip').mockRejectedValue(new ApiError('not_your_trip', 403))
    renderApp(<Trip id={21} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('This is not your trip.')
  })

  it('keeps unsafe contact values out of links', async () => {
    vi.spyOn(api, 'trip').mockResolvedValue(trip({ counterparty: { first_name: 'X', username: 'bad name/../x', phone: 'javascript:alert(1)' } }))
    renderApp(<Trip id={21} />)
    await screen.findByText('30A123BC')
    expect(screen.queryByRole('link', { name: 'Call' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Message on Telegram' })).toBeNull()
  })
})

describe('Trips list', () => {
  it('lists trips with status and links to each', async () => {
    vi.spyOn(api, 'myTrips').mockResolvedValue({ items: [trip(), trip({ id: 22, status: 'completed', role: 'driver' })] })
    renderApp(<Trips />)
    const links = await screen.findAllByRole('link')
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['#/trip/21', '#/trip/22'])
    expect(screen.getByText('Completed')).toBeInTheDocument()
    expect(screen.getByText('You are the driver')).toBeInTheDocument()
  })

  it('shows an empty state', async () => {
    vi.spyOn(api, 'myTrips').mockResolvedValue({ items: [] })
    renderApp(<Trips />)
    expect(await screen.findByText('Nothing here yet.')).toBeInTheDocument()
  })
})
