import { useCallback, useState, type ReactNode } from 'react'
import { api } from './api'
import { MeContext } from './app-context'
import { ErrorBox, Icon, Mascot, Spinner } from './components/ui'
import { useAsync } from './hooks'
import { I18nProvider, useI18n } from './i18n'
import { goBack, href, useRoute, type Route } from './router'
import Driver from './screens/Driver'
import Home from './screens/Home'
import Offers from './screens/Offers'
import Profile from './screens/Profile'
import Share from './screens/Share'
import Subscription from './screens/Subscription'
import Trip from './screens/Trip'
import Trips from './screens/Trips'
import UserbotLogin from './screens/UserbotLogin'
import { inTelegram, telegramLang, useBackButton } from './tg'
import { WebLogin } from './components/WebLogin'
import type { Me } from './types'

const TABS = [
  { path: '/', icon: 'taxi', label: 'nav.home', names: ['home', 'offers'] },
  { path: '/trips', icon: 'clock', label: 'nav.trips', names: ['trips', 'trip'] },
  { path: '/profile', icon: 'driver', label: 'nav.profile', names: ['profile', 'driver', 'subscription', 'userbot'] },
]
const TOP_LEVEL = new Set(['home', 'trips', 'profile'])

function Screen({ route }: { route: Route }) {
  const { t } = useI18n()
  switch (route.name) {
    case 'home':
      return <Home />
    case 'offers':
      return <Offers id={Number(route.params.id)} />
    case 'trips':
      return <Trips />
    case 'trip':
      return <Trip id={Number(route.params.id)} />
    case 'profile':
      return <Profile />
    case 'driver':
      return <Driver />
    case 'subscription':
      return <Subscription />
    case 'userbot':
      return <UserbotLogin />
    default:
      return (
        <div className="empty">
          <Mascot name="sad" size={110} />
          <p>{t('err.generic')}</p>
        </div>
      )
  }
}

function Shell({ route, children }: { route: Route; children: ReactNode }) {
  const { t } = useI18n()
  useBackButton(!TOP_LEVEL.has(route.name), goBack)
  return (
    <div className="app">
      <header className="brandbar">
        <img className="logo" src={`${import.meta.env.BASE_URL}logo.png`} width={36} height={36} alt="" />
        <span className="wordmark">TULPORGO</span>
      </header>
      <main>{children}</main>
      <nav className="tabs" aria-label="TulporGo">
        {TABS.map((tab) => {
          const active = tab.names.includes(route.name)
          return (
            <a key={tab.path} href={href(tab.path)} className={active ? 'tab on' : 'tab'} aria-current={active ? 'page' : undefined}>
              <Icon name={tab.icon} size={26} />
              <span>{t(tab.label)}</span>
            </a>
          )
        })}
      </nav>
    </div>
  )
}

function Authed({ route }: { route: Route }) {
  const state = useAsync(() => api.me(), [])
  const [override, setOverride] = useState<Me>()
  const setMe = useCallback((m: Me) => setOverride(m), [])
  const me = override ?? state.data

  if (!me) {
    if (state.error?.code === 'unauthorized' || (!state.loading && !inTelegram() && state.error))
      return (
        <I18nProvider key="anonymous" initial={telegramLang() ?? navigator.language}>
          <OpenInTelegram />
        </I18nProvider>
      )
    return (
      <I18nProvider key="anonymous" initial={telegramLang() ?? navigator.language}>
        {state.error ? <ErrorBox error={state.error} onRetry={state.reload} /> : <Spinner />}
      </I18nProvider>
    )
  }
  return (
    <I18nProvider key="signed-in" initial={me.lang ?? telegramLang()}>
      <MeContext.Provider value={{ me, setMe, reloadMe: state.reload }}>
        <Shell route={route}>
          <Screen route={route} />
        </Shell>
      </MeContext.Provider>
    </I18nProvider>
  )
}

function OpenInTelegram() {
  const { t } = useI18n()
  return (
    <div className="empty full">
      <Mascot name="hello" size={140} />
      <h1>TulporGo</h1>
      <p>{t('common.open_in_telegram')}</p>
      <WebLogin />
    </div>
  )
}

export default function App() {
  const route = useRoute()
  if (route.name === 'share')
    return (
      <I18nProvider key="anonymous" initial={telegramLang() ?? navigator.language}>
        <Share token={route.params.token} />
      </I18nProvider>
    )
  return <Authed route={route} />
}
