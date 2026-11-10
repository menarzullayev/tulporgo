import { useCallback, useState } from 'react'
import { api } from '../api'
import { useMe } from '../app-context'
import { emptyPlace, PlaceField, type PlaceValue } from '../components/PlaceField'
import { PrimaryAction } from '../components/PrimaryAction'
import { Button, Card, Empty, Inline, Icon, Field, Badge } from '../components/ui'
import { departAtForApi, formatDateTime, formatPrice, tashkentNowInput } from '../format'
import { useAction, useAsync } from '../hooks'
import { useI18n } from '../i18n'
import { href, navigate } from '../router'
import { haptic } from '../tg'
import type { CreateRequestBody } from '../types'

export type FormState = {
  from: PlaceValue
  to: PlaceValue
  later: boolean
  when: string
  seats: number
  note: string
}

export const initialForm: FormState = { from: emptyPlace, to: emptyPlace, later: false, when: '', seats: 1, note: '' }

/** Form -> API body, or the i18n key of what is wrong. Pure, so it is unit-tested. */
export function buildRequest(f: FormState, now: number = Date.now()): { body: CreateRequestBody } | { problem: string } {
  const from = f.from.text.trim()
  const to = f.to.text.trim()
  if (!from || !to) return { problem: 'err.route_required' }
  if (f.from.id !== null && f.from.id === f.to.id) return { problem: 'err.same_place' }
  if (f.seats < 1 || f.seats > 8) return { problem: 'err.bad_seats' }
  let depart: string | null = null
  if (f.later) {
    depart = departAtForApi(f.when)
    if (!depart || depart < tashkentNowInput(now - 10 * 60 * 1000)) return { problem: 'err.depart_in_past' }
  }
  return {
    body: {
      from_place_id: f.from.id,
      to_place_id: f.to.id,
      from_text: from,
      to_text: to,
      depart_at: depart,
      seats: f.seats,
      note: f.note.trim() || null,
    },
  }
}

export default function Home() {
  const { t, err, lang } = useI18n()
  const { me } = useMe()
  const [form, setForm] = useState<FormState>(initialForm)
  const [problem, setProblem] = useState<string>()
  const { busy, error, run, clear } = useAction()
  const mine = useAsync(() => api.myRequests(), [], 15000)
  const set = (patch: Partial<FormState>) => {
    setForm((f) => ({ ...f, ...patch }))
    setProblem(undefined)
    clear()
  }

  const submit = useCallback(async () => {
    const built = buildRequest(form)
    if ('problem' in built) {
      setProblem(built.problem)
      haptic('error')
      return
    }
    const r = await run(() => api.createRequest(built.body))
    if (r) {
      haptic('success')
      setForm(initialForm)
      navigate(`/offers/${r.id}`)
    } else haptic('error')
  }, [form, run])

  const open = (mine.data?.items ?? []).filter((r) => r.status === 'open' || r.status === 'matched').slice(0, 4)

  return (
    <div className="stack">
      <h1>{t('home.title')}</h1>
      <Card className="stack">
        <PlaceField label={t('home.from')} value={form.from} onChange={(from) => set({ from })} />
        <button type="button" className="swap" onClick={() => set({ from: form.to, to: form.from })} aria-label={t('home.swap')}>
          ⇅
        </button>
        <PlaceField label={t('home.to')} value={form.to} onChange={(to) => set({ to })} />

        <fieldset className="field">
          <legend className="field-label">{t('home.when')}</legend>
          <div className="seg" role="radiogroup">
            <button type="button" role="radio" aria-checked={!form.later} className={!form.later ? 'on' : ''} onClick={() => set({ later: false })}>
              {t('home.when_now')}
            </button>
            <button type="button" role="radio" aria-checked={form.later} className={form.later ? 'on' : ''} onClick={() => set({ later: true })}>
              {t('home.when_later')}
            </button>
          </div>
          {form.later ? (
            <input
              type="datetime-local"
              aria-label={t('home.when_later')}
              value={form.when}
              min={tashkentNowInput()}
              onChange={(e) => set({ when: e.target.value })}
            />
          ) : null}
        </fieldset>

        <div className="field" role="group" aria-label={t('home.seats')}>
          <span className="field-label">{t('home.seats')}</span>
          <div className="stepper">
            <Button variant="secondary" aria-label="-" disabled={form.seats <= 1} onClick={() => set({ seats: form.seats - 1 })}>
              −
            </Button>
            <output aria-live="polite">{form.seats}</output>
            <Button variant="secondary" aria-label="+" disabled={form.seats >= 8} onClick={() => set({ seats: form.seats + 1 })}>
              +
            </Button>
          </div>
        </div>

        <Field label={t('home.note')}>
          <textarea rows={2} maxLength={256} value={form.note} placeholder={t('home.note_ph')} onChange={(e) => set({ note: e.target.value })} />
        </Field>

        {me.is_woman ? (
          <p className="notice" data-testid="women-marker">
            <Icon name="shield" size={20} /> {t('home.women_marker')}
          </p>
        ) : null}

        {problem ? (
          <p className="error-inline" role="alert">
            {err(problem.replace(/^err\./, ''))}
          </p>
        ) : null}
        <Inline error={error} />
        <PrimaryAction text={t('home.submit')} onClick={() => void submit()} busy={busy} />
      </Card>

      <h2>{t('home.my_requests')}</h2>
      {open.length === 0 ? (
        <Empty text={t('common.empty')} mascot="hello" />
      ) : (
        <ul className="list">
          {open.map((r) => (
            <li key={r.id}>
              <a className="card link" href={href(r.status === 'matched' ? '/trips' : `/offers/${r.id}`)}>
                <strong>
                  {r.from_text} → {r.to_text}
                </strong>
                <span className="hint">
                  {r.depart_at ? formatDateTime(r.depart_at, lang) : t('home.asap')}
                  {r.price_hint ? ` · ${t('home.price_hint', { price: t('common.currency', { price: formatPrice(r.price_hint) }) })}` : ''}
                </span>
                {r.status === 'open' ? <Badge>{t('home.offers_count', { n: r.offers_count })}</Badge> : <Badge tone="ok">{t(`req.status.${r.status}`)}</Badge>}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
