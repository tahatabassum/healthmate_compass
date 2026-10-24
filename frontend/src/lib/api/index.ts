/** Axios instance pointing at the FastAPI backend. */
import axios from 'axios';
import { supabase } from '../supabase';

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL;
const baseURL = rawBaseUrl ? rawBaseUrl.trim().replace(/\/+$/, '') : 'http://localhost:8000';

const api = axios.create({
  baseURL,
  timeout: 120_000, // 120 seconds to allow vision and report extraction to complete without truncation
});

// Attach Supabase JWT on every request
api.interceptors.request.use(async (config) => {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      // If token is expiring within 60 seconds, refresh proactively
      const isExpiringSoon = session.expires_at && (session.expires_at * 1000 - Date.now() < 60_000);
      if (isExpiringSoon) {
        const { data: refreshed } = await supabase.auth.refreshSession();
        if (refreshed?.session?.access_token) {
          config.headers.Authorization = `Bearer ${refreshed.session.access_token}`;
          return config;
        }
      }
      config.headers.Authorization = `Bearer ${session.access_token}`;
    } else if (import.meta.env.DEV) {
      // In local dev ONLY: allow fallback mock token when not logged in
      config.headers.Authorization = 'Bearer dev-user-demo';
    }
  } catch (err) {
    console.warn('[API] Failed to retrieve Supabase session:', err);
    if (import.meta.env.DEV) {
      config.headers.Authorization = 'Bearer dev-user-demo';
    }
  }
  return config;
});

// Intercept 401 responses: attempt a single session refresh and retry; sign out on permanent failure to prevent loops
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const { data: refreshData, error: refreshError } = await supabase.auth.refreshSession();
        if (!refreshError && refreshData?.session?.access_token) {
          originalRequest.headers.Authorization = `Bearer ${refreshData.session.access_token}`;
          return api(originalRequest);
        }
      } catch (refreshErr) {
        console.warn('[API] Token refresh on 401 failed:', refreshErr);
      }
      // Cleanly sign out on failed refresh to avoid stale credential state
      try {
        await supabase.auth.signOut();
      } catch (_) {}
    }
    return Promise.reject(error);
  }
);

export default api;

