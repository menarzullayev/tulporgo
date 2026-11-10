import { createContext, useContext } from 'react'
import type { Me } from './types'

interface MeCtx {
  me: Me
  setMe(m: Me): void
  reloadMe(): void
}

export const MeContext = createContext<MeCtx | null>(null)

export function useMe(): MeCtx {
  const c = useContext(MeContext)
  if (!c) throw new Error('useMe outside the app shell')
  return c
}
