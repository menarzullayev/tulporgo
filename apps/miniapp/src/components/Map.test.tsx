import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api'
import { renderApp } from '../test/utils'
import MapPicker from './MapPicker'
import { PlaceField, emptyPlace, type PlaceValue } from './PlaceField'
import { useState } from 'react'

// Leaflet needs real layout; a tiny fake keeps the tests about OUR logic (snapping, confirm, tile source).
const leaflet = vi.hoisted(() => {
  const state: { click?: (e: { latlng: { lat: number; lng: number } }) => void; tileUrl?: string; options?: unknown } = {}
  const map = {
    setView: () => map,
    on: (_: string, cb: (e: { latlng: { lat: number; lng: number } }) => void) => {
      state.click = cb
      return map
    },
    remove: vi.fn(),
  }
  const layer = { addTo: () => layer, remove: vi.fn() }
  return {
    state,
    default: {
      map: () => map,
      tileLayer: (url: string, options: unknown) => {
        state.tileUrl = url
        state.options = options
        return layer
      },
      circleMarker: () => layer,
    },
  }
})
vi.mock('leaflet', () => ({ default: leaflet.default }))
vi.mock('leaflet/dist/leaflet.css', () => ({}))

describe('MapPicker', () => {
  beforeEach(() => {
    leaflet.state.click = undefined
  })

  it('uses OpenStreetMap tiles (no API key) with attribution', () => {
    renderApp(<MapPicker onPick={vi.fn()} onClose={vi.fn()} />)
    expect(leaflet.state.tileUrl).toBe('https://tile.openstreetmap.org/{z}/{x}/{y}.png')
    expect(JSON.stringify(leaflet.state.options)).toContain('OpenStreetMap')
    expect(JSON.stringify(leaflet.state.options)).not.toMatch(/key|token/i)
  })

  it('cannot confirm before a point is chosen', () => {
    const onPick = vi.fn()
    renderApp(<MapPicker onPick={onPick} onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Use this place' })).toBeDisabled()
    expect(onPick).not.toHaveBeenCalled()
  })

  it('snaps the tapped point to the nearest known place', async () => {
    const nearest = vi.spyOn(api, 'nearestPlace').mockResolvedValue({
      item: { id: 4, name: 'Samarqand shahri', name_ru: null, kind: 'city', parent: null, lat: 39.65, lon: 66.96 },
      distance_km: 1.2,
    })
    const onPick = vi.fn()
    renderApp(<MapPicker onPick={onPick} onClose={vi.fn()} />)
    act(() => leaflet.state.click?.({ latlng: { lat: 39.66, lng: 66.97 } }))
    await userEvent.click(await waitForEnabled())
    expect(nearest).toHaveBeenCalledWith(39.66, 66.97)
    expect(onPick).toHaveBeenCalledWith({ id: 4, text: 'Samarqand shahri' })
  })

  it('keeps a labelled coordinate when no place is close enough', async () => {
    vi.spyOn(api, 'nearestPlace').mockRejectedValue(new ApiError('place_not_found', 404))
    const onPick = vi.fn()
    renderApp(<MapPicker onPick={onPick} onClose={vi.fn()} />)
    act(() => leaflet.state.click?.({ latlng: { lat: 41.31234, lng: 69.2799 } }))
    await userEvent.click(await waitForEnabled())
    expect(onPick).toHaveBeenCalledWith({ id: null, text: 'Map point (41.3123, 69.2799)' })
  })

  it('closes without choosing', async () => {
    const onClose = vi.fn()
    const onPick = vi.fn()
    renderApp(<MapPicker onPick={onPick} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalled()
    expect(onPick).not.toHaveBeenCalled()
  })
})

async function waitForEnabled() {
  const button = screen.getByRole('button', { name: 'Use this place' })
  await waitFor(() => expect(button).toBeEnabled())
  return button
}

function Harness({ initial = emptyPlace }: { initial?: PlaceValue }) {
  const [v, setV] = useState(initial)
  return (
    <>
      <PlaceField label="From" value={v} onChange={setV} />
      <output data-testid="value">{JSON.stringify(v)}</output>
    </>
  )
}

describe('PlaceField', () => {
  it('opens the map, and a picked place fills the field', async () => {
    vi.spyOn(api, 'searchPlaces').mockResolvedValue({ items: [] })
    vi.spyOn(api, 'nearestPlace').mockResolvedValue({
      item: { id: 4, name: 'Samarqand shahri', name_ru: null, kind: 'city', parent: null, lat: 1, lon: 1 },
      distance_km: 1,
    })
    renderApp(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Pick on map' }))
    await screen.findByRole('dialog')
    act(() => leaflet.state.click?.({ latlng: { lat: 39.65, lng: 66.96 } }))
    await userEvent.click(await waitForEnabled())
    await waitFor(() => expect(screen.getByTestId('value')).toHaveTextContent('"id":4'))
    expect(screen.getByRole('combobox')).toHaveValue('Samarqand shahri')
    expect(screen.queryByRole('dialog')).toBeNull() // the map closed
  })

  it('editing the text after picking a place forgets the stale id', async () => {
    vi.spyOn(api, 'searchPlaces').mockResolvedValue({ items: [] })
    renderApp(<Harness initial={{ id: 4, text: 'Samarqand' }} />)
    await userEvent.type(screen.getByRole('combobox'), 'x')
    expect(screen.getByTestId('value')).toHaveTextContent('{"id":null,"text":"Samarqandx"}')
  })

  it('still works when the suggestion search fails', async () => {
    vi.spyOn(api, 'searchPlaces').mockRejectedValue(new ApiError('network', 0))
    renderApp(<Harness />)
    await userEvent.type(screen.getByRole('combobox'), 'Qovunchi')
    expect(screen.getByTestId('value')).toHaveTextContent('"text":"Qovunchi"')
    expect(screen.queryByRole('listbox')).toBeNull()
  })
})
