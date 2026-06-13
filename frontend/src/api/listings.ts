import { api } from './client';
import type { ListingsPage, MapPoint } from '../types';

export interface ListingParams {
  cursor?: string;
  limit?: number;
  source?: string;
  listing_type?: string;
  city?: string;
  min_price?: number;
  max_price?: number;
  min_surface?: number;
  max_surface?: number;
  min_rooms?: number;
  filter_id?: string;
}

export const listingsApi = {
  list: (params: ListingParams = {}) =>
    api.get<ListingsPage>('/api/v1/listings', { params }),

  map: (filter_id?: string) =>
    api.get<{ listings: MapPoint[] }>('/api/v1/listings/map', {
      params: filter_id ? { filter_id } : undefined,
    }),
};
