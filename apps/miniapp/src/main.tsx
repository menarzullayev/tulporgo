import '@fontsource-variable/manrope'
import '@fontsource-variable/unbounded'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import { startApp } from './tg'
import { captureLoginFromHash } from './webAuth'

captureLoginFromHash() // before the first render: the router reads the (cleaned) hash
startApp()
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
