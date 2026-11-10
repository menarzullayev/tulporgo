import { useState } from 'react'
import { api } from '../api'
import { Badge, Button, Card, ErrorBox, Icon, Inline, Mascot, Rating, Row, Spinner, StarInput } from '../components/ui'
import { formatDateTime, formatPrice, telHref, tgHref } from '../format'
import { useAction, useAsync } from '../hooks'
import { useI18n } from '../i18n'
import { confirmDialog, haptic, openTelegram, shareLink } from '../tg'
import type { Trip as TripT } from '../types'
import { tripTone } from './Trips'

/** Which actions a participant may take, mirroring the rules enforced by the API (the server stays the authority). */
export function tripActions(trip: Pick<TripT, 'status' | 'role' | 'rated'>) {
  const live = trip.status === 'confirmed' || trip.status === 'started'
  return {
    start: trip.role === 'driver' && trip.status === 'confirmed',
    complete: live,
    cancel: trip.status === 'confirmed',
    rate: trip.status === 'completed' && !trip.rated,
    share: trip.role === 'passenger' && trip.status !== 'cancelled',
  }
}

export default function Trip({ id }: { id: number }) {
  const { t, lang } = useI18n()
  const state = useAsync(() => api.trip(id), [id], 10000)
  const { busy, error, run } = useAction()
  const [stars, setStars] = useState(0)
  const [comment, setComment] = useState('')
  const [copied, setCopied] = useState(false)

  if (state.loading && !state.data) return <Spinner />
  if (state.error && !state.data) return <ErrorBox error={state.error} onRetry={state.reload} />
  if (!state.data) return null
  const trip = state.data
  const can = tripActions(trip)
  const money = t('common.currency', { price: formatPrice(trip.price) })
  const route = `${trip.from_text} → ${trip.to_text}`
  const tel = telHref(trip.counterparty.phone)
  const tg = tgHref(trip.counterparty.username)

  const act = async (fn: () => Promise<unknown>) => {
    if (await run(fn)) {
      haptic('success')
      state.reload()
    } else haptic('error')
  }
  const cancel = async () => {
    if (await confirmDialog(t('trip.confirm_cancel'))) await act(() => api.cancelTrip(id))
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(trip.share_url)
      setCopied(true)
    } catch {
      /* clipboard can be blocked inside some webviews; the share button still works */
    }
  }

  return (
    <div className="stack">
      <h1>{t('trip.title')}</h1>
      <Card className="stack">
        <div className="offer-head">
          <strong>{route}</strong>
          <Badge tone={tripTone(trip.status)}>{t(`trip.status.${trip.status}`)}</Badge>
        </div>
        <Row label={t('home.when')}>{trip.depart_at ? formatDateTime(trip.depart_at, lang) : t('home.asap')}</Row>
        <Row label={t('trip.price')}>
          <strong>{money}</strong>
        </Row>
        <Row label={t('home.seats')}>{trip.seats}</Row>
        <Row label={t('trip.car')}>
          {trip.car.make}, {trip.car.color}
        </Row>
        <Row label={t('trip.plate')}>
          <span className="plate">{trip.car.plate}</span>
        </Row>
        <Row label={trip.role === 'passenger' ? t('trip.driver') : t('trip.passenger')}>
          {trip.counterparty.first_name ?? '—'}
          {trip.role === 'passenger' ? (
            <>
              {' '}
              <Rating value={trip.driver_rating} />
              {trip.driver_verified ? (
                <>
                  {' '}
                  <Badge>
                    <Icon name="check" size={14} /> {t('common.verified')}
                  </Badge>
                </>
              ) : null}
            </>
          ) : null}
        </Row>
        {tel || tg ? (
          <div className="actions">
            {tel ? (
              <a className="btn btn-secondary" href={tel}>
                {t('trip.call')}
              </a>
            ) : null}
            {tg ? (
              <Button variant="secondary" onClick={() => openTelegram(tg)}>
                {t('trip.message')}
              </Button>
            ) : null}
          </div>
        ) : null}
      </Card>

      <Inline error={error} />

      {can.share ? (
        <Card className="stack">
          <p className="hint">{t('trip.share_hint')}</p>
          <div className="actions">
            <Button onClick={() => shareLink(trip.share_url, t('trip.share_text', { route }))}>{t('trip.share')}</Button>
            <Button variant="secondary" onClick={() => void copy()}>
              {copied ? t('common.copied') : t('common.copy')}
            </Button>
          </div>
        </Card>
      ) : null}

      {can.start ? (
        <Button busy={busy} onClick={() => void act(() => api.startTrip(id))}>
          {t('trip.start')}
        </Button>
      ) : null}
      {can.complete ? (
        <Button busy={busy} onClick={() => void act(() => api.completeTrip(id))}>
          {t('trip.complete')}
        </Button>
      ) : null}
      {can.cancel ? (
        <Button variant="danger" busy={busy} onClick={() => void cancel()}>
          {t('trip.cancel')}
        </Button>
      ) : null}

      {can.rate ? (
        <Card className="stack">
          <h2>{t('trip.rate_title')}</h2>
          <StarInput value={stars} onChange={setStars} />
          <label className="field">
            <span className="field-label">{t('trip.rate_comment')}</span>
            <textarea rows={2} maxLength={512} value={comment} onChange={(e) => setComment(e.target.value)} />
          </label>
          <Button disabled={stars === 0} busy={busy} onClick={() => void act(() => api.rateTrip(id, stars, comment))}>
            {t('trip.rate_send')}
          </Button>
        </Card>
      ) : null}
      {trip.status === 'completed' && trip.rated ? (
        <div className="empty">
          <Mascot name="thumbs" size={110} />
          <p>{t('trip.rated')}</p>
        </div>
      ) : null}
    </div>
  )
}
