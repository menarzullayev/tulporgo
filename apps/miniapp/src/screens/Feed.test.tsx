import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyPlace } from '../components/PlaceField'
import { driverMe, renderApp } from '../test/utils'
import type { FeedFilter, FeedState } from '../types'
import Feed, { bodyFromFilter, buildFilterBody, emptyForm, formFromFilter, type FilterForm } from './Feed'

const SAMARQAND = { id: 3, name: 'Samarqand' }
const TOSHKENT = { id: 4, name: 'Toshkent' }
const places = [SAMARQAND, TOSHKENT].map((p) => ({ ...p, name_ru: null, kind: 'city', parent: null, lat: null, lon: null }))

const filter = (over: Partial<FeedFilter> = {}): FeedFilter => ({
  id: 11,
  name: 'Morning run',
  enabled: true,
  routes: [{ from: SAMARQAND, to: TOSHKENT, on_way: true }],
  time_from: '06:00',
  time_to: '09:30',
  include_asap: true,
  include_tomorrow: false,
  weekdays: [0, 1],
  seats_min: 2,
  seats_max: null,
  kinds: ['passenger', 'parcel'],
  group_chat_ids: [],
  ...over,
})

const feedState = (over: Partial<FeedState> = {}): FeedState => ({
  paused: false,
  delivery_linked: false,
  connected: true,
  consent_ok: true,
  groups: [
    { chat_id: -1001, title: 'Samarqand taksi' },
    { chat_id: -1002, title: 'Toshkent taksi' },
  ],
  filters: [filter()],
  kinds: ['passenger', 'parcel', 'cargo', 'delivery', 'bazaar'],
  max_filters: 20,
  ...over,
})

interface Call {
  method: string
  path: string
  body: unknown
}

/** A fake /api: records every call; `reply` can override the answer of a method + path. */
function server(state: FeedState, reply: (c: Call) => { status: number; json: unknown } | undefined = () => undefined) {
  const calls: Call[] = []
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.replace(/^\/api/, '')
    const call: Call = { method: init?.method ?? 'GET', path, body: init?.body ? JSON.parse(init.body as string) : undefined }
    if (!path.startsWith('/places')) calls.push(call)
    const over = reply(call)
    if (over) return new Response(JSON.stringify(over.json), { status: over.status })
    if (path.startsWith('/places')) return new Response(JSON.stringify({ items: places }))
    if (call.method === 'GET') return new Response(JSON.stringify(state))
    if (call.method === 'DELETE') return new Response(JSON.stringify({ ok: true }))
    if (path === '/userbot/feed/pause') return new Response(JSON.stringify({ ...state, paused: (call.body as { paused: boolean }).paused }))
    const body = call.body as Record<string, unknown>
    const id = call.method === 'PUT' ? Number(path.split('/').pop()) : 99
    const routes = (body.routes as { from: number | null; to: number | null; on_way: boolean }[]).map((r) => ({
      from: places.find((p) => p.id === r.from) ? { id: r.from, name: places.find((p) => p.id === r.from)!.name } : null,
      to: places.find((p) => p.id === r.to) ? { id: r.to, name: places.find((p) => p.id === r.to)!.name } : null,
      on_way: r.on_way,
    }))
    return new Response(JSON.stringify({ ...body, id, routes }))
  })
  vi.stubGlobal('fetch', fn)
  return { calls, writes: () => calls.filter((c) => c.method !== 'GET') }
}

afterEach(() => vi.unstubAllGlobals())

const open = async (state = feedState(), reply?: Parameters<typeof server>[1]) => {
  const s = server(state, reply)
  renderApp(<Feed />, { me: driverMe })
  await screen.findByRole('heading', { name: 'Requests from groups' })
  return s
}

/** Types into a place combobox and picks the suggestion. */
const pickPlace = async (box: HTMLElement, query: string, name: string) => {
  await userEvent.type(box, query)
  await userEvent.click(await screen.findByRole('option', { name: new RegExp(name) }))
}

describe('Feed screen', () => {
  it('lists the filters with a short summary', async () => {
    await open()
    expect(screen.getByText('Morning run')).toBeInTheDocument()
    expect(screen.getByText(/Samarqand → Toshkent/)).toBeInTheDocument()
    expect(screen.getByText(/on the way/)).toBeInTheDocument()
    const summary = screen.getByText(/06:00–09:30/)
    expect(summary).toHaveTextContent('now / no time')
    expect(summary).toHaveTextContent('Mon Tue')
    expect(summary).toHaveTextContent('Seats: 2+')
    expect(summary).toHaveTextContent('Passenger, Parcel')
    expect(summary).toHaveTextContent('all groups')
    expect(summary).not.toHaveTextContent('tomorrow') // include_tomorrow is false
    expect(screen.getByRole('switch', { name: /Morning run/ })).toBeChecked()
  })

  it('shows the empty state and no filters when there are none', async () => {
    await open(feedState({ filters: [] }))
    expect(screen.getByText(/No filters yet/)).toBeInTheDocument()
    expect(screen.queryByRole('switch', { name: /Turn the filter/ })).toBeNull()
  })

  it('says where the cards go: the bot chat until a channel is linked', async () => {
    await open()
    expect(screen.getByText(/make @tulporgobot an admin/)).toBeInTheDocument()
  })

  it('says the cards go to his channel when it is linked', async () => {
    await open(feedState({ delivery_linked: true }))
    expect(screen.getByText('Cards are sent to your channel.')).toBeInTheDocument()
    expect(screen.queryByText(/make @tulporgobot an admin/)).toBeNull()
  })

  it('explains a missing account connection and links to the login page', async () => {
    await open(feedState({ connected: false }))
    expect(screen.getByText(/not connected/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Connect an account' })).toHaveAttribute('href', '#/userbot/login')
  })

  it('tells him to accept the updated consent in the bot', async () => {
    await open(feedState({ consent_ok: false }))
    expect(screen.getByText(/Accept the updated consent/)).toHaveTextContent('/elon')
  })

  it('shows no warnings when everything is in order', async () => {
    await open()
    expect(screen.queryByText(/not connected/)).toBeNull()
    expect(screen.queryByText(/Accept the updated consent/)).toBeNull()
    expect(screen.queryByRole('link', { name: 'Connect an account' })).toBeNull()
  })

  it('pauses everything with one switch', async () => {
    const s = await open()
    const sw = screen.getByRole('switch', { name: /Pause all cards/ })
    expect(sw).not.toBeChecked()
    await userEvent.click(sw)
    await waitFor(() => expect(sw).toBeChecked())
    expect(s.writes()).toEqual([{ method: 'POST', path: '/userbot/feed/pause', body: { paused: true } }])
  })

  it('switches a filter off with a PUT of the same filter and only `enabled` changed', async () => {
    const s = await open()
    await userEvent.click(screen.getByRole('switch', { name: /Morning run/ }))
    await waitFor(() => expect(screen.getByRole('switch', { name: /Morning run/ })).not.toBeChecked())
    expect(s.writes()).toEqual([{ method: 'PUT', path: '/userbot/feed/filters/11', body: bodyFromFilter(filter(), false) }])
    expect(s.writes()[0].body).toMatchObject({ routes: [{ from: 3, to: 4, on_way: true }], weekdays: [0, 1], seats_min: 2, kinds: ['passenger', 'parcel'] })
  })

  it('deletes only after the confirmation', async () => {
    const s = await open()
    await userEvent.click(screen.getByRole('button', { name: /Delete: Morning run/ }))
    expect(screen.getByText('Delete the filter "Morning run"?')).toBeInTheDocument()
    expect(s.writes()).toEqual([]) // nothing is sent before the answer
    await userEvent.click(screen.getByRole('button', { name: 'Yes, delete' }))
    await waitFor(() => expect(screen.queryByText('Morning run')).toBeNull())
    expect(s.writes()).toEqual([{ method: 'DELETE', path: '/userbot/feed/filters/11', body: undefined }])
  })

  it('keeps the filter when the deletion is cancelled', async () => {
    const s = await open()
    await userEvent.click(screen.getByRole('button', { name: /Delete: Morning run/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByText('Morning run')).toBeInTheDocument()
    expect(s.writes()).toEqual([])
  })

  it('disables "Add a filter" at the limit', async () => {
    await open(feedState({ max_filters: 1 }))
    expect(screen.getByRole('button', { name: 'Add a filter' })).toBeDisabled()
    expect(screen.getByText(/limit of 1 filters/)).toBeInTheDocument()
  })

  it('shows the server error when the list cannot be loaded', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'not_a_driver' }), { status: 403 })))
    renderApp(<Feed />, { me: driverMe })
    expect(await screen.findByRole('alert')).toHaveTextContent(/driver/i)
  })
})

describe('Feed editor', () => {
  it('creates a filter and sends exactly what was entered', async () => {
    const s = await open(feedState({ filters: [] }))
    await userEvent.click(screen.getByRole('button', { name: 'Add a filter' }))
    await userEvent.type(screen.getByLabelText('Filter name'), '  Evening  ')
    const [from, to] = screen.getAllByRole('combobox')
    await pickPlace(from, 'sam', 'Samarqand')
    await pickPlace(to, 'tosh', 'Toshkent')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Include requests on the way' }))
    await userEvent.type(screen.getByLabelText('Time from'), '18:00')
    await userEvent.click(screen.getByRole('switch', { name: /Requests for tomorrow/ })) // off
    await userEvent.click(screen.getByRole('button', { name: 'Fri' }))
    await userEvent.click(screen.getByRole('button', { name: 'Mon' }))
    await userEvent.selectOptions(screen.getByLabelText('Seats at least'), '2')
    await userEvent.selectOptions(screen.getByLabelText('Seats at most'), '4')
    await userEvent.click(screen.getByRole('button', { name: 'Passenger' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(s.writes()).toHaveLength(1))
    expect(s.writes()[0]).toEqual({
      method: 'POST',
      path: '/userbot/feed/filters',
      body: {
        name: 'Evening',
        enabled: true,
        routes: [{ from: 3, to: 4, on_way: true }],
        time_from: '18:00',
        time_to: null,
        include_asap: true,
        include_tomorrow: false,
        weekdays: [0, 4],
        seats_min: 2,
        seats_max: 4,
        kinds: ['passenger'],
        group_chat_ids: [],
      },
    })
    expect(await screen.findByText('Evening')).toBeInTheDocument() // back on the list with the new filter
  })

  it('edits an existing filter with a PUT', async () => {
    const s = await open()
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(screen.getByLabelText('Filter name')).toHaveValue('Morning run')
    await userEvent.clear(screen.getByLabelText('Filter name'))
    await userEvent.type(screen.getByLabelText('Filter name'), 'Renamed')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(s.writes()).toHaveLength(1))
    expect(s.writes()[0]).toMatchObject({ method: 'PUT', path: '/userbot/feed/filters/11', body: { name: 'Renamed', routes: [{ from: 3, to: 4, on_way: true }] } })
    expect(await screen.findByText('Renamed')).toBeInTheDocument()
  })

  it('blocks a filter without any route and sends nothing (negative)', async () => {
    const s = await open(feedState({ filters: [] }))
    await userEvent.click(screen.getByRole('button', { name: 'Add a filter' }))
    await userEvent.type(screen.getByLabelText('Filter name'), 'No route')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Add at least one route')
    expect(s.writes()).toEqual([])
    expect(screen.getByRole('heading', { name: 'New filter' })).toBeInTheDocument() // stays in the editor
  })

  it('blocks a typed place that was never picked from the list (negative)', async () => {
    const s = await open(feedState({ filters: [] }))
    await userEvent.click(screen.getByRole('button', { name: 'Add a filter' }))
    await userEvent.type(screen.getByLabelText('Filter name'), 'Typed')
    await userEvent.type(screen.getAllByRole('combobox')[0], 'Somewhere')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('not picked from the list')
    expect(s.writes()).toEqual([])
  })

  it('blocks seats min above max and a missing name (negative)', async () => {
    const s = await open()
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.selectOptions(screen.getByLabelText('Seats at most'), '1') // min is 2
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Seats must be between 1 and 8.')
    await userEvent.clear(screen.getByLabelText('Filter name'))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Give the filter a name.')
    expect(s.writes()).toEqual([])
  })

  it('adds the reverse route as a second route', async () => {
    const s = await open()
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.click(screen.getByRole('button', { name: 'Add the reverse route' }))
    const boxes = screen.getAllByRole('group', { name: /^Route \d$/ })
    expect(boxes).toHaveLength(2)
    const second = within(boxes[1]).getAllByRole('combobox') as HTMLInputElement[]
    expect([second[0].value, second[1].value]).toEqual(['Toshkent', 'Samarqand'])
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(s.writes()).toHaveLength(1))
    expect((s.writes()[0].body as { routes: unknown[] }).routes).toEqual([
      { from: 3, to: 4, on_way: true },
      { from: 4, to: 3, on_way: true },
    ])
  })

  it('needs at least one chosen group when "chosen ones" is selected (negative), then sends the chosen ids', async () => {
    const s = await open()
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.click(screen.getByRole('radio', { name: 'Chosen ones' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Pick at least one group')
    expect(s.writes()).toEqual([])
    await userEvent.click(screen.getByRole('checkbox', { name: 'Toshkent taksi' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(s.writes()).toHaveLength(1))
    expect(s.writes()[0].body).toMatchObject({ group_chat_ids: [-1002] })
  })

  it('shows the translated text of a server 422 and stays in the editor (not_your_group)', async () => {
    const s = await open(feedState({ filters: [] }), (c) =>
      c.method === 'POST' ? { status: 422, json: { error: 'not_your_group', detail: 'x' } } : undefined,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Add a filter' }))
    await userEvent.type(screen.getByLabelText('Filter name'), 'Other')
    await pickPlace(screen.getAllByRole('combobox')[0], 'sam', 'Samarqand')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('That group is not among your taxi groups.')
    expect(screen.getByRole('heading', { name: 'New filter' })).toBeInTheDocument()
    expect(s.writes()).toHaveLength(1)
  })

  it.each([
    ['bad_time', 'Time must look like HH:MM'],
    ['bad_weekday', 'Invalid day of the week.'],
    ['unknown_place', 'not picked from the list'],
    ['empty_route', 'Add at least one route'],
    ['too_many_filters', 'filter limit'],
    ['filter_not_found', 'Filter not found'],
  ])('shows a text for the server code %s', async (code, text) => {
    await open(feedState(), (c) => (c.method === 'PUT' ? { status: code === 'filter_not_found' ? 404 : 422, json: { error: code } } : undefined))
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(text)
  })

  it('returns to the list without saving on Cancel', async () => {
    const s = await open()
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('heading', { name: 'Requests from groups' })).toBeInTheDocument()
    expect(s.writes()).toEqual([])
  })
})

describe('buildFilterBody', () => {
  const ok = (over: Partial<FilterForm> = {}): FilterForm => ({
    ...emptyForm(),
    name: 'A',
    routes: [{ from: { id: 3, text: 'Samarqand' }, to: emptyPlace, on_way: false }],
    ...over,
  })

  it('accepts one open-ended route (the other side is "anywhere")', () => {
    expect(buildFilterBody(ok())).toMatchObject({ body: { routes: [{ from: 3, to: null, on_way: false }], group_chat_ids: [] } })
  })

  it('rejects what the server would reject', () => {
    expect(buildFilterBody(ok({ name: '   ' }))).toEqual({ problem: 'feed.err_name' })
    expect(buildFilterBody(ok({ routes: [] }))).toEqual({ problem: 'err.empty_route' })
    expect(buildFilterBody(ok({ routes: [{ from: emptyPlace, to: { id: null, text: '  ' }, on_way: false }] }))).toEqual({ problem: 'err.empty_route' })
    expect(buildFilterBody(ok({ routes: [{ from: { id: null, text: 'typed' }, to: emptyPlace, on_way: false }] }))).toEqual({ problem: 'err.unknown_place' })
    expect(buildFilterBody(ok({ time_from: '8:30' }))).toEqual({ problem: 'err.bad_time' })
    expect(buildFilterBody(ok({ time_to: '24:00' }))).toEqual({ problem: 'err.bad_time' })
    expect(buildFilterBody(ok({ seats_min: '5', seats_max: '3' }))).toEqual({ problem: 'err.bad_seats' })
    expect(buildFilterBody(ok({ seats_min: '9' }))).toEqual({ problem: 'err.bad_seats' })
    expect(buildFilterBody(ok({ allGroups: false, groups: [] }))).toEqual({ problem: 'feed.err_group' })
  })

  it('round-trips a stored filter through the form unchanged', () => {
    const f = filter({ group_chat_ids: [-1001] })
    const form = formFromFilter(f, feedState())
    const { id, ...rest } = f
    expect(id).toBe(11)
    expect(buildFilterBody(form)).toEqual({ body: bodyFromFilter(f) })
    expect(bodyFromFilter(f)).toEqual({ ...rest, routes: [{ from: 3, to: 4, on_way: true }] })
  })

  it('drops a group he no longer has instead of sending it back', () => {
    const form = formFromFilter(filter({ group_chat_ids: [-1001, -9999] }), feedState())
    expect(form.groups).toEqual([-1001])
  })
})
