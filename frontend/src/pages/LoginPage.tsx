import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { signIn, signUp, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  // If already logged in, redirect to origin or dashboard
  const from = (location.state as any)?.from?.pathname || '/';

  React.useEffect(() => {
    if (user) {
      navigate(from, { replace: true });
    }
  }, [user, navigate, from]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setInfoMessage(null);

    if (!email.trim() || !password) {
      setErrorMessage('Please enter both email and password.');
      return;
    }

    if (mode === 'signup') {
      if (!fullName.trim()) {
        setErrorMessage('Please enter your full name.');
        return;
      }
      if (password.length < 6) {
        setErrorMessage('Password must be at least 6 characters.');
        return;
      }
      if (password !== confirmPassword) {
        setErrorMessage('Passwords do not match.');
        return;
      }

      setLoading(true);
      const res = await signUp(email, password, fullName.trim());
      setLoading(false);

      if (res.error) {
        setErrorMessage(res.error.message || 'Failed to create account.');
      } else if (res.needsEmailConfirmation) {
        setInfoMessage(
          'Account created! A confirmation email has been sent. Please verify your email before logging in.'
        );
        setMode('signin');
      } else {
        // Logged in immediately!
        navigate(from, { replace: true });
      }
    } else {
      setLoading(true);
      const res = await signIn(email, password);
      setLoading(false);

      if (res.error) {
        setErrorMessage(res.error.message || 'Invalid email or password.');
      } else {
        navigate(from, { replace: true });
      }
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col justify-between selection:bg-primary-fixed selection:text-on-primary-fixed">
      {/* Top Banner */}
      <header className="px-6 py-4 flex items-center justify-between border-b border-outline-variant/60 bg-surface-container-lowest">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center shadow-xs">
            <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
              medical_services
            </span>
          </div>
          <div>
            <span className="text-lg font-bold text-primary tracking-tight">HealthMate Compass</span>
            <span className="hidden sm:inline-block ml-2 text-[10px] font-semibold text-secondary bg-surface-container px-2 py-0.5 rounded-full border border-outline-variant/40">
              Clinical Portal
            </span>
          </div>
        </div>

        {/* Emergency Notice */}
        <a
          href="tel:1122"
          className="flex items-center gap-1.5 bg-[#DC2626] hover:bg-[#B91C1C] text-white px-3 py-1.5 rounded-xl text-xs font-bold shadow-xs active:scale-95 transition-all"
        >
          <span className="material-symbols-outlined text-sm animate-pulse" style={{ fontVariationSettings: "'FILL' 1" }}>
            emergency
          </span>
          <span>Emergency: 1122</span>
        </a>
      </header>

      {/* Main Auth Card Container */}
      <main className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-md bg-surface-container-lowest border border-outline-variant/70 rounded-3xl p-6 sm:p-8 shadow-md">
          {/* Header Title */}
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-primary-container/30 text-primary mb-3">
              <span className="material-symbols-outlined text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                {mode === 'signin' ? 'lock' : 'person_add'}
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-on-surface tracking-tight">
              {mode === 'signin' ? 'Welcome Back' : 'Create Your Health Account'}
            </h1>
            <p className="text-xs text-secondary mt-1">
              {mode === 'signin'
                ? 'Sign in to access your lab reports and private health history.'
                : '1-User-1-Profile architecture. Your medical records remain private and encrypted.'}
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="flex bg-surface-container-low p-1 rounded-2xl border border-outline-variant/50 mb-6">
            <button
              type="button"
              onClick={() => {
                setMode('signin');
                setErrorMessage(null);
                setInfoMessage(null);
              }}
              className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all ${
                mode === 'signin'
                  ? 'bg-surface-container-lowest text-primary shadow-xs'
                  : 'text-secondary hover:text-on-surface'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('signup');
                setErrorMessage(null);
                setInfoMessage(null);
              }}
              className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all ${
                mode === 'signup'
                  ? 'bg-surface-container-lowest text-primary shadow-xs'
                  : 'text-secondary hover:text-on-surface'
              }`}
            >
              Sign Up
            </button>
          </div>

          {/* Error Message */}
          {errorMessage && (
            <div className="mb-4 p-3.5 rounded-2xl bg-error-container/20 border border-error/30 text-error text-xs flex items-start gap-2 animate-in fade-in">
              <span className="material-symbols-outlined text-base shrink-0">error</span>
              <span className="leading-snug">{errorMessage}</span>
            </div>
          )}

          {/* Info Message (e.g. Email confirmation fallback) */}
          {infoMessage && (
            <div className="mb-4 p-3.5 rounded-2xl bg-primary-container/20 border border-primary/30 text-primary text-xs flex items-start gap-2 animate-in fade-in">
              <span className="material-symbols-outlined text-base shrink-0">mark_email_read</span>
              <span className="leading-snug">{infoMessage}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <div>
                <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1.5">
                  Full Name
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-3.5 top-3 text-secondary text-lg">
                    badge
                  </span>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Taha Tabassum"
                    className="w-full bg-surface-container-low border border-outline-variant/60 rounded-2xl pl-10 pr-3.5 py-2.5 text-xs sm:text-sm text-on-surface focus:outline-none focus:border-primary transition-colors"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3.5 top-3 text-secondary text-lg">
                  mail
                </span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full bg-surface-container-low border border-outline-variant/60 rounded-2xl pl-10 pr-3.5 py-2.5 text-xs sm:text-sm text-on-surface focus:outline-none focus:border-primary transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3.5 top-3 text-secondary text-lg">
                  key
                </span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-surface-container-low border border-outline-variant/60 rounded-2xl pl-10 pr-10 py-2.5 text-xs sm:text-sm text-on-surface focus:outline-none focus:border-primary transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-secondary hover:text-on-surface transition-colors"
                >
                  <span className="material-symbols-outlined text-lg">
                    {showPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>

            {mode === 'signup' && (
              <div>
                <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1.5">
                  Confirm Password
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-3.5 top-3 text-secondary text-lg">
                    lock_reset
                  </span>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-surface-container-low border border-outline-variant/60 rounded-2xl pl-10 pr-3.5 py-2.5 text-xs sm:text-sm text-on-surface focus:outline-none focus:border-primary transition-colors"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3 px-4 rounded-2xl bg-primary text-on-primary hover:opacity-95 font-bold text-xs sm:text-sm shadow-xs transition-all active:scale-98 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>{mode === 'signin' ? 'Signing In...' : 'Creating Account...'}</span>
                </>
              ) : (
                <>
                  <span>{mode === 'signin' ? 'Sign In to HealthMate' : 'Create Free Account'}</span>
                  <span className="material-symbols-outlined text-sm">arrow_forward</span>
                </>
              )}
            </button>
          </form>

          {/* Fallback Notice for Email Confirmation */}
          <div className="mt-6 pt-4 border-t border-outline-variant/40 text-center">
            <p className="text-[11px] text-secondary leading-relaxed">
              Note: Email confirmation is currently disabled for instant sign-in. If re-enabled on Supabase, check your inbox to confirm before signing in.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 text-center text-xs text-secondary border-t border-outline-variant/40">
        HealthMate Compass • HacktoberFest &copy; 2026 • Faisalabad, Pakistan
      </footer>
    </div>
  );
};
