import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api'
import { emptyPlace } from '../components/PlaceField'
import { baseMe, installTelegram, renderApp, request } from '../test/utils'
import Home, { buildRequest, initialForm, type FormState } from './Home'

const NOW = Date.UTC(2026, 10, 10, 5, 0) // 10:00 in Tashkent
const form = (over: Partial<FormState> = {}): FormState => ({
  ...initialForm,
  from: { id: 3, text: "Qo'shrabot" },
  to: { id: 4, text: 'Samarqand' },
  ...over,
})

describe('buildRequest', () => {
  it('builds the API body from the form', () => {
    const r = buildRequest(form({ seats: 3, note: '  2 bags ' }), NOW)
    expect(r).toEqual({
      body: { from_place_id: 3, to_place_id: 4, from_text: "Qo'shrabot", to_text: 'Samarqand', depart_at: null, seats: 3, note: '2 bags' },
    })
  })

  it('keeps typed text without a place id (free-form addresses)', () => {
    const r = buildRequest(form({ from: { id: null, text: ' Qovunchi ' } }), NOW)
    expect(r).toMatchObject({ body: { from_place_id: null, from_text: 'Qovunchi' } })
  })

  it('sends the chosen departure as Tashkent local time', () => {
    expect(buildRequest(form({ later: true, when: '2026-11-11T07:30' }), NOW)).toMatchObject({ body: { depart_at: '2026-11-11T07:30' } })
  })

  it('rejects what the API would reject', () => {
    expect(buildRequest(form({ from: emptyPlace }), NOW)).toEqual({ problem: 'err.route_required' })
    expect(buildRequest(form({ to: { id: null, text: '   ' } }), NOW)).toEqual({ problem: 'err.route_required' })
    expect(buildRequest(form({ to: { id: 3, text: 'x' } }), NOW)).toEqual({ problem: 'err.same_place' })
    expect(buildRequest(form({ seats: 0 }), NOW)).toEqual({ problem: 'err.bad_seats' })
    expect(buildRequest(form({ seats: 9 }), NOW)).toEqual({ problem: 'err.bad_seats' })
    expect(buildRequest(form({ later: true, when: '' }), NOW)).toEqual({ problem: 'err.depart_in_past' })
    expect(buildRequest(form({ later: true, when: '2026-11-10T08:00' }), NOW)).toEqual({ problem: 'err.depart_in_past' })
    expect(buildRequest(form({ later: true, when: 'tomorrow' }), NOW)).toEqual({ problem: 'err.depart_in_past' })
  })

  it('allows "now" even when a stale time is still typed in the hidden field', () => {
    expect(buildRequest(form({ later: false, when: '2020-01-01T00:00' }), NOW)).toMatchObject({ body: { depart_at: null } })
  })
})

describe('Home screen', () => {
  beforeEach(() => {
    vi.spyOn(api, 'myRequests').mockResolvedValue({ items: [] })
    vi.spyOn(api, 'searchPlaces').mockResolvedValue({
      items: [{ id: 3, name: "Qo'shrabot", name_ru: null, kind: 'district', parent: 'Samarqand viloyati', lat: null, lon: null }],
    })
  })

  it('creates a request and opens its offers', async () => {
    const create = vi.spyOn(api, 'createRequest').mockResolvedValue(request({ id: 9 }))
    renderApp(<Home />)
    const [from, to] = screen.getAllByRole('combobox')
    await userEvent.type(from, 'Qovunchi')
    await userEvent.type(to, 'Samarqand')
    await userEvent.click(screen.getByRole('button', { name: 'Request a ride' }))
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0][0]).toMatchObject({ from_text: 'Qovunchi', to_text: 'Samarqand', seats: 1, depart_at: null })
    await waitFor(() => expect(window.location.hash).toBe('#/offers/9'))
  })

  it('picks a suggestion and sends its place id', async () => {
    const create = vi.spyOn(api, 'createRequest').mockResolvedValue(request({ id: 9 }))
    renderApp(<Home />)
    const [from, to] = screen.getAllByRole('combobox')
    await userEvent.type(from, 'qosh')
    await userEvent.click(await screen.findByRole('option', { name: /Qo'shrabot/ }))
    await userEvent.type(to, 'Samarqand')
    await userEvent.click(screen.getByRole('button', { name: 'Request a ride' }))
    await waitFor(() => expect(create).toHaveBeenCalled())
    expect(create.mock.calls[0][0]).toMatchObject({ from_place_id: 3, from_text: "Qo'shrabot", to_place_id: null })
  })

  it('does not call the API when the form is empty and shows why', async () => {
    const create = vi.spyOn(api, 'createRequest')
    renderApp(<Home />)
    await userEvent.click(screen.getByRole('button', { name: 'Request a ride' }))
    expect(create).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Enter where from and where to.')
  })

  it('shows the API error text and stays on the form', async () => {
    vi.spyOn(api, 'createRequest').mockRejectedValue(new ApiError('too_many_open_requests', 409))
    renderApp(<Home />)
    const [from, to] = screen.getAllByRole('combobox')
    await userEvent.type(from, 'A place')
    await userEvent.type(to, 'B place')
    await userEvent.click(screen.getByRole('button', { name: 'Request a ride' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many open requests. Cancel one first.')
    expect(window.location.hash).not.toContain('offers')
  })

  it('swaps from and to', async () => {
    renderApp(<Home />)
    const [from, to] = screen.getAllByRole('combobox') as HTMLInputElement[]
    await userEvent.type(from, 'AAA')
    await userEvent.type(to, 'BBB')
    await userEvent.click(screen.getByRole('button', { name: 'Swap' }))
    expect(from.value).toBe('BBB')
    expect(to.value).toBe('AAA')
  })

  it('shows the women-only marker only for women passengers', async () => {
    const { unmount } = renderApp(<Home />, { me: { ...baseMe, is_woman: true } })
    expect(screen.getByTestId('women-marker')).toBeInTheDocument()
    await screen.findByText('Nothing here yet.')
    unmount()
    renderApp(<Home />)
    expect(screen.queryByTestId('women-marker')).toBeNull()
    await screen.findByText('Nothing here yet.')
  })

  it('keeps the seat count between 1 and 8', async () => {
    renderApp(<Home />)
    const minus = screen.getByRole('button', { name: '-' })
    const plus = screen.getByRole('button', { name: '+' })
    expect(minus).toBeDisabled()
    for (let i = 0; i < 10; i++) if (!plus.hasAttribute('disabled')) await userEvent.click(plus)
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(plus).toBeDisabled()
  })

  it('lists open requests with their offer counts', async () => {
    vi.spyOn(api, 'myRequests').mockResolvedValue({
      items: [request({ offers_count: 2, price_hint: 45000 }), request({ id: 6, status: 'cancelled' })],
    })
    renderApp(<Home />)
    expect(await screen.findByText('2 offers')).toBeInTheDocument()
    expect(screen.getAllByRole('link')).toHaveLength(1) // the cancelled one is not listed
    expect(screen.getByRole('link')).toHaveAttribute('href', '#/offers/5')
  })

  it('works with the native MainButton inside Telegram', async () => {
    const tg = installTelegram()
    const create = vi.spyOn(api, 'createRequest').mockResolvedValue(request({ id: 4 }))
    renderApp(<Home />)
    await screen.findByText('Nothing here yet.')
    expect(screen.queryByRole('button', { name: 'Request a ride' })).toBeNull()
    const [from, to] = screen.getAllByRole('combobox')
    await userEvent.type(from, 'A place')
    await userEvent.type(to, 'B place')
    act(() => tg.main.onClick.mock.calls.at(-1)![0]())
    await waitFor(() => expect(create).toHaveBeenCalled())
  })
})
