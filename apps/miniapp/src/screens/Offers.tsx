import { useState } from 'react'
import { api } from '../api'
import { Badge, Button, Card, Empty, ErrorBox, Icon, Inline, Mascot, Rating, Spinner } from '../components/ui'
import { formatDateTime, formatPrice } from '../format'
import { useAction, useAsync } from '../hooks'
import { useI18n } from '../i18n'
import { href, navigate } from '../router'
import { confirmDialog, haptic } from '../tg'
import type { Offer } from '../types'

/** True when the counter price is something the API will accept (whole so'm, lower than the offer, >= 1 000). */
export function validCounter(value: string, offer: Pick<Offer, 'price'>): number | null {
  if (!/^\d{4,8}$/.test(value.trim())) return null
  const n = Number(value)
  return n >= 1000 && n < offer.price ? n : null
}

function OfferCard({ offer, onChanged }: { offer: Offer; onChanged(): void }) {
  const { t } = useI18n()
  const { busy, error, run } = useAction()
  const [counter, setCounter] = useState('')
  const [showCounter, setShowCounter] = useState(false)
  const d = offer.driver
  const money = (n: number) => t('common.currency', { price: formatPrice(n) })

  const accept = async () => {
    const trip = await run(() => api.acceptOffer(offer.id))
    if (trip) {
      haptic('success')
      navigate(`/trip/${trip.id}`)
    } else haptic('error')
  }
  const sendCounter = async () => {
    const n = validCounter(counter, offer)
    if (n === null) return
    const r = await run(() => api.counterOffer(offer.id, n))
    if (r) {
      setShowCounter(false)
      setCounter('')
      onChanged()
    }
  }
  const countered = offer.status === 'countered' && offer.counter_price !== null

  return (
    <Card className="stack offer">
      <div className="offer-head">
        <strong className="price">{money(offer.price)}</strong>
        {d.verified ? (
          <Badge>
            <Icon name="check" size={14} /> {t('common.verified')}
          </Badge>
        ) : null}
      </div>
      <div>
        <div>{t('offers.driver', { name: d.first_name ?? '' })}</div>
        <div className="hint">
          {d.car_make}, {d.car_color}
        </div>
        <Rating value={d.rating} count={d.rating_count} />
      </div>
      {offer.message ? <p className="quote">{offer.message}</p> : null}
      {countered ? <p className="notice">{t('offers.countered', { price: formatPrice(offer.counter_price ?? 0) })}</p> : null}
      <Inline error={error} />
      <div className="actions">
        <Button onClick={() => void accept()} busy={busy}>
          {t('offers.accept')} · {money(offer.price)}
        </Button>
        {!countered ? (
          <Button variant="secondary" onClick={() => setShowCounter((s) => !s)} aria-expanded={showCounter}>
            {t('offers.counter')}
          </Button>
        ) : null}
      </div>
      {showCounter ? (
        <div className="counter">
          <input
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder={t('offers.counter_ph')}
            aria-label={t('offers.counter_ph')}
            value={counter}
            onChange={(e) => setCounter(e.target.value.replace(/\D/g, ''))}
          />
          <Button disabled={validCounter(counter, offer) === null} busy={busy} onClick={() => void sendCounter()}>
            {t('offers.counter_send')}
          </Button>
        </div>
      ) : null}
    </Card>
  )
}

export default function Offers({ id }: { id: number }) {
  const { t, lang } = useI18n()
  const state = useAsync(() => api.offers(id), [id], 5000) // live refresh while the passenger waits
  const { busy, error, run } = useAction()

  if (state.loading && !state.data) return <Spinner />
  if (state.error && !state.data) return <ErrorBox error={state.error} onRetry={state.reload} />
  if (!state.data) return null
  const { request: r, offers, trip_id } = state.data

  const cancel = async () => {
    if (!(await confirmDialog(t('offers.cancel_request') + '?'))) return
    if (await run(() => api.cancelRequest(r.id))) {
      state.reload()
      navigate('/')
    }
  }

  return (
    <div className="stack">
      <h1>{t('offers.title')}</h1>
      <Card>
        <strong>
          {r.from_text} → {r.to_text}
        </strong>
        <div className="hint">
          {r.depart_at ? formatDateTime(r.depart_at, lang) : t('home.asap')} · {t('common.seats', { n: r.seats })}
        </div>
        <Badge tone={r.status === 'open' ? 'brand' : r.status === 'matched' ? 'ok' : 'muted'}>{t(`req.status.${r.status}`)}</Badge>
        {r.price_hint ? <div className="hint">{t('home.price_hint', { price: t('common.currency', { price: formatPrice(r.price_hint) }) })}</div> : null}
      </Card>

      {trip_id ? (
        <a className="btn btn-primary" href={href(`/trip/${trip_id}`)}>
          {t('offers.open_trip')}
        </a>
      ) : null}

      {r.status === 'open' && offers.length === 0 ? (
        <div className="empty">
          <Mascot name="waiting" size={120} />
          <p>{t('offers.waiting')}</p>
        </div>
      ) : null}
      {r.status === 'open' && offers.length > 0 ? <p className="hint">{t('offers.how')}</p> : null}
      {r.status === 'open' ? offers.map((o) => <OfferCard key={o.id} offer={o} onChanged={state.reload} />) : null}
      {r.status === 'cancelled' || r.status === 'expired' ? <Empty text={t(`req.status.${r.status}`)} mascot="sad" /> : null}

      <Inline error={error} />
      {r.status === 'open' ? (
        <Button variant="danger" busy={busy} onClick={() => void cancel()}>
          {t('offers.cancel_request')}
        </Button>
      ) : null}
    </div>
  )
}
