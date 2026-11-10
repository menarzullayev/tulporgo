// Map pick: OpenStreetMap tiles through Leaflet (no API key). A tap is snapped to the nearest known place by the API;
// when none is close enough (or the place table has no coordinates yet) the point is kept as a labelled coordinate.
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useI18n } from '../i18n'
import { haptic } from '../tg'
import { Button } from './ui'
import type { PlaceValue } from './PlaceField'

const SAMARQAND: [number, number] = [39.6542, 66.9597]

export default function MapPicker({ onPick, onClose }: { onPick(v: PlaceValue): void; onClose(): void }) {
  const { t } = useI18n()
  const host = useRef<HTMLDivElement>(null)
  const [point, setPoint] = useState<{ lat: number; lon: number } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!host.current) return
    const map = L.map(host.current, { zoomControl: true }).setView(SAMARQAND, 11)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map)
    let marker: L.CircleMarker | undefined
    map.on('click', (e: L.LeafletMouseEvent) => {
      const { lat, lng } = e.latlng
      marker?.remove()
      marker = L.circleMarker(e.latlng, { radius: 9, color: '#111214', weight: 3, fillColor: '#FFC72C', fillOpacity: 1 }).addTo(map)
      setPoint({ lat, lon: lng })
      haptic('select')
    })
    return () => {
      map.remove()
    }
  }, [])

  const confirm = async () => {
    if (!point) return
    setBusy(true)
    try {
      const r = await api.nearestPlace(point.lat, point.lon)
      onPick({ id: r.item.id, text: r.item.name })
    } catch {
      onPick({ id: null, text: `${t('map.point')} (${point.lat.toFixed(4)}, ${point.lon.toFixed(4)})` })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label={t('map.title')}>
      <div className="modal-bar">
        <strong>{t('map.title')}</strong>
        <Button variant="ghost" onClick={onClose}>
          {t('common.close')}
        </Button>
      </div>
      <div ref={host} className="map" data-testid="map" />
      <div className="modal-foot">
        <p className="hint">{t('map.hint')}</p>
        <Button disabled={!point} busy={busy} onClick={() => void confirm()}>
          {t('map.confirm')}
        </Button>
      </div>
    </div>
  )
}
