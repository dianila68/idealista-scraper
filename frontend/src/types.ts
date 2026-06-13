export interface User {
  id: string;
  email: string;
  is_verified: boolean;
  is_active: boolean;
  timezone: string;
  created_at: string;
  filter_count: number;
  device_count: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Listing {
  id: string;
  source: string;
  source_id: string;
  url: string;
  title: string;
  price: number | null;
  surface_m2: number | null;
  rooms: number | null;
  floor: number | null;
  city: string | null;
  zone: string | null;
  lat: number | null;
  lng: number | null;
  location_precision: string;
  is_furnished: boolean | null;
  listing_type: string;
  description: string | null;
  image_urls: string[];
  scraped_at: string;
  first_seen_at: string;
}

export interface ListingsPage {
  items: Listing[];
  next_cursor: string | null;
  total: number;
}

export interface MapPoint {
  id: string;
  title: string;
  price: number | null;
  city: string | null;
  zone: string | null;
  lat: number;
  lng: number;
  url: string;
  location_precision: string;
}

export interface Filter {
  id: string;
  name: string;
  city: string | null;
  min_price: number | null;
  max_price: number | null;
  min_surface: number | null;
  max_surface: number | null;
  min_rooms: number | null;
  listing_type: string | null;
  sources: string[];
  is_active: boolean;
  created_at: string;
}

export interface FilterCreate {
  name: string;
  city?: string | null;
  min_price?: number | null;
  max_price?: number | null;
  min_surface?: number | null;
  max_surface?: number | null;
  min_rooms?: number | null;
  listing_type?: string | null;
  sources?: string[];
}
