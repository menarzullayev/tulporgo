import { useEffect, useState } from 'react'
import { api, apiBase } from '../api'
import { useI18n } from '../i18n'
import { inTelegram } from '../tg'
import { clearWebToken, hasWebToken, loginStartUrl, takeLoginError } from '../webAuth'

/**
 * "Telegram orqali kirish" for the site opened outside Telegram. Renders nothing inside Telegram (no request is
 * made either) and nothing when the server has Login with Telegram switched off.
 */
export function WebLogin() {
  const { t } = useI18n()
  const [enabled, setEnabled] = useState(false)
  const [failure] = useState(() => takeLoginError())
  const outside = !inTelegram()

  useEffect(() => {
    if (!outside) return
    let alive = true
    void api.loginConfig().then((c) => alive && setEnabled(c.enabled))
    return () => {
      alive = false
    }
  }, [outside])

  if (!outside || !enabled) return null
  return (
    <>
      {failure ? <p role="alert">{t(failure === 'denied' ? 'auth.denied' : 'auth.failed')}</p> : null}
      <a className="btn btn-primary" href={loginStartUrl(apiBase())}>
        {t('auth.telegram_login')}
      </a>
    </>
  )
}

/** Log out of a web session (plain browser only; inside Telegram there is no separate session to end). */
export function LogoutButton() {
  const { t } = useI18n()
  if (inTelegram() || !hasWebToken()) return null
  const logout = () => {
    clearWebToken()
    window.location.reload()
  }
  return (
    <button type="button" className="btn btn-secondary" onClick={logout}>
      {t('auth.logout')}
    </button>
  )
}
