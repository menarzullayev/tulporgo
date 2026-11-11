// Driver userbot login (decision 8): risk consent -> phone -> code -> 2FA password -> done.
// The code and the password are typed only into this form (Telegram blocks codes sent in chats), are never stored
// in the browser, and are cleared from state as soon as they are sent. Server contract: docs/goals/W2.md.
import { useState } from 'react'
import { api, ApiError } from '../api'
import { Button, Card, Field, Icon, Inline, Mascot } from '../components/ui'
import { useAction } from '../hooks'
import { useI18n } from '../i18n'
import { href } from '../router'
import { haptic } from '../tg'

export type Step = 'consent' | 'phone' | 'code' | 'password' | 'done' | 'unavailable'

const PASSWORD_HINTS = ['password_needed', 'password_required', '2fa_required', 'two_step_required', 'session_password_needed']

/** Decide what follows a successful or failed `login/code` call; tolerant of the exact wording W2 uses. */
export function afterCode(result: unknown | ApiError): Step {
  if (result instanceof ApiError) return PASSWORD_HINTS.includes(result.code) ? 'password' : 'code'
  const r = (result ?? {}) as Record<string, unknown>
  const flag = [r.status, r.next, r.step, r.state].find((v) => typeof v === 'string') as string | undefined
  if (r.password_required === true || r.needs_password === true || (flag && /password|2fa/i.test(flag))) return 'password'
  return 'done'
}

/** The endpoint family is not mounted (W2 not deployed): show a plain "not available" page. */
export const isUnavailable = (e: unknown): boolean =>
  e instanceof ApiError && e.code === 'generic' && (e.status === 404 || e.status === 405 || e.status === 501)

/** Errors after which the login cannot continue and must be started again from the phone number. */
export const RESTART = ['no_pending_login', 'login_expired', 'too_many_attempts', 'code_expired']

export default function UserbotLogin() {
  const { t, err } = useI18n()
  const [step, setStep] = useState<Step>('consent')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, run, clear } = useAction()

  const guarded = async (fn: () => Promise<unknown>): Promise<{ ok: true; value: unknown } | { ok: false; error: ApiError | undefined }> => {
    let failure: ApiError | undefined
    const value = await run(async () => {
      try {
        return await fn()
      } catch (e) {
        failure = e instanceof ApiError ? e : new ApiError('generic', 0)
        throw e
      }
    })
    return failure ? { ok: false, error: failure } : { ok: true, value }
  }

  // Consent is recorded by the bot (/elon); this screen only shows the risks. The API answers 403
  // `consent_required` on login/start when it is missing, and that message is shown on the phone step.
  const consent = () => setStep('phone')
  const sendPhone = async () => {
    const r = await guarded(() => api.userbotStart(phone.trim()))
    if (r.ok) setStep('code')
    else if (isUnavailable(r.error)) setStep('unavailable')
  }
  const sendCode = async () => {
    const r = await guarded(() => api.userbotCode(code.trim()))
    setCode('') // never keep a login code around
    const next = afterCode(r.ok ? r.value : (r.error as ApiError))
    if (next === 'code' && !r.ok && isUnavailable(r.error)) setStep('unavailable')
    else if (!r.ok && RESTART.includes(r.error?.code ?? '')) setStep('phone') // error text stays visible: start again
    else {
      if (next === 'password') clear()
      setStep(next)
      if (next === 'done') haptic('success')
    }
  }
  const sendPassword = async () => {
    const r = await guarded(() => api.userbotPassword(password))
    setPassword('') // never keep the 2FA password around
    if (r.ok) {
      haptic('success')
      setStep('done')
    } else if (RESTART.includes(r.error?.code ?? '')) setStep('phone')
  }

  if (step === 'unavailable')
    return (
      <div className="stack">
        <h1>{t('userbot.title')}</h1>
        <div className="empty">
          <Mascot name="sad" size={110} />
          <p>{t('userbot.unavailable')}</p>
        </div>
      </div>
    )

  return (
    <div className="stack">
      <h1>{t('userbot.title')}</h1>

      {step === 'consent' ? (
        <Card className="stack">
          <h2>{t('userbot.consent_title')}</h2>
          <ul className="risks">
            {['risk1', 'risk2', 'risk3'].map((k) => (
              <li key={k}>
                <Icon name="shield" size={22} />
                <span>{t(`userbot.${k}`)}</span>
              </li>
            ))}
          </ul>
          <Inline error={error} />
          <Button busy={busy} onClick={consent}>
            {t('userbot.consent_accept')}
          </Button>
        </Card>
      ) : null}

      {step === 'phone' ? (
        <Card className="stack">
          <Field label={t('userbot.phone_title')}>
            <input type="tel" inputMode="tel" autoComplete="tel" placeholder="+998 90 123 45 67" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </Field>
          <Inline error={error} />
          <Button disabled={phone.replace(/\D/g, '').length < 9} busy={busy} onClick={() => void sendPhone()}>
            {t('userbot.send_code')}
          </Button>
        </Card>
      ) : null}

      {step === 'code' ? (
        <Card className="stack">
          <Field label={t('userbot.code_title')} hint={t('userbot.code_hint')}>
            <input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]*" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} />
          </Field>
          <Inline error={error} />
          <Button disabled={code.length < 4} busy={busy} onClick={() => void sendCode()}>
            {t('userbot.verify')}
          </Button>
        </Card>
      ) : null}

      {step === 'password' ? (
        <Card className="stack">
          <Field label={t('userbot.password_title')} hint={t('userbot.password_hint')}>
            <input type="password" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          {error ? <p className="error-inline" role="alert">{err(error.code)}</p> : null}
          <Button disabled={!password} busy={busy} onClick={() => void sendPassword()}>
            {t('userbot.verify')}
          </Button>
        </Card>
      ) : null}

      {step === 'done' ? (
        <div className="empty">
          <Mascot name="thumbs" size={120} />
          <h2>{t('userbot.done_title')}</h2>
          <p>{t('userbot.done_hint')}</p>
          <a className="btn btn-secondary" href={href('/feed')}>
            {t('profile.feed_open')}
          </a>
        </div>
      ) : null}
    </div>
  )
}
