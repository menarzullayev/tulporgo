import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  delete (window as { Telegram?: unknown }).Telegram
  window.location.hash = ''
  document.documentElement.removeAttribute('style')
  delete document.documentElement.dataset.scheme
})
