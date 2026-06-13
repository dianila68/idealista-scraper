import { api } from './client';
import type { Filter, FilterCreate } from '../types';

export const filtersApi = {
  list: () => api.get<Filter[]>('/api/v1/filters'),
  create: (body: FilterCreate) => api.post<Filter>('/api/v1/filters', body),
  delete: (id: string) => api.delete(`/api/v1/filters/${id}`),
};
