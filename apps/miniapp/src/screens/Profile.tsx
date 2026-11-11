import { useState } from 'react'
import { api } from '../api'
import { useMe } from '../app-context'
import { Badge, Button, Card, Icon, Inline, Rating, Row } from '../components/ui'
import { formatDate } from '../format'
import { useAction } from '../hooks'
import { LANGS, useI18n } from '../i18n'
import { href } from '../router'
import { haptic, openTelegram, shareLink } from '../tg'
import { LogoutButton } from '../components/WebLogin'
import type { LangCode, Me } from '../types'

/** The one-line subscription status shown on the profile, from the user's point of view. */
export function subscriptionLine(
  me: Pick<Me, 'free_period' | 'free_period_until' | 'driver'>,
  t: (k: string, p?: Record<string, string | number>) => string,
  lang: LangCode,
): string {
  if (me.free_period) {
    return me.free_period_until
      ? t('profile.sub_free', { date: formatDate(me.free_period_until, lang) })
      : t('profile.sub_free_open')
  }
  const until = me.driver?.subscription_until
  return me.driver?.subscription_active && until ? t('profile.sub_until', { date: formatDate(until, lang) }) : t('profile.sub_none')
}

/** Privacy policy §8: export or delete own data — handled by the bot's /malumotlarim screen. */
export const MY_DATA_URL = 'https://t.me/tulporgobot?start=malumotlarim'

export default function Profile() {
  const { t, lang, setLang } = useI18n()
  const { me, setMe } = useMe()
  const { error, run } = useAction()
  const [copied, setCopied] = useState(false)
  const d = me.driver

  const chooseLang = async (code: LangCode) => {
    setLang(code) // instant; the choice is stored so the bot speaks the same language
    haptic('select')
    const res = await run(() => api.patchMe({ lang: code }))
    if (res) setMe(res)
  }
  const toggleWoman = async (on: boolean) => {
    const res = await run(() => api.patchMe({ is_woman: on }))
    if (res) setMe(res)
  }
  const copy = async () => {
    if (!me.referral_link) return
    try {
      await navigator.clipboard.writeText(me.referral_link)
      setCopied(true)
    } catch {
      /* blocked clipboard: the share button still works */
    }
  }

  return (
    <div className="stack">
      <h1>{me.first_name ?? t('profile.title')}</h1>
      <Inline error={error} />

      <Card className="stack">
        <h2>{t('profile.language')}</h2>
        <div className="seg seg-wrap" role="radiogroup" aria-label={t('profile.language')}>
          {LANGS.map((l) => (
            <button key={l.code} type="button" role="radio" aria-checked={lang === l.code} className={lang === l.code ? 'on' : ''} onClick={() => void chooseLang(l.code)}>
              {l.name}
            </button>
          ))}
        </div>
      </Card>

      <Card className="stack">
        <label className="switch">
          <input type="checkbox" role="switch" checked={me.is_woman} onChange={(e) => void toggleWoman(e.target.checked)} />
          <span>
            <strong>{t('profile.woman')}</strong>
            <span className="hint block">{t('profile.woman_hint')}</span>
          </span>
        </label>
      </Card>

      <Card className="stack">
        <h2>{t('profile.driver')}</h2>
        {d ? (
          <>
            <Row label={t('driver.make')}>
              {d.car_make}, {d.car_color}
            </Row>
            <Row label={t('driver.plate')}>
              <span className="plate">{d.car_plate}</span>
            </Row>
            <Row label={t('common.rating', { rating: '' }).trim()}>
              <Rating value={d.rating} count={d.rating_count} />
            </Row>
            <div className="badges">
              <Badge tone={d.status === 'active' ? 'ok' : 'muted'}>{t(`driver.status.${d.status}`)}</Badge>
              {d.verified ? (
                <Badge>
                  <Icon name="check" size={14} /> {t('common.verified')}
                </Badge>
              ) : null}
            </div>
            <p className="hint">{d.has_documents ? t('profile.documents_sent') : t('profile.documents_missing')}</p>
            <a className="btn btn-secondary" href={href('/driver')}>
              {t('profile.send_documents')}
            </a>
          </>
        ) : (
          <a className="btn btn-primary" href={href('/driver')}>
            {t('profile.become_driver')}
          </a>
        )}
      </Card>

      {me.referral_link ? (
        <Card className="stack">
          <h2>{t('profile.referral')}</h2>
          <code className="code" data-testid="referral-link">
            {me.referral_link}
          </code>
          <p className="hint">{t('profile.referral_hint')}</p>
          <div className="actions">
            <Button onClick={() => shareLink(me.referral_link ?? '', t('profile.referral_text'))}>{t('profile.referral_share')}</Button>
            <Button variant="secondary" onClick={() => void copy()}>
              {copied ? t('common.copied') : t('common.copy')}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card className="stack">
        <h2>{t('profile.subscription')}</h2>
        <p data-testid="sub-line">{subscriptionLine(me, t, lang)}</p>
        <a className="btn btn-secondary" href={href('/subscription')}>
          {t('profile.sub_open')}
        </a>
      </Card>

      {d ? (
        <Card className="stack">
          <h2>{t('profile.userbot')}</h2>
          <p className="hint">{t('profile.userbot_hint')}</p>
          <a className="btn btn-secondary" href={href('/userbot/login')}>
            {t('profile.userbot_open')}
          </a>
          <p className="hint">{t('profile.feed_hint')}</p>
          <a className="btn btn-secondary" href={href('/feed')}>
            {t('profile.feed_open')}
          </a>
        </Card>
      ) : null}

      <Card className="stack">
        <h2>{t('profile.my_data')}</h2>
        <p className="hint">{t('profile.my_data_hint')}</p>
        <Button variant="secondary" onClick={() => openTelegram(MY_DATA_URL)}>
          {t('profile.my_data_open')}
        </Button>
      </Card>

      <LogoutButton />
    </div>
  )
}
