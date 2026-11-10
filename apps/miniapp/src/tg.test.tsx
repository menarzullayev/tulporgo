import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PrimaryAction } from './components/PrimaryAction'
import { I18nProvider } from './i18n'
import { applyTheme, confirmDialog, haptic, inTelegram, initData, shareLink, shareUrl, startApp } from './tg'
import { installTelegram } from './test/utils'

describe('outside Telegram everything is a safe no-op', () => {
  it('has no initData and does not throw', () => {
    expect(inTelegram()).toBe(false)
    expect(initData()).toBe('')
    expect(() => {
      startApp()
      applyTheme()
      haptic('success')
    }).not.toThrow()
  })
})

describe('inside Telegram', () => {
  it('starts the SDK and maps the theme to CSS variables', () => {
    const tg = installTelegram()
    startApp()
    expect(tg.ready).toHaveBeenCalled()
    expect(tg.expand).toHaveBeenCalled()
    const root = document.documentElement
    expect(root.style.getPropertyValue('--tg-bg')).toBe('#212121')
    expect(root.style.getPropertyValue('--tg-surface')).toBe('#303030')
    expect(root.dataset.scheme).toBe('dark')
  })

  it('ignores theme keys it does not know (no CSS variable injection)', () => {
    installTelegram({ themeParams: { bg_color: '#111111', 'evil; background: url(x)': 'red' } })
    startApp()
    expect(document.documentElement.getAttribute('style')).not.toContain('evil')
  })

  it('uses the matching haptic channel', () => {
    const tg = installTelegram()
    haptic('success')
    haptic('error')
    haptic('select')
    haptic('light')
    expect(tg.haptic.notificationOccurred).toHaveBeenCalledWith('success')
    expect(tg.haptic.notificationOccurred).toHaveBeenCalledWith('error')
    expect(tg.haptic.selectionChanged).toHaveBeenCalled()
    expect(tg.haptic.impactOccurred).toHaveBeenCalledWith('light')
  })

  it('shares through Telegram when possible and encodes the link', () => {
    const tg = installTelegram()
    shareLink('https://tulporgo.uz/app/#/share/abc12345', 'Men & TulporGo')
    expect(tg.openTelegramLink).toHaveBeenCalledWith(shareUrl('https://tulporgo.uz/app/#/share/abc12345', 'Men & TulporGo'))
    expect(shareUrl('https://x.y/?a=1&b=2', 'a b')).toBe('https://t.me/share/url?url=https%3A%2F%2Fx.y%2F%3Fa%3D1%26b%3D2&text=a%20b')
  })

  it('asks for confirmation through Telegram', async () => {
    installTelegram({ showConfirm: (_m: string, cb: (ok: boolean) => void) => cb(false) })
    expect(await confirmDialog('sure?')).toBe(false)
  })
})

function Action({ onClick }: { onClick: () => void }) {
  return (
    <I18nProvider initial="en">
      <PrimaryAction text="Request a ride" onClick={onClick} />
    </I18nProvider>
  )
}

describe('PrimaryAction', () => {
  it('renders an ordinary button outside Telegram', async () => {
    const onClick = vi.fn()
    render(<Action onClick={onClick} />)
    await userEvent.click(screen.getByRole('button', { name: 'Request a ride' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('uses the native MainButton inside Telegram and renders no duplicate button', () => {
    const tg = installTelegram()
    const onClick = vi.fn()
    const { unmount } = render(<Action onClick={onClick} />)
    expect(screen.queryByRole('button')).toBeNull()
    expect(tg.main.setText).toHaveBeenCalledWith('Request a ride')
    expect(tg.main.show).toHaveBeenCalled()
    tg.main.onClick.mock.calls[0][0]() // Telegram invokes the registered handler
    expect(onClick).toHaveBeenCalledTimes(1)
    unmount()
    expect(tg.main.hide).toHaveBeenCalled()
    expect(tg.main.offClick).toHaveBeenCalledWith(tg.main.onClick.mock.calls[0][0])
  })
})
