import { lazy, Suspense, useEffect, useId, useState } from 'react'
import { api } from '../api'
import { useDebounced } from '../hooks'
import { useI18n } from '../i18n'
import { haptic } from '../tg'
import type { PlaceItem } from '../types'
import { Icon, Spinner } from './ui'

const MapPicker = lazy(() => import('./MapPicker')) // Leaflet only loads when someone opens the map

export interface PlaceValue {
  id: number | null
  text: string
}
export const emptyPlace: PlaceValue = { id: null, text: '' }

interface Props {
  label: string
  value: PlaceValue
  onChange(v: PlaceValue): void
}

export function PlaceField({ label, value, onChange }: Props) {
  const { t } = useI18n()
  const listId = useId()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<PlaceItem[]>([])
  const [mapOpen, setMapOpen] = useState(false)
  const query = useDebounced(value.id === null ? value.text.trim() : '', 200)

  useEffect(() => {
    if (!open || value.id !== null) return
    const ctrl = new AbortController()
    api
      .searchPlaces(query, ctrl.signal)
      .then((r) => setItems(r.items))
      .catch(() => undefined) // suggestions are a convenience; the typed text still works
    return () => ctrl.abort()
  }, [query, open, value.id])

  const pick = (p: PlaceItem) => {
    onChange({ id: p.id, text: p.name })
    setOpen(false)
    haptic('select')
  }

  return (
    <div className="place-field">
      <label className="field">
        <span className="field-label">{label}</span>
        <span className="input-row">
          <input
            type="text"
            value={value.text}
            maxLength={128}
            autoComplete="off"
            placeholder={t('home.search_hint')}
            role="combobox"
            aria-expanded={open && items.length > 0}
            aria-controls={listId}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 120)}
            onChange={(e) => onChange({ id: null, text: e.target.value })}
          />
          <button type="button" className="icon-btn" aria-label={t('home.pick_map')} onClick={() => setMapOpen(true)}>
            <Icon name="pin" size={28} />
          </button>
        </span>
      </label>
      {open && value.id === null && items.length > 0 ? (
        <ul className="suggest" role="listbox" id={listId}>
          {items.map((p) => (
            <li key={p.id} role="option" aria-selected={false} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(p)}>
              <span>{p.name}</span>
              {p.parent ? <span className="hint">{p.parent}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {mapOpen ? (
        <Suspense fallback={<Spinner />}>
          <MapPicker
            onClose={() => setMapOpen(false)}
            onPick={(v) => {
              onChange(v)
              setMapOpen(false)
            }}
          />
        </Suspense>
      ) : null}
    </div>
  )
}
