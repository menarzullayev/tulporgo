import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { api, ApiError } from './api'
import { baseMe, installTelegram, trip } from './test/utils'

describe('App', () => {
  it('asks to open the app inside Telegram when the API refuses the (missing) auth', async () => {
    vi.spyOn(api, 'me').mockRejectedValue(new ApiError('unauthorized', 401))
    render(<App />)
    expect(await screen.findByText('This page works inside Telegram.')).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).toBeNull()
  })

  it('shows the three tabs and the order form for a signed-in user', async () => {
    vi.spyOn(api, 'me').mockResolvedValue(baseMe)
    vi.spyOn(api, 'myRequests').mockResolvedValue({ items: [] })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Where to?' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation')
    expect(nav.querySelectorAll('a')).toHaveLength(3)
    expect(screen.getByRole('link', { name: 'Order' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Profile' })).toHaveAttribute('href', '#/profile')
  })

  it('uses the stored language of the user, else the Telegram language', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ ...baseMe, lang: 'ru' })
    vi.spyOn(api, 'myRequests').mockResolvedValue({ items: [] })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Куда поедем?' })).toBeInTheDocument()
  })

  it('opens the public share page without calling /me', async () => {
    window.location.hash = '#/share/tok_abcdefgh12'
    const me = vi.spyOn(api, 'me')
    vi.spyOn(api, 'shared').mockResolvedValue({
      status: 'confirmed', finished: false, from: 'A', to: 'B', depart_at: null, driver_first_name: 'Sardor',
      car: { make: 'Cobalt', color: 'white', plate: '30A123BC' },
    })
    render(<App />)
    expect(await screen.findByText('Sardor')).toBeInTheDocument()
    expect(me).not.toHaveBeenCalled()
    expect(screen.queryByRole('navigation')).toBeNull()
  })

  it('routes to a trip and marks the Trips tab active', async () => {
    window.location.hash = '#/trip/21'
    vi.spyOn(api, 'me').mockResolvedValue(baseMe)
    vi.spyOn(api, 'trip').mockResolvedValue(trip())
    render(<App />)
    expect(await screen.findByText('30A123BC')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Trips' })).toHaveAttribute('aria-current', 'page')
  })

  it('opens the filter screen from the bot link ?page=feed (no hash) under the Profile tab', async () => {
    window.history.replaceState(null, '', '/?page=feed')
    try {
      vi.spyOn(api, 'me').mockResolvedValue(baseMe)
      vi.spyOn(api, 'feed').mockResolvedValue({ paused: false, delivery_linked: false, connected: true, consent_ok: true, groups: [], filters: [], kinds: [], max_filters: 20 })
      render(<App />)
      expect(await screen.findByRole('heading', { name: 'Requests from groups' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Profile' })).toHaveAttribute('aria-current', 'page')
    } finally {
      window.history.replaceState(null, '', '/')
    }
  })

  it('keeps an unknown ?page= on the home screen (negative)', async () => {
    window.history.replaceState(null, '', '/?page=nothing')
    try {
      vi.spyOn(api, 'me').mockResolvedValue(baseMe)
      vi.spyOn(api, 'myRequests').mockResolvedValue({ items: [] })
      const feed = vi.spyOn(api, 'feed')
      render(<App />)
      expect(await screen.findByRole('heading', { name: 'Where to?' })).toBeInTheDocument()
      expect(feed).not.toHaveBeenCalled()
    } finally {
      window.history.replaceState(null, '', '/')
    }
  })

  it('shows an unknown route as an error page, not a blank screen', async () => {
    window.location.hash = '#/definitely/not/a/page'
    vi.spyOn(api, 'me').mockResolvedValue(baseMe)
    render(<App />)
    expect(await screen.findByText('Something went wrong. Please try again.')).toBeInTheDocument()
  })

  it('shows the Telegram back button on sub-screens only', async () => {
    const tg = installTelegram()
    window.location.hash = '#/trip/21'
    vi.spyOn(api, 'me').mockResolvedValue(baseMe)
    vi.spyOn(api, 'trip').mockResolvedValue(trip())
    render(<App />)
    await screen.findByText('30A123BC')
    await waitFor(() => expect(tg.back.show).toHaveBeenCalled())
    expect(tg.back.onClick).toHaveBeenCalled()
  })

  it('does not show the back button on a top-level tab', async () => {
    const tg = installTelegram()
    vi.spyOn(api, 'me').mockResolvedValue(baseMe)
    vi.spyOn(api, 'myRequests').mockResolvedValue({ items: [] })
    render(<App />)
    await screen.findByRole('heading', { name: 'Where to?' })
    expect(tg.back.show).not.toHaveBeenCalled()
  })

  it('offers a retry when /me fails for a non-auth reason', async () => {
    const me = vi.spyOn(api, 'me').mockRejectedValueOnce(new ApiError('network', 0))
    installTelegram()
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('No connection')
    me.mockResolvedValue(baseMe)
    vi.spyOn(api, 'myRequests').mockResolvedValue({ items: [] })
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: 'Where to?' })).toBeInTheDocument()
  })
})
