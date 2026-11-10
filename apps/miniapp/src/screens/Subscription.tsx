// Subscription page (decisions 10, 44). Plans come from core billing; paying goes through W4's
// POST /api/payments/checkout. Rules: nothing to pay during the free period; the terms are accepted with an explicit
// button before any checkout (Telegram Stars rules, terms §6.6); only safe targets are opened.
import { useState } from 'react'
import { api, ApiError } from '../api'
import { Badge, Button, Card, ErrorBox, Inline, Spinner } from '../components/ui'
import { formatDate, formatPrice } from '../format'
import { useAction, useAsync } from '../hooks'
import { useI18n } from '../i18n'
import { openInvoice, openTelegram, webApp } from '../tg'
import type { Plan } from '../types'

export const TERMS_URL = 'https://tulporgo.uz/legal/terms'
export const BOT_OBUNA_URL = 'https://t.me/tulporgobot?start=obuna'
export const MONTHS = [1, 3, 6, 12] as const

export type CheckoutTarget = { url: string } | { invoice: string } | { bot: true } | { text: string }

/** What a checkout response asks the app to do (W4 puts it under `start`). Only safe targets are returned. */
export function checkoutTarget(res: Record<string, unknown> | undefined): CheckoutTarget | null {
  if (!res) return null
  const start = res.start && typeof res.start === 'object' ? (res.start as Record<string, unknown>) : res
  if (start.type === 'stars') {
    const link = start.invoice_link
    return typeof link === 'string' && /^https:\/\/t\.me\//i.test(link) ? { invoice: link } : null
  }
  if (start.type === 'p2p') return { bot: true } // the receipt photo is sent to the bot, so P2P continues there
  const url = start.url ?? start.pay_url ?? start.payment_url
  if (typeof url === 'string' && /^https:\/\//i.test(url)) return { url }
  const text = start.instructions ?? start.text ?? start.message
  return typeof text === 'string' && text ? { text } : null
}

export default function Subscription() {
  const { t, lang } = useI18n()
  const state = useAsync(() => api.plans(), [])
  const { busy, error, run } = useAction()
  const [choice, setChoice] = useState<Plan>()
  const [months, setMonths] = useState<number>(1)
  const [providers, setProviders] = useState<string[]>()
  const [provider, setProvider] = useState<string>()
  const [info, setInfo] = useState<string>()
  const [coming, setComing] = useState(false)
  const [p2p, setP2p] = useState(false)

  if (state.loading && !state.data) return <Spinner />
  if (state.error && !state.data) return <ErrorBox error={state.error} onRetry={state.reload} />
  if (!state.data) return null
  const { plans, free_period, free_period_until, trial_days } = state.data

  const reset = () => {
    setInfo(undefined)
    setComing(false)
    setP2p(false)
  }

  const choose = async (p: Plan) => {
    reset()
    setChoice(p)
    setMonths(1)
    try {
      const res = await api.paymentProviders()
      if (res.free_period) {
        setChoice(undefined) // the server says the free period is on: nothing to pay
        return
      }
      setProviders(res.providers)
      setProvider(res.providers[0])
      if (!res.providers.length) setComing(true)
    } catch (e) {
      setChoice(undefined)
      if (e instanceof ApiError && (e.status === 404 || e.status === 405 || e.status === 501)) setComing(true)
      else await run(() => Promise.reject(e))
    }
  }

  const confirmAndPay = async () => {
    if (!choice || !provider) return
    reset()
    if (provider === 'p2p') {
      setP2p(true)
      return
    }
    try {
      const target = checkoutTarget(await api.checkout(choice.plan, months, provider))
      if (target && 'url' in target) {
        const app = webApp()
        if (app?.openLink) app.openLink(target.url)
        else window.open(target.url, '_blank', 'noopener')
      } else if (target && 'invoice' in target) {
        if ((await openInvoice(target.invoice)) === 'paid') setInfo(t('sub.stars_paid'))
      } else if (target && 'bot' in target) setP2p(true)
      else if (target) setInfo(target.text)
      else setComing(true)
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 405 || e.status === 501)) setComing(true)
      else await run(() => Promise.reject(e))
    }
  }

  return (
    <div className="stack">
      <h1>{t('sub.title')}</h1>
      {free_period ? (
        <Card className="stack">
          <p>{t('sub.free_now')}</p>
          {free_period_until ? <p className="hint">{t('profile.sub_free', { date: formatDate(free_period_until, lang) })}</p> : null}
        </Card>
      ) : null}
      <p className="hint">{t('sub.trial', { n: trial_days })}</p>
      {plans.map((p) => (
        <Card key={p.plan} className="stack plan">
          <div className="offer-head">
            <h2>{t(`sub.plan.${p.plan}`)}</h2>
            {p.priority ? <Badge>{t('sub.feat.business')}</Badge> : null}
          </div>
          <strong className="price">{t('sub.per_month', { price: formatPrice(p.price_uzs) })}</strong>
          <p className="hint">{t(`sub.feat.${p.plan}`)}</p>
          {free_period ? null : (
            <Button variant={p.plan === 'pro' ? 'primary' : 'secondary'} busy={busy} onClick={() => void choose(p)}>
              {t('sub.pay')}
            </Button>
          )}
        </Card>
      ))}

      {choice && providers && providers.length ? (
        <Card className="stack" aria-label={t('sub.checkout')}>
          <h2>{t(`sub.plan.${choice.plan}`)}</h2>
          <div className="chips" role="radiogroup" aria-label={t('sub.months_label')}>
            {MONTHS.map((m) => (
              <Button key={m} role="radio" aria-checked={m === months} variant={m === months ? 'primary' : 'secondary'} onClick={() => setMonths(m)}>
                {t('sub.months', { n: m })}
              </Button>
            ))}
          </div>
          <strong className="price">{t('sub.total', { price: formatPrice(choice.price_uzs * months) })}</strong>
          <div className="chips" role="radiogroup" aria-label={t('sub.method')}>
            {providers.map((name) => (
              <Button key={name} role="radio" aria-checked={name === provider} variant={name === provider ? 'primary' : 'secondary'} onClick={() => setProvider(name)}>
                {t(`sub.provider.${name}`)}
              </Button>
            ))}
          </div>
          <p className="hint">
            {t('sub.terms_note')}{' '}
            <a href={TERMS_URL} target="_blank" rel="noopener noreferrer">
              {t('sub.terms_link')}
            </a>
          </p>
          <Button variant="primary" busy={busy} onClick={() => void confirmAndPay()}>
            {t('sub.confirm_pay')}
          </Button>
          <Button variant="secondary" onClick={() => setChoice(undefined)}>
            {t('sub.cancel')}
          </Button>
        </Card>
      ) : null}

      <Inline error={error} />
      {p2p ? (
        <Card className="stack">
          <p>{t('sub.p2p_in_bot')}</p>
          <Button variant="primary" onClick={() => openTelegram(BOT_OBUNA_URL)}>
            {t('sub.open_bot')}
          </Button>
        </Card>
      ) : null}
      {coming ? <p className="notice">{t('sub.coming')}</p> : null}
      {info ? <p className="notice">{info}</p> : null}
    </div>
  )
}
