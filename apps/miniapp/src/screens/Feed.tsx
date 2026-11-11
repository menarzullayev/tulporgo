// Group feed filters (decision 73): the driver decides which requests from his taxi groups reach him as cards.
// Server contract and limits: apps/userbot/tulporgo_userbot/feedapi.py. The client checks mirror the server so a
// mistake is shown at once; the server stays the authority and its error codes are shown with their own texts.
import { useEffect, useState } from 'react'
import { api } from '../api'
import { emptyPlace, PlaceField, type PlaceValue } from '../components/PlaceField'
import { PrimaryAction } from '../components/PrimaryAction'
import { Button, Card, Empty, ErrorBox, Field, Inline, Spinner } from '../components/ui'
import { useAction, useAsync } from '../hooks'
import { useI18n } from '../i18n'
import { href } from '../router'
import { haptic } from '../tg'
import { FEED_KINDS, type FeedFilter, type FeedFilterBody, type FeedKind, type FeedState } from '../types'

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/
const MAX_ROUTES = 10
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]
const SEATS = [1, 2, 3, 4, 5, 6, 7, 8]

export interface RouteForm {
  from: PlaceValue
  to: PlaceValue
  on_way: boolean
}

export interface FilterForm {
  name: string
  enabled: boolean
  routes: RouteForm[]
  time_from: string
  time_to: string
  include_asap: boolean
  include_tomorrow: boolean
  weekdays: number[]
  seats_min: string
  seats_max: string
  kinds: FeedKind[]
  allGroups: boolean
  groups: number[]
}

export const emptyRoute = (): RouteForm => ({ from: emptyPlace, to: emptyPlace, on_way: false })

export const emptyForm = (): FilterForm => ({
  name: '',
  enabled: true,
  routes: [emptyRoute()],
  time_from: '',
  time_to: '',
  include_asap: true,
  include_tomorrow: true,
  weekdays: [],
  seats_min: '',
  seats_max: '',
  kinds: [],
  allGroups: true,
  groups: [],
})

export function formFromFilter(f: FeedFilter, state: Pick<FeedState, 'groups'>): FilterForm {
  const mine = new Set(state.groups.map((g) => g.chat_id))
  return {
    name: f.name,
    enabled: f.enabled,
    routes: f.routes.length
      ? f.routes.map((r) => ({
          from: r.from ? { id: r.from.id, text: r.from.name } : emptyPlace,
          to: r.to ? { id: r.to.id, text: r.to.name } : emptyPlace,
          on_way: r.on_way,
        }))
      : [emptyRoute()],
    time_from: f.time_from ?? '',
    time_to: f.time_to ?? '',
    include_asap: f.include_asap,
    include_tomorrow: f.include_tomorrow,
    weekdays: [...f.weekdays],
    seats_min: f.seats_min ? String(f.seats_min) : '',
    seats_max: f.seats_max ? String(f.seats_max) : '',
    kinds: [...f.kinds],
    allGroups: f.group_chat_ids.length === 0,
    groups: f.group_chat_ids.filter((id) => mine.has(id)), // a group he left is dropped, never sent back
  }
}

/** A stored filter -> the PUT body (used by the on/off switch: the same filter, only `enabled` changes). */
export const bodyFromFilter = (f: FeedFilter, enabled: boolean = f.enabled): FeedFilterBody => ({
  name: f.name,
  enabled,
  routes: f.routes.map((r) => ({ from: r.from?.id ?? null, to: r.to?.id ?? null, on_way: r.on_way })),
  time_from: f.time_from,
  time_to: f.time_to,
  include_asap: f.include_asap,
  include_tomorrow: f.include_tomorrow,
  weekdays: f.weekdays,
  seats_min: f.seats_min,
  seats_max: f.seats_max,
  kinds: f.kinds,
  group_chat_ids: f.group_chat_ids,
})

/** Form -> API body, or the i18n key of what is wrong. Pure, so it is unit-tested. */
export function buildFilterBody(f: FilterForm): { body: FeedFilterBody } | { problem: string } {
  const name = f.name.trim()
  if (!name) return { problem: 'feed.err_name' }
  if (f.routes.length === 0) return { problem: 'err.empty_route' }
  const routes = []
  for (const r of f.routes) {
    const sides = [r.from, r.to].map((p) => ({ id: p.id, text: p.text.trim() }))
    if (sides.some((s) => s.text && s.id === null)) return { problem: 'err.unknown_place' } // typed, never picked
    const [from, to] = sides.map((s) => (s.text ? s.id : null))
    if (from === null && to === null) return { problem: 'err.empty_route' }
    routes.push({ from, to, on_way: r.on_way })
  }
  for (const v of [f.time_from, f.time_to]) if (v && !HHMM.test(v)) return { problem: 'err.bad_time' }
  const min = f.seats_min ? Number(f.seats_min) : null
  const max = f.seats_max ? Number(f.seats_max) : null
  for (const n of [min, max]) if (n !== null && !(Number.isInteger(n) && n >= 1 && n <= 8)) return { problem: 'err.bad_seats' }
  if (min !== null && max !== null && min > max) return { problem: 'err.bad_seats' }
  if (!f.allGroups && f.groups.length === 0) return { problem: 'feed.err_group' }
  return {
    body: {
      name,
      enabled: f.enabled,
      routes,
      time_from: f.time_from || null,
      time_to: f.time_to || null,
      include_asap: f.include_asap,
      include_tomorrow: f.include_tomorrow,
      weekdays: [...f.weekdays].sort(),
      seats_min: min,
      seats_max: max,
      kinds: FEED_KINDS.filter((k) => f.kinds.includes(k)),
      group_chat_ids: f.allGroups ? [] : [...f.groups],
    },
  }
}

const toggle = <T,>(list: T[], v: T): T[] => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

function Summary({ f }: { f: FeedFilter }) {
  const { t } = useI18n()
  const any = t('feed.any_place')
  const time =
    f.time_from && f.time_to
      ? `${f.time_from}–${f.time_to}`
      : f.time_from
        ? t('feed.time_from_only', { t: f.time_from })
        : f.time_to
          ? t('feed.time_to_only', { t: f.time_to })
          : t('feed.time_any')
  let seats = ''
  if (f.seats_min && f.seats_max) seats = f.seats_min === f.seats_max ? String(f.seats_min) : `${f.seats_min}–${f.seats_max}`
  else if (f.seats_min) seats = `${f.seats_min}+`
  else if (f.seats_max) seats = `≤${f.seats_max}`
  const parts = [
    time,
    f.include_asap ? t('feed.sum_asap') : '',
    f.include_tomorrow ? t('feed.sum_tomorrow') : '',
    f.weekdays.length ? f.weekdays.map((d) => t(`feed.wd.${d}`)).join(' ') : t('feed.every_day'),
    seats ? t('feed.seats_label', { range: seats }) : '',
    f.kinds.length ? f.kinds.map((k) => t(`feed.kind.${k}`)).join(', ') : t('feed.all_kinds'),
    f.group_chat_ids.length ? t('feed.groups_n', { n: f.group_chat_ids.length }) : t('feed.all_groups'),
  ].filter(Boolean)
  return (
    <>
      <ul className="list">
        {f.routes.map((r, i) => (
          <li key={i}>
            {r.from?.name ?? any} → {r.to?.name ?? any}
            {r.on_way ? <span className="hint"> ({t('feed.on_way_tag')})</span> : null}
          </li>
        ))}
      </ul>
      <p className="hint">{parts.join(' · ')}</p>
    </>
  )
}

function Chips<T extends string | number>({
  label,
  hint,
  items,
  picked,
  text,
  onToggle,
}: {
  label: string
  hint: string
  items: readonly T[]
  picked: T[]
  text(v: T): string
  onToggle(v: T): void
}) {
  return (
    <div className="field" role="group" aria-label={label}>
      <span className="field-label">{label}</span>
      <div className="seg seg-wrap">
        {items.map((v) => {
          const on = picked.includes(v)
          return (
            <button key={v} type="button" aria-pressed={on} className={on ? 'on' : ''} onClick={() => onToggle(v)}>
              {text(v)}
            </button>
          )
        })}
      </div>
      <span className="hint">{hint}</span>
    </div>
  )
}

function Editor({ state, filter, onSaved, onCancel }: { state: FeedState; filter: FeedFilter | null; onSaved(f: FeedFilter): void; onCancel(): void }) {
  const { t } = useI18n()
  const [form, setForm] = useState<FilterForm>(() => (filter ? formFromFilter(filter, state) : emptyForm()))
  const [problem, setProblem] = useState<string>()
  const { busy, error, run, clear } = useAction()
  const set = (patch: Partial<FilterForm>) => {
    setForm((f) => ({ ...f, ...patch }))
    setProblem(undefined)
    clear()
  }
  const setRoute = (i: number, patch: Partial<RouteForm>) => set({ routes: form.routes.map((r, j) => (j === i ? { ...r, ...patch } : r)) })

  const save = async () => {
    const built = buildFilterBody(form)
    if ('problem' in built) {
      setProblem(built.problem)
      haptic('error')
      return
    }
    const saved = await run(() => (filter ? api.feedUpdate(filter.id, built.body) : api.feedCreate(built.body)))
    if (saved) {
      haptic('success')
      onSaved(saved)
    } else haptic('error')
  }

  return (
    <div className="stack">
      <h1>{filter ? t('feed.editor_edit') : t('feed.editor_new')}</h1>
      <Card className="stack">
        <Field label={t('feed.name')}>
          <input type="text" maxLength={64} value={form.name} placeholder={t('feed.name_ph')} onChange={(e) => set({ name: e.target.value })} />
        </Field>
      </Card>

      <Card className="stack">
        <h2>{t('feed.routes')}</h2>
        <p className="hint">{t('feed.routes_hint')}</p>
        {form.routes.map((r, i) => (
          <div key={i} className="route-box stack" role="group" aria-label={t('feed.route_n', { n: i + 1 })}>
            <strong>{t('feed.route_n', { n: i + 1 })}</strong>
            <PlaceField label={t('home.from')} value={r.from} onChange={(from) => setRoute(i, { from })} />
            <PlaceField label={t('home.to')} value={r.to} onChange={(to) => setRoute(i, { to })} />
            <label className="switch">
              <input type="checkbox" checked={r.on_way} onChange={(e) => setRoute(i, { on_way: e.target.checked })} />
              <span>{t('feed.on_way')}</span>
            </label>
            <div className="actions">
              <Button
                variant="secondary"
                disabled={form.routes.length >= MAX_ROUTES || (!r.from.text.trim() && !r.to.text.trim())}
                onClick={() => set({ routes: [...form.routes, { from: r.to, to: r.from, on_way: r.on_way }] })}
              >
                {t('feed.add_reverse')}
              </Button>
              {form.routes.length > 1 ? (
                <Button variant="ghost" aria-label={`${t('feed.remove_route')}: ${t('feed.route_n', { n: i + 1 })}`} onClick={() => set({ routes: form.routes.filter((_, j) => j !== i) })}>
                  {t('feed.remove_route')}
                </Button>
              ) : null}
            </div>
          </div>
        ))}
        <Button variant="secondary" disabled={form.routes.length >= MAX_ROUTES} onClick={() => set({ routes: [...form.routes, emptyRoute()] })}>
          {t('feed.add_route')}
        </Button>
      </Card>

      <Card className="stack">
        <h2>{t('feed.time')}</h2>
        <div className="actions">
          <Field label={t('feed.time_from')}>
            <input type="time" value={form.time_from} onChange={(e) => set({ time_from: e.target.value })} />
          </Field>
          <Field label={t('feed.time_to')}>
            <input type="time" value={form.time_to} onChange={(e) => set({ time_to: e.target.value })} />
          </Field>
        </div>
        <p className="hint">{t('feed.time_hint')}</p>
        <label className="switch">
          <input type="checkbox" role="switch" checked={form.include_asap} onChange={(e) => set({ include_asap: e.target.checked })} />
          <span>{t('feed.include_asap')}</span>
        </label>
        <label className="switch">
          <input type="checkbox" role="switch" checked={form.include_tomorrow} onChange={(e) => set({ include_tomorrow: e.target.checked })} />
          <span>{t('feed.include_tomorrow')}</span>
        </label>
        <Chips label={t('feed.weekdays')} hint={t('feed.weekdays_hint')} items={WEEKDAYS} picked={form.weekdays} text={(d) => t(`feed.wd.${d}`)} onToggle={(d) => set({ weekdays: toggle(form.weekdays, d) })} />
      </Card>

      <Card className="stack">
        <div className="actions">
          <Field label={t('feed.seats_min')}>
            <select value={form.seats_min} onChange={(e) => set({ seats_min: e.target.value })}>
              <option value="">{t('feed.seats_any')}</option>
              {SEATS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('feed.seats_max')}>
            <select value={form.seats_max} onChange={(e) => set({ seats_max: e.target.value })}>
              <option value="">{t('feed.seats_any')}</option>
              {SEATS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Chips label={t('feed.kinds')} hint={t('feed.kinds_hint')} items={FEED_KINDS} picked={form.kinds} text={(k) => t(`feed.kind.${k}`)} onToggle={(k) => set({ kinds: toggle(form.kinds, k) })} />
      </Card>

      <Card className="stack">
        <h2>{t('feed.groups')}</h2>
        <div className="seg" role="radiogroup" aria-label={t('feed.groups')}>
          <button type="button" role="radio" aria-checked={form.allGroups} className={form.allGroups ? 'on' : ''} onClick={() => set({ allGroups: true })}>
            {t('feed.groups_all')}
          </button>
          <button type="button" role="radio" aria-checked={!form.allGroups} className={!form.allGroups ? 'on' : ''} onClick={() => set({ allGroups: false })}>
            {t('feed.groups_chosen')}
          </button>
        </div>
        {!form.allGroups ? (
          state.groups.length ? (
            <ul className="list">
              {state.groups.map((g) => (
                <li key={g.chat_id}>
                  <label className="switch">
                    <input type="checkbox" checked={form.groups.includes(g.chat_id)} onChange={() => set({ groups: toggle(form.groups, g.chat_id) })} />
                    <span>{g.title}</span>
                  </label>
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint">{t('feed.no_groups')}</p>
          )
        ) : null}
      </Card>

      {problem ? (
        <p className="error-inline" role="alert">
          {t(problem)}
        </p>
      ) : null}
      <Inline error={error} />
      <PrimaryAction text={t('feed.save')} onClick={() => void save()} busy={busy} />
      <Button variant="ghost" onClick={onCancel}>
        {t('feed.cancel')}
      </Button>
    </div>
  )
}

export default function Feed() {
  const { t } = useI18n()
  const load = useAsync(() => api.feed(), [])
  const [state, setState] = useState<FeedState>()
  const [editing, setEditing] = useState<FeedFilter | 'new' | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const { busy, error, run, clear } = useAction()

  useEffect(() => {
    if (load.data) setState(load.data)
  }, [load.data])

  if (!state) return load.error ? <ErrorBox error={load.error} onRetry={load.reload} /> : <Spinner />

  const replace = (f: FeedFilter) =>
    setState((s) => (s ? { ...s, filters: s.filters.some((x) => x.id === f.id) ? s.filters.map((x) => (x.id === f.id ? f : x)) : [...s.filters, f] } : s))

  if (editing)
    return (
      <Editor
        state={state}
        filter={editing === 'new' ? null : editing}
        onCancel={() => setEditing(null)}
        onSaved={(f) => {
          replace(f)
          setEditing(null)
        }}
      />
    )

  const pause = async () => {
    const next = await run(() => api.feedPause(!state.paused))
    if (next) setState(next)
  }
  const flip = async (f: FeedFilter) => {
    const saved = await run(() => api.feedUpdate(f.id, bodyFromFilter(f, !f.enabled)))
    if (saved) replace(saved)
    else load.reload() // e.g. filter_not_found: show what the server has now
  }
  const remove = async (f: FeedFilter) => {
    const r = await run(() => api.feedDelete(f.id))
    setConfirmId(null)
    if (r) setState((s) => (s ? { ...s, filters: s.filters.filter((x) => x.id !== f.id) } : s))
    else load.reload()
  }
  const full = state.filters.length >= state.max_filters

  return (
    <div className="stack">
      <h1>{t('feed.title')}</h1>

      <Card className="stack">
        <label className="switch">
          <input type="checkbox" role="switch" checked={state.paused} disabled={busy} onChange={() => void pause()} />
          <span>
            <strong>{t('feed.pause_title')}</strong>
            <span className="hint block">{t('feed.pause_hint')}</span>
          </span>
        </label>
        <p className="hint">{state.delivery_linked ? t('feed.dest_channel') : t('feed.dest_bot')}</p>
        {!state.connected ? (
          <>
            <p className="notice">{t('feed.not_connected')}</p>
            <a className="btn btn-secondary" href={href('/userbot/login')}>
              {t('profile.userbot_open')}
            </a>
          </>
        ) : null}
        {state.connected && !state.consent_ok ? <p className="notice">{t('feed.consent_needed')}</p> : null}
        {state.connected && state.groups.length === 0 ? <p className="hint">{t('feed.no_groups')}</p> : null}
        <Inline error={error} />
      </Card>

      <h2>{t('feed.filters')}</h2>
      {state.filters.length === 0 ? <Empty text={t('feed.empty')} /> : null}
      <ul className="list">
        {state.filters.map((f) => (
          <li key={f.id}>
            <Card className={`stack${f.enabled ? '' : ' filter-off'}`}>
              <div className="filter-head">
                <strong>{f.name}</strong>
                <input type="checkbox" role="switch" aria-label={t('feed.toggle_aria', { name: f.name })} checked={f.enabled} disabled={busy} onChange={() => void flip(f)} />
              </div>
              <Summary f={f} />
              {confirmId === f.id ? (
                <div className="stack" role="alertdialog" aria-label={t('feed.delete_confirm', { name: f.name })}>
                  <p>{t('feed.delete_confirm', { name: f.name })}</p>
                  <div className="actions">
                    <Button variant="danger" busy={busy} onClick={() => void remove(f)}>
                      {t('feed.delete_yes')}
                    </Button>
                    <Button variant="secondary" onClick={() => setConfirmId(null)}>
                      {t('feed.cancel')}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="actions">
                  <Button variant="secondary" onClick={() => { clear(); setEditing(f) }}>
                    {t('feed.edit')}
                  </Button>
                  <Button variant="ghost" aria-label={`${t('feed.delete')}: ${f.name}`} onClick={() => { clear(); setConfirmId(f.id) }}>
                    {t('feed.delete')}
                  </Button>
                </div>
              )}
            </Card>
          </li>
        ))}
      </ul>

      {full ? <p className="hint">{t('feed.limit', { n: state.max_filters })}</p> : null}
      <Button disabled={full} onClick={() => { clear(); setEditing('new') }}>
        {t('feed.add')}
      </Button>
    </div>
  )
}
