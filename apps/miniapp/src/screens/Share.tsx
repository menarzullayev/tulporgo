// Public trip status page for relatives (decision 13): no sign-in, no Telegram needed.
// It only ever shows what GET /api/share/{token} returns: route, time, status, car and the driver's first name.
import { api } from '../api'
import { Badge, Card, Empty, ErrorBox, Mascot, Row, Spinner } from '../components/ui'
import { formatDateTime } from '../format'
import { useAsync } from '../hooks'
import { useI18n } from '../i18n'
import { tripTone } from './Trips'

export default function Share({ token }: { token: string }) {
  const { t, lang } = useI18n()
  const state = useAsync(() => api.shared(token), [token], 15000)

  let body
  if (state.loading && !state.data) body = <Spinner />
  else if (state.error && !state.data)
    body = state.error.status === 404 ? <Empty text={t('share.not_found')} mascot="sad" /> : <ErrorBox error={state.error} onRetry={state.reload} />
  else if (state.data) {
    const s = state.data
    body = (
      <>
        <Card className="stack">
          <div className="offer-head">
            <strong>
              {s.from} → {s.to}
            </strong>
            <Badge tone={tripTone(s.status)}>{t(`trip.status.${s.status}`)}</Badge>
          </div>
          {s.depart_at ? <Row label={t('home.when')}>{formatDateTime(s.depart_at, lang)}</Row> : null}
          <Row label={t('share.driver')}>{s.driver_first_name ?? '—'}</Row>
          <Row label={t('trip.car')}>
            {s.car.make}, {s.car.color}
          </Row>
          <Row label={t('trip.plate')}>
            <span className="plate">{s.car.plate}</span>
          </Row>
        </Card>
        {s.finished ? <p className="notice">{t('share.finished')}</p> : null}
        <p className="hint">{t('share.note')}</p>
      </>
    )
  }

  return (
    <div className="stack share">
      <header className="brandbar">
        <Mascot name="driving" size={64} />
        <span className="wordmark">TULPORGO</span>
      </header>
      <h1>{t('share.title')}</h1>
      {body}
    </div>
  )
}
