// Placeholder page: shows the plans from core billing (decision 10) and hands "Pay" to W4's checkout endpoint
// (POST /api/payments/checkout). Everything is free for now (decision 44), so a missing checkout is not an error.
import { useState } from 'react'
import { api, ApiError } from '../api'
import { Badge, Button, Card, ErrorBox, Inline, Spinner } from '../components/ui'
import { formatDate, formatPrice } from '../format'
import { useAction, useAsync } from '../hooks'
import { useI18n } from '../i18n'
import { webApp } from '../tg'
import type { Plan } from '../types'

/** What a checkout response asks the app to do. Provider payloads differ, so only a safe https URL is followed. */
export function checkoutTarget(res: Record<string, unknown> | undefined): { url: string } | { text: string } | null {
  if (!res) return null
  const url = res.url ?? res.pay_url ?? res.payment_url
  if (typeof url === 'string' && /^https:\/\//i.test(url)) return { url }
  const text = res.instructions ?? res.text ?? res.message
  return typeof text === 'string' && text ? { text } : null
}

export default function Subscription() {
  const { t, lang } = useI18n()
  const state = useAsync(() => api.plans(), [])
  const { busy, error, run } = useAction()
  const [info, setInfo] = useState<string>()
  const [coming, setComing] = useState(false)

  if (state.loading && !state.data) return <Spinner />
  if (state.error && !state.data) return <ErrorBox error={state.error} onRetry={state.reload} />
  if (!state.data) return null
  const { plans, free_period, free_period_until, trial_days } = state.data

  const pay = async (p: Plan) => {
    setInfo(undefined)
    setComing(false)
    try {
      const res = await api.checkout(p.plan)
      const target = checkoutTarget(res)
      if (target && 'url' in target) {
        const app = webApp()
        if (app?.openLink) app.openLink(target.url)
        else window.open(target.url, '_blank', 'noopener')
      } else if (target) setInfo(target.text)
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
          <Button variant={p.plan === 'pro' ? 'primary' : 'secondary'} busy={busy} onClick={() => void pay(p)}>
            {t('sub.pay')}
          </Button>
        </Card>
      ))}
      <Inline error={error} />
      {coming ? <p className="notice">{t('sub.coming')}</p> : null}
      {info ? <p className="notice">{info}</p> : null}
    </div>
  )
}
