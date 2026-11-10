import { useState } from 'react'
import { api } from '../api'
import { useMe } from '../app-context'
import { Button, Card, Field, Inline } from '../components/ui'
import { useAction } from '../hooks'
import { prepareImage, tooLarge } from '../imageUtil'
import { useI18n } from '../i18n'
import { haptic } from '../tg'
import type { DriverBody } from '../types'

/** Client-side checks that mirror the API, so obvious slips never need a round trip. Returns an i18n error code. */
export function checkDriverForm(f: DriverBody & { needPhone: boolean }): string | null {
  if (f.needPhone && !/^\+?[\d\s\-()]{9,18}$/.test(f.phone ?? '')) return 'bad_phone'
  if (f.car_make.trim().length < 2 || f.car_color.trim().length < 2) return 'generic'
  const plate = f.car_plate.replace(/[\s\-_]/g, '').toUpperCase()
  if (!/^\d{2}([A-Z]\d{3}[A-Z]{2}|\d{3}[A-Z]{3})$/.test(plate)) return 'bad_plate'
  if (f.seats < 1 || f.seats > 8) return 'bad_seats'
  return null
}

function Register() {
  const { t, err } = useI18n()
  const { me, setMe } = useMe()
  const { busy, error, run } = useAction()
  const [f, setF] = useState({ phone: '', car_make: '', car_color: '', car_plate: '', seats: 4 })
  const [problem, setProblem] = useState<string>()

  const submit = async () => {
    const code = checkDriverForm({ ...f, needPhone: !me.phone_set })
    if (code) {
      setProblem(code)
      haptic('error')
      return
    }
    setProblem(undefined)
    const res = await run(() => api.registerDriver({ ...f, phone: f.phone.trim() || undefined }))
    if (res) {
      haptic('success')
      setMe(res)
    }
  }

  return (
    <Card className="stack">
      {!me.phone_set ? (
        <Field label={t('driver.phone')}>
          <input type="tel" inputMode="tel" autoComplete="tel" placeholder="+998 90 123 45 67" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
        </Field>
      ) : null}
      <Field label={t('driver.make')}>
        <input value={f.car_make} maxLength={64} placeholder={t('driver.make_ph', { example: 'Cobalt' })} onChange={(e) => setF({ ...f, car_make: e.target.value })} />
      </Field>
      <Field label={t('driver.color')}>
        <input value={f.car_color} maxLength={32} placeholder={t('driver.color_ph')} onChange={(e) => setF({ ...f, car_color: e.target.value })} />
      </Field>
      <Field label={t('driver.plate')}>
        <input value={f.car_plate} maxLength={16} placeholder="30 A 123 BC" autoCapitalize="characters" onChange={(e) => setF({ ...f, car_plate: e.target.value })} />
      </Field>
      <Field label={t('driver.seats')}>
        <input type="number" min={1} max={8} value={f.seats} onChange={(e) => setF({ ...f, seats: Number(e.target.value) || 1 })} />
      </Field>
      {problem ? (
        <p className="error-inline" role="alert">
          {err(problem)}
        </p>
      ) : null}
      <Inline error={error} />
      <Button busy={busy} onClick={() => void submit()}>
        {t('driver.register')}
      </Button>
    </Card>
  )
}

type DocKey = 'license' | 'techpass' | 'car_photo'

function Documents() {
  const { t, err } = useI18n()
  const { me, setMe } = useMe()
  const { busy, error, run } = useAction()
  const [files, setFiles] = useState<Partial<Record<DocKey, File>>>({})
  const [problem, setProblem] = useState<string>()
  const [done, setDone] = useState(false)
  const driver = me.driver

  const pick = (key: DocKey) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    setDone(false)
    setProblem(undefined)
    setFiles((cur) => ({ ...cur, [key]: file }))
  }

  const upload = async () => {
    if (!files.license || !files.techpass) {
      setProblem('documents_required')
      return
    }
    const form = new FormData()
    for (const key of ['license', 'techpass', 'car_photo'] as DocKey[]) {
      const original = files[key]
      if (!original) continue
      const ready = await prepareImage(original)
      if (tooLarge(ready)) {
        setProblem('file_too_large')
        return
      }
      form.append(key, ready, ready.name)
    }
    setProblem(undefined)
    const res = await run(() => api.uploadDocuments(form))
    if (res) {
      haptic('success')
      setMe(res)
      setDone(true)
      setFiles({})
    }
  }

  const input = (key: DocKey, label: string) => (
    <Field label={label}>
      <input type="file" accept="image/*,application/pdf" onChange={pick(key)} />
      {files[key] ? <span className="hint">{files[key]?.name}</span> : null}
    </Field>
  )

  return (
    <Card className="stack">
      <h2>{t('driver.docs_title')}</h2>
      <p className="hint">{t('driver.docs_optional')}</p>
      <p className="hint">{t('driver.docs_privacy')}</p>
      {driver?.has_documents ? <p className="notice">{t('profile.documents_sent')}</p> : null}
      {input('license', t('driver.license'))}
      {input('techpass', t('driver.techpass'))}
      {input('car_photo', t('driver.car_photo'))}
      {problem ? (
        <p className="error-inline" role="alert">
          {err(problem)}
        </p>
      ) : null}
      <Inline error={error} />
      {done ? <p className="notice">{t('driver.uploaded')}</p> : null}
      <Button busy={busy} onClick={() => void upload()}>
        {t('driver.upload')}
      </Button>
    </Card>
  )
}

export default function Driver() {
  const { t } = useI18n()
  const { me } = useMe()
  return (
    <div className="stack">
      <h1>{t('driver.title')}</h1>
      {me.driver ? (
        <>
          <p className="notice">{t('driver.registered')}</p>
          <Documents />
        </>
      ) : (
        <Register />
      )}
    </div>
  )
}
