import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api'
import { offer, renderApp, request, trip } from '../test/utils'
import Offers, { validCounter } from './Offers'

afterEach(() => vi.useRealTimers())

describe('validCounter', () => {
  const o = { price: 50000 }
  it('accepts whole so\'m below the offer', () => {
    expect(validCounter('40000', o)).toBe(40000)
    expect(validCounter(' 1000 ', o)).toBe(1000)
    expect(validCounter('49999', o)).toBe(49999)
  })
  it('rejects everything the API would reject', () => {
    for (const bad of ['', 'abc', '50000', '60000', '999', '0', '-5', '4e4', '40000.5', '123456789']) expect(validCounter(bad, o), bad).toBeNull()
  })
})

describe('Offers screen', () => {
  it('waits for offers and shows the waiting state', async () => {
    vi.spyOn(api, 'offers').mockResolvedValue({ request: request(), offers: [], trip_id: null })
    renderApp(<Offers id={5} />)
    expect(await screen.findByText(/Waiting for driver offers/)).toBeInTheDocument()
  })

  it('refreshes by itself while the passenger waits', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const spy = vi.spyOn(api, 'offers').mockResolvedValue({ request: request(), offers: [], trip_id: null })
    renderApp(<Offers id={5} />)
    await screen.findByText(/Waiting for driver offers/)
    spy.mockResolvedValue({ request: request({ offers_count: 1 }), offers: [offer()], trip_id: null })
    await act(() => vi.advanceTimersByTimeAsync(5100))
    expect(await screen.findByText(/50.000 UZS/, { selector: 'strong' })).toBeInTheDocument()
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('keeps showing the last offers when a refresh fails', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const spy = vi.spyOn(api, 'offers').mockResolvedValue({ request: request(), offers: [offer()], trip_id: null })
    renderApp(<Offers id={5} />)
    await screen.findByText(/Sardor/)
    spy.mockRejectedValue(new ApiError('network', 0))
    await act(() => vi.advanceTimersByTimeAsync(5100))
    expect(screen.getByText(/Sardor/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows price, car, rating and the verified badge - but no phone or plate', async () => {
    vi.spyOn(api, 'offers').mockResolvedValue({ request: request(), offers: [offer({ message: 'Yo\'lda to\'xtamayman' })], trip_id: null })
    const { container } = renderApp(<Offers id={5} />)
    expect(await screen.findByText('Driver Sardor')).toBeInTheDocument()
    expect(screen.getByText('Cobalt, white')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
    expect(container.textContent).toContain('4.5')
    expect(container.textContent).not.toMatch(/\+998|\d{2}A\d{3}BC/)
  })

  it('accepts an offer and opens the trip', async () => {
    vi.spyOn(api, 'offers').mockResolvedValue({ request: request(), offers: [offer()], trip_id: null })
    const accept = vi.spyOn(api, 'acceptOffer').mockResolvedValue(trip({ id: 77 }))
    renderApp(<Offers id={5} />)
    await userEvent.click(await screen.findByRole('button', { name: /^Accept/ }))
    expect(accept).toHaveBeenCalledWith(11)
    await waitFor(() => expect(window.location.hash).toBe('#/trip/77'))
  })

  it('shows why accepting failed and does not navigate', async () => {
    vi.spyOn(api, 'offers').mockResolvedValue({ request: request(), offers: [offer()], trip_id: null })
    vi.spyOn(api, 'acceptOffer').mockRejectedValue(new ApiError('request_not_open', 409))
    renderApp(<Offers id={5} />)
    await userEvent.click(await screen.findByRole('button', { name: /^Accept/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The request is no longer open.')
    expect(window.location.hash).toBe('')
  })

  it('sends a lower counter price and only a valid one', async () => {
    vi.spyOn(api, 'offers').mockResolvedValue({ request: request(), offers: [offer()], trip_id: null })
    const counter = vi.spyOn(api, 'counterOffer').mockResolvedValue(offer({ status: 'countered', counter_price: 40000 }))
    renderApp(<Offers id={5} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Propose another price' }))
    const send = screen.getByRole('button', { name: 'Send' })
    const input = screen.getByLabelText('Your price, UZS')
    expect(send).toBeDisabled()
    await userEvent.type(input, '60000') // higher than the offer
    expect(send).toBeDisabled()
    await userEvent.clear(input)
    await userEvent.type(input, '4a0b0c00') // letters are stripped as they are typed
    expect(input).toHaveValue('40000')
    expect(send).toBeEnabled()
    await userEvent.click(send)
    expect(counter).toHaveBeenCalledWith(11, 40000)
  })

  it('shows a pending counter price and hides the counter button', async () => {
    vi.spyOn(api, 'offers').mockResolvedValue({
      request: request(),
      offers: [offer({ status: 'countered', counter_price: 40000 })],
      trip_id: null,
    })
    renderApp(<Offers id={5} />)
    expect(await screen.findByText(/You proposed 40.000 UZS/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Propose another price' })).toBeNull()
  })

  it('offers the trip once a driver is chosen and no longer lists offers', async () => {
    vi.spyOn(api, 'offers').mockResolvedValue({ request: request({ status: 'matched' }), offers: [offer({ status: 'accepted' })], trip_id: 21 })
    renderApp(<Offers id={5} />)
    expect(await screen.findByRole('link', { name: 'Open the trip' })).toHaveAttribute('href', '#/trip/21')
    expect(screen.queryByRole('button', { name: /^Accept/ })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Cancel the request' })).toBeNull()
  })

  it('cancels the request after confirmation, and not without it', async () => {
    vi.spyOn(api, 'offers').mockResolvedValue({ request: request(), offers: [], trip_id: null })
    const cancel = vi.spyOn(api, 'cancelRequest').mockResolvedValue(request({ status: 'cancelled' }))
    const confirm = vi.spyOn(window, 'confirm')
    renderApp(<Offers id={5} />)
    const button = await screen.findByRole('button', { name: 'Cancel the request' })
    confirm.mockReturnValueOnce(false)
    await userEvent.click(button)
    expect(cancel).not.toHaveBeenCalled()
    confirm.mockReturnValueOnce(true)
    await userEvent.click(button)
    await waitFor(() => expect(cancel).toHaveBeenCalledWith(5))
  })

  it('shows the error with a retry button when the request cannot be loaded', async () => {
    const spy = vi.spyOn(api, 'offers').mockRejectedValueOnce(new ApiError('not_your_request', 403))
    renderApp(<Offers id={5} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('This is not your request.')
    spy.mockResolvedValue({ request: request(), offers: [], trip_id: null })
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText(/Waiting for driver offers/)).toBeInTheDocument()
  })
})
