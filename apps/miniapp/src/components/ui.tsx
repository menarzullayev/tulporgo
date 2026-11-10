import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { ApiError } from '../api'
import { useI18n } from '../i18n'

const asset = (p: string) => `${import.meta.env.BASE_URL}${p}`

export function Icon({ name, size = 24, alt = '' }: { name: string; size?: number; alt?: string }) {
  return <img className="icon" src={asset(`icons/${name}.svg`)} width={size} height={size} alt={alt} />
}

export type MascotName = 'hello' | 'waiting' | 'thumbs' | 'driving' | 'sad' | 'map'
export function Mascot({ name, size = 120 }: { name: MascotName; size?: number }) {
  return <img className="mascot" src={asset(`mascot/${name}.webp`)} width={size} height={size} alt="" />
}

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'
export function Button({
  variant = 'primary',
  busy,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button type="button" className={`btn btn-${variant}`} {...rest} disabled={rest.disabled || busy} aria-busy={busy || undefined}>
      {busy ? <span className="spinner spinner-sm" aria-hidden /> : null}
      {children}
    </button>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`.trim()}>{children}</section>
}

export function Spinner() {
  const { t } = useI18n()
  return (
    <div className="center" role="status" aria-live="polite">
      <span className="spinner" aria-hidden />
      <span className="sr-only">{t('common.loading')}</span>
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const { t, err } = useI18n()
  return (
    <div className="error" role="alert">
      <p>{err(error.code)}</p>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          {t('common.retry')}
        </Button>
      ) : null}
    </div>
  )
}

export function Inline({ error }: { error: ApiError | undefined }) {
  const { err } = useI18n()
  return error ? (
    <p className="error-inline" role="alert">
      {err(error.code)}
    </p>
  ) : null
}

export function Empty({ text, mascot = 'waiting' }: { text: string; mascot?: MascotName }) {
  return (
    <div className="empty">
      <Mascot name={mascot} size={96} />
      <p>{text}</p>
    </div>
  )
}

export function Badge({ children, tone = 'brand' }: { children: ReactNode; tone?: 'brand' | 'muted' | 'ok' | 'bad' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function Rating({ value, count }: { value: number | null; count?: number }) {
  const { t } = useI18n()
  if (value === null) return <span className="hint">{t('common.no_rating')}</span>
  return (
    <span className="rating" aria-label={t('common.rating', { rating: value.toFixed(1) })}>
      <Icon name="star" size={16} /> {value.toFixed(1)}
      {count ? <span className="hint"> ({count})</span> : null}
    </span>
  )
}

export function StarInput({ value, onChange }: { value: number; onChange(n: number): void }) {
  const { t } = useI18n()
  return (
    <div className="stars" role="radiogroup" aria-label={t('trip.rate_title')}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={t('trip.stars', { n })}
          className={`star${n <= value ? ' on' : ''}`}
          onClick={() => onChange(n)}
        >
          ★
        </button>
      ))}
    </div>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="hint">{hint}</span> : null}
    </label>
  )
}

export function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="row">
      <span className="hint">{label}</span>
      <span className="row-value">{children}</span>
    </div>
  )
}
