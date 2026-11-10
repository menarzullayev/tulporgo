import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api'
import { driverMe, renderApp } from '../test/utils'
import UserbotLogin, { afterCode, isUnavailable } from './UserbotLogin'

describe('afterCode', () => {
  it('goes to the password step only when the server asks for 2FA', () => {
    expect(afterCode({ status: 'password_required' })).toBe('password')
    expect(afterCode({ next: '2fa' })).toBe('password')
    expect(afterCode({ password_required: true })).toBe('password')
    expect(afterCode(new ApiError('password_needed', 401))).toBe('password')
    expect(afterCode({ status: 'connected' })).toBe('done')
    expect(afterCode({ ok: true })).toBe('done')
    expect(afterCode(null)).toBe('done')
  })
  it('stays on the code step after a wrong code', () => {
    expect(afterCode(new ApiError('bad_code', 422))).toBe('code')
    expect(afterCode(new ApiError('generic', 500))).toBe('code')
  })
  it('recognises a missing endpoint family', () => {
    expect(isUnavailable(new ApiError('generic', 404))).toBe(true)
    expect(isUnavailable(new ApiError('generic', 501))).toBe(true)
    expect(isUnavailable(new ApiError('bad_code', 422))).toBe(false)
    expect(isUnavailable(new Error('x'))).toBe(false)
  })
})

const consent = async () => userEvent.click(await screen.findByRole('button', { name: 'I agree' }))
const phone = async (value = '+998 90 123 45 67') => {
  await userEvent.type(screen.getByRole('textbox'), value)
  await userEvent.click(screen.getByRole('button', { name: 'Send the code' }))
}

describe('Userbot login', () => {
  it('shows the risks first and nothing else', () => {
    const start = vi.spyOn(api, 'userbotStart')
    renderApp(<UserbotLogin />, { me: driverMe })
    expect(screen.getByText(/limited or banned/)).toBeInTheDocument()
    expect(screen.getByText(/never bypasses Telegram limits/)).toBeInTheDocument()
    expect(screen.getByText(/stored encrypted/)).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(start).not.toHaveBeenCalled()
  })

  it('runs consent -> phone -> code -> done', async () => {
    const s = vi.spyOn(api, 'userbotStart').mockResolvedValue({ status: 'code_sent' })
    const v = vi.spyOn(api, 'userbotCode').mockResolvedValue({ status: 'connected' })
    const p = vi.spyOn(api, 'userbotPassword')
    renderApp(<UserbotLogin />, { me: driverMe })
    await consent()
    await phone()
    expect(s).toHaveBeenCalledWith('+998 90 123 45 67')
    await userEvent.type(await screen.findByRole('textbox'), '12345')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(v).toHaveBeenCalledWith('12345')
    expect(await screen.findByText('Account connected')).toBeInTheDocument()
    expect(p).not.toHaveBeenCalled() // no 2FA password was requested, so none is asked for
  })

  it('asks for the 2FA password only when needed, and never keeps it', async () => {
    vi.spyOn(api, 'userbotStart').mockResolvedValue({})
    vi.spyOn(api, 'userbotCode').mockRejectedValue(new ApiError('password_needed', 401))
    const pw = vi.spyOn(api, 'userbotPassword').mockResolvedValue({ status: 'connected' })
    renderApp(<UserbotLogin />, { me: driverMe })
    await consent()
    await phone()
    await userEvent.type(await screen.findByRole('textbox'), '54321')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    const field = await screen.findByLabelText(/Two-step password/)
    expect(field).toHaveAttribute('type', 'password')
    expect(field).toHaveAttribute('autocomplete', 'off')
    await userEvent.type(field, 's3cret pass')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(pw).toHaveBeenCalledWith('s3cret pass')
    expect(await screen.findByText('Account connected')).toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain('s3cret pass')
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toMatch(/s3cret|54321/)
  })

  it('stays on the code step after a wrong code and shows the error', async () => {
    vi.spyOn(api, 'userbotStart').mockResolvedValue({})
    vi.spyOn(api, 'userbotCode').mockRejectedValue(new ApiError('generic', 422))
    renderApp(<UserbotLogin />, { me: driverMe })
    await consent()
    await phone()
    await userEvent.type(await screen.findByRole('textbox'), '00000')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('') // the code is cleared even on failure
    expect(screen.queryByText('Account connected')).toBeNull()
  })

  it('keeps digits only in the code field and requires a plausible phone', async () => {
    vi.spyOn(api, 'userbotStart').mockResolvedValue({})
    renderApp(<UserbotLogin />, { me: driverMe })
    await consent()
    const send = screen.getByRole('button', { name: 'Send the code' })
    expect(send).toBeDisabled()
    await userEvent.type(screen.getByRole('textbox'), '12')
    expect(send).toBeDisabled()
    await userEvent.type(screen.getByRole('textbox'), '3456789')
    expect(send).toBeEnabled()
    await userEvent.click(send)
    const code = await screen.findByRole('textbox')
    await userEvent.type(code, '1a2-3b')
    expect(code).toHaveValue('123')
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled() // fewer than 4 digits
  })

  it('reports an unavailable login only for a missing endpoint, not for no_pending_login', async () => {
    vi.spyOn(api, 'userbotStart').mockRejectedValue(new ApiError('generic', 404))
    renderApp(<UserbotLogin />, { me: driverMe })
    await consent()
    await phone()
    expect(await screen.findByText('Auto-posting is not available yet.')).toBeInTheDocument()
  })

  it('does not call any API when consent is accepted (the bot records it)', async () => {
    const start = vi.spyOn(api, 'userbotStart')
    renderApp(<UserbotLogin />, { me: driverMe })
    await consent()
    expect(start).not.toHaveBeenCalled()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('tells the driver to consent in the bot when the API answers consent_required', async () => {
    vi.spyOn(api, 'userbotStart').mockRejectedValue(new ApiError('consent_required', 403))
    renderApp(<UserbotLogin />, { me: driverMe })
    await consent()
    await phone()
    expect(await screen.findByRole('alert')).toHaveTextContent('/elon')
    expect(screen.getByRole('button', { name: 'Send the code' })).toBeInTheDocument() // still on the phone step
  })

  it.each(['no_pending_login', 'login_expired', 'too_many_attempts', 'code_expired'])(
    'goes back to the phone step after %s',
    async (code) => {
      vi.spyOn(api, 'userbotStart').mockResolvedValue({})
      vi.spyOn(api, 'userbotCode').mockRejectedValue(new ApiError(code, 429))
      renderApp(<UserbotLogin />, { me: driverMe })
      await consent()
      await phone()
      await userEvent.type(await screen.findByRole('textbox'), '12345')
      await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
      expect(await screen.findByRole('button', { name: 'Send the code' })).toBeInTheDocument()
      expect(screen.getByRole('alert')).toBeInTheDocument()
    },
  )

  it('keeps the code step after a wrong code (bad_code)', async () => {
    vi.spyOn(api, 'userbotStart').mockResolvedValue({})
    vi.spyOn(api, 'userbotCode').mockRejectedValue(new ApiError('bad_code', 422))
    renderApp(<UserbotLogin />, { me: driverMe })
    await consent()
    await phone()
    await userEvent.type(await screen.findByRole('textbox'), '12345')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The code is wrong.')
    expect(screen.queryByRole('button', { name: 'Send the code' })).toBeNull()
  })

  it('shows the warning not to type the code into a Telegram chat', async () => {
    vi.spyOn(api, 'userbotStart').mockResolvedValue({})
    renderApp(<UserbotLogin />, { me: driverMe })
    await consent()
    await phone()
    expect(await screen.findByText(/Never type it into a Telegram chat/)).toBeInTheDocument()
  })
})
