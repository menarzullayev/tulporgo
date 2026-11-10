import { initData } from './tg'
import type {
  CreateRequestBody,
  DriverBody,
  DriverOffer,
  Me,
  OffersResponse,
  Offer,
  PlaceItem,
  Plans,
  RideRequest,
  SharedTrip,
  Trip,
} from './types'

export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
    detail = '',
  ) {
    super(detail || code)
  }
}

const base = (): string => ((import.meta.env.VITE_API_BASE as string | undefined) ?? '/api').replace(/\/$/, '')

interface Opts {
  method?: 'GET' | 'POST' | 'PATCH'
  body?: unknown
  form?: FormData
  auth?: boolean
  signal?: AbortSignal
}

export async function request<T>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (opts.auth !== false) {
    const data = initData()
    if (data) headers.Authorization = `tma ${data}`
  }
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  let res: Response
  try {
    res = await fetch(base() + path, { method: opts.method ?? 'GET', headers, body, signal: opts.signal })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError('network', 0)
  }
  let json: unknown = null
  try {
    json = await res.json()
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) {
    const j = (json ?? {}) as { error?: string; detail?: unknown }
    const code = res.status === 401 ? 'unauthorized' : typeof j.error === 'string' ? j.error : 'generic'
    throw new ApiError(code, res.status, typeof j.detail === 'string' ? j.detail : '')
  }
  return json as T
}

const post = <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body })

export const api = {
  me: () => request<Me>('/me'),
  patchMe: (body: { lang?: string; is_woman?: boolean }) => request<Me>('/me', { method: 'PATCH', body }),
  plans: () => request<Plans>('/plans'),

  searchPlaces: (q: string, signal?: AbortSignal) =>
    request<{ items: PlaceItem[] }>(`/places?q=${encodeURIComponent(q)}`, { signal }),
  nearestPlace: (lat: number, lon: number) =>
    request<{ item: PlaceItem; distance_km: number }>(`/places/nearest?lat=${lat}&lon=${lon}`),

  createRequest: (body: CreateRequestBody) => post<RideRequest>('/requests', body),
  myRequests: () => request<{ items: RideRequest[] }>('/requests/mine'),
  cancelRequest: (id: number) => post<RideRequest>(`/requests/${id}/cancel`),
  offers: (id: number) => request<OffersResponse>(`/requests/${id}/offers`),
  acceptOffer: (id: number) => post<Trip>(`/offers/${id}/accept`),
  counterOffer: (id: number, price: number) => post<Offer>(`/offers/${id}/counter`, { price }),

  myTrips: () => request<{ items: Trip[] }>('/trips/mine'),
  trip: (id: number) => request<Trip>(`/trips/${id}`),
  startTrip: (id: number) => post<Trip>(`/trips/${id}/start`),
  completeTrip: (id: number) => post<Trip>(`/trips/${id}/complete`),
  cancelTrip: (id: number) => post<Trip>(`/trips/${id}/cancel`),
  rateTrip: (id: number, stars: number, comment: string) =>
    post<{ ok: boolean; stars: number }>(`/trips/${id}/rate`, { stars, comment: comment || null }),

  /** Public: no Authorization header is sent. */
  shared: (token: string) => request<SharedTrip>(`/share/${encodeURIComponent(token)}`, { auth: false }),

  registerDriver: (body: DriverBody) => post<Me>('/driver', body),
  uploadDocuments: (form: FormData) => request<Me>('/driver/documents', { method: 'POST', form }),
  driverOffers: () => request<{ items: DriverOffer[] }>('/driver/offers'),

  // W2 (apps/userbot): login runs here, never through a Telegram chat. Contract: docs/goals/W2.md
  userbotCancel: () => post<unknown>('/userbot/login/cancel'),
  userbotStart: (phone: string) => post<unknown>('/userbot/login/start', { phone }),
  userbotCode: (code: string) => post<unknown>('/userbot/login/code', { code }),
  userbotPassword: (password: string) => post<unknown>('/userbot/login/password', { password }),

  // W4 (packages/payments): checkout payload is provider specific
  checkout: (plan: string, months = 1, provider = 'p2p') =>
    post<Record<string, unknown>>('/payments/checkout', { plan, months, provider }),
}
