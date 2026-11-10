import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api'
import { renderApp } from '../test/utils'
import Share from './Share'

const shared = {
  status: 'started' as const,
  finished: false,
  from: "Qo'shrabot",
  to: 'Samarqand',
  depart_at: '2026-11-11T07:30+05:00',
  driver_first_name: 'Sardor',
  car: { make: 'Cobalt', color: 'white', plate: '30A123BC' },
}

describe('public share page', () => {
  it('shows route, status, car and the driver first name', async () => {
    const spy = vi.spyOn(api, 'shared').mockResolvedValue(shared)
    renderApp(<Share token="tok_abcdefgh12" />)
    expect(await screen.findByText(/Qo'shrabot → Samarqand/)).toBeInTheDocument()
    expect(screen.getByText('On the way')).toBeInTheDocument()
    expect(screen.getByText('Sardor')).toBeInTheDocument()
    expect(screen.getByText('30A123BC')).toBeInTheDocument()
    expect(spy).toHaveBeenCalledWith('tok_abcdefgh12')
  })

  it('needs no profile: it renders without the app shell or sign-in', async () => {
    vi.spyOn(api, 'shared').mockResolvedValue(shared)
    const me = vi.spyOn(api, 'me')
    renderApp(<Share token="tok_abcdefgh12" />)
    await screen.findByText('Sardor')
    expect(me).not.toHaveBeenCalled()
    expect(screen.queryByRole('navigation')).toBeNull()
  })

  it('states what the page shows, and shows no phone numbers or contact buttons', async () => {
    vi.spyOn(api, 'shared').mockResolvedValue(shared)
    const { container } = renderApp(<Share token="tok_abcdefgh12" />)
    await screen.findByText('Sardor')
    expect(screen.getByText(/only the route, the car and the driver's first name/)).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\+?998\d|tel:/)
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('says so when the trip is finished', async () => {
    vi.spyOn(api, 'shared').mockResolvedValue({ ...shared, status: 'completed', finished: true })
    renderApp(<Share token="tok_abcdefgh12" />)
    expect(await screen.findByText('The trip is finished.')).toBeInTheDocument()
  })

  it('shows a friendly message for an unknown or expired link', async () => {
    vi.spyOn(api, 'shared').mockRejectedValue(new ApiError('trip_not_found', 404))
    renderApp(<Share token="tok_abcdefgh12" />)
    expect(await screen.findByText('This link was not found or has expired.')).toBeInTheDocument()
    expect(screen.queryByText('Sardor')).toBeNull()
  })

  it('offers a retry on a network failure, not the "expired" message', async () => {
    vi.spyOn(api, 'shared').mockRejectedValue(new ApiError('network', 0))
    renderApp(<Share token="tok_abcdefgh12" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('No connection')
    expect(screen.queryByText(/expired/)).toBeNull()
  })
})
