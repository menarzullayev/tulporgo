// Shapes of the JSON returned by apps/api (tulporgo_api.routes). Kept by hand: the API is small and stable.

export type LangCode = 'uz_new' | 'uz_latn' | 'uz_cyrl' | 'ru' | 'en'

export interface DriverCard {
  id: number
  status: 'pending' | 'active' | 'suspended' | 'blocked'
  verified: boolean
  car_make: string
  car_color: string
  car_plate: string
  seats: number
  has_photo: boolean
  has_documents: boolean
  rating: number | null
  rating_count: number
  ambassador: boolean
  plan: string | null
  subscription_until: string | null
  subscription_active: boolean
  effective_plan: string | null
}

export interface Me {
  id: number
  first_name: string | null
  username: string | null
  lang: string | null
  is_woman: boolean
  phone_set: boolean
  is_admin: boolean
  driver: DriverCard | null
  free_period: boolean
  free_period_until: string | null
  referral_link: string | null
}

export interface PlaceItem {
  id: number
  name: string
  name_ru: string | null
  kind: string
  parent: string | null
  lat: number | null
  lon: number | null
}

export interface RideRequest {
  id: number
  status: 'open' | 'matched' | 'cancelled' | 'expired' | 'completed'
  from_text: string
  to_text: string
  from_place_id: number | null
  to_place_id: number | null
  depart_at: string | null
  seats: number
  women_only: boolean
  note: string | null
  price_hint: number | null
  created_at: string
  expires_at: string | null
  offers_count: number
}

export interface OfferDriver {
  first_name: string | null
  car_make: string
  car_color: string
  rating: number | null
  rating_count: number
  verified: boolean
}

export interface Offer {
  id: number
  request_id: number
  status: 'sent' | 'countered' | 'accepted' | 'declined' | 'withdrawn' | 'expired'
  price: number
  counter_price: number | null
  message: string | null
  created_at: string
  driver: OfferDriver
}

export interface OffersResponse {
  request: RideRequest
  offers: Offer[]
  trip_id: number | null
}

export interface Trip {
  id: number
  request_id: number
  status: 'confirmed' | 'started' | 'completed' | 'cancelled'
  price: number
  role: 'passenger' | 'driver'
  from_text: string
  to_text: string
  depart_at: string | null
  seats: number
  women_only: boolean
  created_at: string
  completed_at: string | null
  share_token: string
  share_url: string
  car: { make: string; color: string; plate: string }
  driver_verified: boolean
  driver_rating: number | null
  counterparty: { first_name: string | null; username: string | null; phone: string | null }
  rated: boolean
}

export interface SharedTrip {
  status: Trip['status']
  finished: boolean
  from: string
  to: string
  depart_at: string | null
  driver_first_name: string | null
  car: { make: string; color: string; plate: string }
}

export interface Plan {
  plan: 'basic' | 'pro' | 'business'
  price_uzs: number
  max_groups: number | null
  autopost: boolean
  priority: boolean
}

export interface Plans {
  free_period: boolean
  free_period_until: string | null
  trial_days: number
  plans: Plan[]
}

export interface DriverOffer {
  id: number
  request_id: number
  status: string
  price: number
  counter_price: number | null
  trip_id: number | null
  from_text: string
  to_text: string
  depart_at: string | null
  seats: number
  request_status: string
}

export interface CreateRequestBody {
  from_place_id?: number | null
  to_place_id?: number | null
  from_text?: string
  to_text?: string
  depart_at?: string | null
  seats: number
  note?: string | null
}

export interface DriverBody {
  phone?: string
  car_make: string
  car_color: string
  car_plate: string
  seats: number
  referral_code?: string
}
