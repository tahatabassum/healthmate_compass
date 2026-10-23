import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { User, Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import api from '../lib/api';

export interface UserProfile {
  id: string;
  owner_id: string;
  full_name: string;
  relation: string;
  gender?: string;
  blood_group?: string;
  dob?: string;
  chronic_conditions?: string[];
  allergies?: string[];
}

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: UserProfile | null;
  loading: boolean;
  signIn: (email: string, pass: string) => Promise<{ error: Error | null }>;
  signUp: (email: string, pass: string, fullName?: string) => Promise<{ error: Error | null; needsEmailConfirmation?: boolean }>;
  signOut: () => Promise<void>;
  updateProfile: (data: Partial<UserProfile>) => Promise<{ error: Error | null; profile?: UserProfile }>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Fetch or auto-create single user profile from backend
  const fetchProfile = async () => {
    try {
      const res = await api.get('/api/profile');
      if (res.data) {
        setProfile(res.data);
      }
    } catch (err) {
      console.warn('Could not fetch user profile from /api/profile:', err);
    }
  };

  useEffect(() => {
    // 1. Initial session check
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      if (session) {
        fetchProfile().finally(() => setLoading(false));
      } else {
        setLoading(false);
      }
    });

    // 2. Auth state change listener
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
      setSession(session);
      setUser(session?.user ?? null);
      if (session) {
        await fetchProfile();
      } else {
        setProfile(null);
      }
      setLoading(false);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const signIn = async (email: string, pass: string) => {
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password: pass,
      });
      if (error) {
        return { error };
      }
      await fetchProfile();
      return { error: null };
    } catch (err: any) {
      return { error: err };
    }
  };

  const signUp = async (email: string, pass: string, fullName?: string) => {
    try {
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password: pass,
        options: {
          data: {
            full_name: fullName || email.split('@')[0],
          },
        },
      });

      if (error) {
        return { error };
      }

      // If Supabase has confirm email off, session is returned immediately
      if (data.session) {
        setSession(data.session);
        setUser(data.user);
        // Sync full name with profile if given
        try {
          if (fullName) {
            await api.patch('/api/profile', { full_name: fullName });
          }
          await fetchProfile();
        } catch {
          // ignore
        }
        return { error: null, needsEmailConfirmation: false };
      }

      // If email confirmation is ever enabled, user is created without active session
      return { error: null, needsEmailConfirmation: !data.session };
    } catch (err: any) {
      return { error: err };
    }
  };

  const signOut = async () => {
    try {
      await supabase.auth.signOut();
    } catch (err) {
      console.warn('Error during signOut:', err);
    } finally {
      setUser(null);
      setSession(null);
      setProfile(null);
    }
  };

  const updateProfile = async (data: Partial<UserProfile>) => {
    try {
      const res = await api.patch('/api/profile', data);
      if (res.data) {
        setProfile(res.data);
        return { error: null, profile: res.data };
      }
      return { error: null };
    } catch (err: any) {
      return { error: err };
    }
  };

  const refreshProfile = async () => {
    await fetchProfile();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        profile,
        loading,
        signIn,
        signUp,
        signOut,
        updateProfile,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
