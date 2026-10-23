/** Axios instance pointing at the FastAPI backend. */
import axios from 'axios';
import { supabase } from '../supabase';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  timeout: 120_000, // 120 seconds to allow vision and report extraction to complete without truncation
});

// Attach Supabase JWT on every request
api.interceptors.request.use(async (config) => {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = 'Bearer ' + session.access_token;
    } else {
      config.headers.Authorization = 'Bearer dev-user-demo';
    }
  } catch (err) {
    config.headers.Authorization = 'Bearer dev-user-demo';
  }
  return config;
});

export default api;

