import { api } from '../api'
import { Badge, Empty, ErrorBox, Spinner } from '../components/ui'
import { formatDateTime, formatPrice } from '../format'
import { useAsync } from '../hooks'
import { useI18n } from '../i18n'
import { href } from '../router'
import type { Trip } from '../types'

export const tripTone = (s: Trip['status']) => (s === 'completed' ? 'ok' : s === 'cancelled' ? 'bad' : 'brand')

export default function Trips() {
  const { t, lang } = useI18n()
  const state = useAsync(() => api.myTrips(), [], 15000)
  if (state.loading && !state.data) return <Spinner />
  if (state.error && !state.data) return <ErrorBox error={state.error} onRetry={state.reload} />
  const items = state.data?.items ?? []
  return (
    <div className="stack">
      <h1>{t('trips.title')}</h1>
      {items.length === 0 ? (
        <Empty text={t('common.empty')} mascot="driving" />
      ) : (
        <ul className="list">
          {items.map((trip) => (
            <li key={trip.id}>
              <a className="card link" href={href(`/trip/${trip.id}`)}>
                <strong>
                  {trip.from_text} → {trip.to_text}
                </strong>
                <span className="hint">
                  {trip.depart_at ? formatDateTime(trip.depart_at, lang) : formatDateTime(trip.created_at, lang)} ·{' '}
                  {t('common.currency', { price: formatPrice(trip.price) })}
                </span>
                <span className="hint">{t(`trip.role.${trip.role}`)}</span>
                <Badge tone={tripTone(trip.status)}>{t(`trip.status.${trip.status}`)}</Badge>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
