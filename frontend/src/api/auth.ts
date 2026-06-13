import { api } from './client';
import type { TokenResponse, User } from '../types';

export const authApi = {
  register: (email: string, password: string) =>
    api.post<{ id: string; email: string; message: string }>('/api/v1/auth/register', {
      email,
      password,
    }),

  login: (email: string, password: string) =>
    api.post<TokenResponse>('/api/v1/auth/token', { email, password }),

  forgotPassword: (email: string) =>
    api.post<{ message: string }>('/api/v1/auth/forgot-password', { email }),

  resetPassword: (token: string, new_password: string) =>
    api.post<{ message: string }>('/api/v1/auth/reset-password', { token, new_password }),

  me: () => api.get<User>('/api/v1/users/me'),

  updateMe: (body: { timezone?: string; current_password?: string; new_password?: string }) =>
    api.patch<User>('/api/v1/users/me', body),

  deleteMe: () => api.delete('/api/v1/users/me'),
};
