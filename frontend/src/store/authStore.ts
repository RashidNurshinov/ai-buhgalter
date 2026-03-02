/**
 * Zustand-стор для аутентификации.
 * Пункт плана: 1.17.5
 */
import { create } from 'zustand';
import type { User } from '@/types';
import { authApi, userApi } from '@/api/endpoints';
import { AxiosError } from 'axios';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  setUser: (user: User) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName: string,
  ) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: false,
  error: null,

  setUser: (user: User) => set({ user }),

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authApi.login({ email, password });
      const { access_token, refresh_token } = response.data;

      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      // Загружаем профиль пользователя
      const userResponse = await userApi.getMe();

      set({
        user: userResponse.data,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>;
      set({
        isLoading: false,
        error:
          axiosErr.response?.data?.detail ||
          'Ошибка входа. Проверьте email и пароль.',
      });
      throw err;
    }
  },

  register: async (email, password, fullName) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authApi.register({
        email,
        password,
        full_name: fullName,
      });
      const { access_token, refresh_token } = response.data;

      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      const userResponse = await userApi.getMe();

      set({
        user: userResponse.data,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>;
      set({
        isLoading: false,
        error:
          axiosErr.response?.data?.detail ||
          'Ошибка регистрации. Попробуйте другой email.',
      });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, isAuthenticated: false, error: null });
  },

  fetchUser: async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      set({ user: null, isAuthenticated: false });
      return;
    }

    set({ isLoading: true });
    try {
      const response = await userApi.getMe();
      set({
        user: response.data,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch {
      // Токен невалиден
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  },

  clearError: () => set({ error: null }),
}));