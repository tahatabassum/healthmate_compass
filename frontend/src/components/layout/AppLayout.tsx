import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { setLanguage } from '../../lib/i18n';
import { useAuth } from '../../context/AuthContext';

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const { i18n } = useTranslation();
  const location = useLocation();
  const { user, profile, signOut } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  const currentLang = i18n.language.startsWith('ur') ? 'ur' : 'en';

  const displayName = profile?.full_name || user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'User';

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .slice(0, 2)
      .join('')
      .toUpperCase();
  };

  const navItems = [
    { to: '/', label: 'Home', icon: 'home' },
    { to: '/translate', label: 'Reports', icon: 'description' },
    { to: '/consult', label: 'AI Doctor Chat', icon: 'smart_toy' },
    { to: '/doctors', label: 'Find Doctors', icon: 'location_on' },
    { to: '/memory', label: 'Health Memory', icon: 'history_edu' },
  ];

  return (
    <div className="h-screen flex flex-col font-sans text-on-surface bg-background antialiased selection:bg-primary-fixed selection:text-on-primary-fixed overflow-hidden">
      {/* ── TOP APP BAR (Stitch Header) ─────────────────────────────────── */}
      <header className="bg-surface-container-lowest border-b border-outline-variant shadow-xs top-0 sticky z-40 shrink-0">
        <div className="flex justify-between items-center w-full px-4 md:px-8 h-16">
          {/* Left: Brand Identity */}
          <div className="flex items-center gap-3 md:gap-4">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-1.5 text-on-surface-variant hover:text-primary transition-colors"
              aria-label="Toggle menu"
            >
              <span className="material-symbols-outlined text-2xl">menu</span>
            </button>

            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform">
                <span
                  className="material-symbols-outlined text-xl"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  medical_services
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg md:text-xl font-bold text-primary tracking-tight">
                  HealthMate Compass
                </span>
                <span className="hidden sm:inline-block text-[11px] font-semibold text-secondary bg-surface-container px-2 py-0.5 rounded-full border border-outline-variant/40">
                  Clinical AI
                </span>
              </div>
            </Link>
          </div>

          {/* Right Action Cluster */}
          <div className="flex items-center gap-2 md:gap-4">
            {/* Language Switcher Pill */}
            <div className="flex items-center bg-surface-container-low border border-outline-variant/60 rounded-xl p-0.5 text-xs font-semibold shadow-2xs">
              <button
                onClick={() => setLanguage('en')}
                className={`px-2.5 py-1 rounded-lg transition-all ${
                  currentLang === 'en'
                    ? 'bg-surface-container-lowest text-primary shadow-xs font-bold'
                    : 'text-secondary hover:text-primary'
                }`}
              >
                EN
              </button>
              <button
                onClick={() => setLanguage('ur')}
                className={`px-2.5 py-1 rounded-lg font-urdu transition-all ${
                  currentLang === 'ur'
                    ? 'bg-surface-container-lowest text-primary shadow-xs font-bold'
                    : 'text-secondary hover:text-primary'
                }`}
              >
                اردو
              </button>
            </div>

            {/* Authenticated User Profile Badge & Menu */}
            <div className="relative">
              <button
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                className="flex items-center gap-2 bg-surface-container-low hover:bg-surface-container-high border border-outline-variant/60 rounded-xl px-2.5 md:px-3 py-1.5 cursor-pointer transition-colors"
                title="Your Profile"
              >
                <div className="w-7 h-7 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center text-xs font-bold shadow-xs">
                  {getInitials(displayName)}
                </div>
                <div className="hidden md:flex flex-col text-left leading-tight">
                  <span className="text-xs font-semibold text-on-surface flex items-center gap-0.5">
                    {displayName}
                    <span className="material-symbols-outlined text-sm text-secondary">
                      expand_more
                    </span>
                  </span>
                  <span className="text-[10px] text-secondary">
                    {profile?.blood_group ? `Blood ${profile.blood_group}` : user?.email || '1-User Profile'}
                  </span>
                </div>
              </button>

              {/* User Dropdown Menu */}
              {userDropdownOpen && (
                <div className="absolute right-0 mt-2 w-64 bg-surface-container-lowest border border-outline-variant rounded-2xl shadow-lg p-2.5 z-50 animate-in fade-in">
                  <div className="px-3 py-2 border-b border-outline-variant/50 mb-1">
                    <p className="text-xs font-bold text-on-surface truncate">{displayName}</p>
                    <p className="text-[11px] text-secondary truncate">{user?.email}</p>
                    {profile?.blood_group && (
                      <span className="inline-block mt-1 text-[10px] font-bold text-primary bg-primary-container/20 px-2 py-0.5 rounded-md">
                        Blood: {profile.blood_group}
                      </span>
                    )}
                  </div>

                  <Link
                    to="/memory"
                    onClick={() => setUserDropdownOpen(false)}
                    className="flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-on-surface hover:bg-surface-container-low rounded-xl transition-colors"
                  >
                    <span className="material-symbols-outlined text-primary text-base">manage_accounts</span>
                    <span>Edit Health Profile</span>
                  </Link>

                  <div className="border-t border-outline-variant/60 my-1"></div>

                  <button
                    onClick={() => {
                      setUserDropdownOpen(false);
                      signOut();
                    }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-error hover:bg-error-container/20 rounded-xl transition-colors text-left"
                  >
                    <span className="material-symbols-outlined text-base">logout</span>
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>

          </div>
        </div>
      </header>

      {/* ── BODY VIEWPORT (Side Rail + Workspace Canvas) ─────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* PERSISTENT LEFT SIDEBAR RAIL (Desktop) */}
        <aside className="w-64 hidden lg:flex flex-col z-30 bg-surface-container-lowest border-r border-outline-variant shadow-xs shrink-0 select-none">
          <div className="h-full flex flex-col justify-between p-4">
            {/* Top Section */}
            <div className="space-y-4">
              {/* User Profile Pill */}
              <div className="p-3 bg-surface-container-low rounded-2xl border border-outline-variant/50 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-sm shrink-0 shadow-2xs">
                  {getInitials(displayName)}
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="text-xs font-bold text-on-surface truncate">
                    {displayName}
                  </h3>
                  <p className="text-[11px] text-secondary truncate">
                    {profile?.blood_group ? `Blood ${profile.blood_group}` : 'Health Profile'}
                  </p>
                </div>
              </div>

              {/* Navigation Tabs */}
              <nav className="space-y-1">
                {navItems.map((item) => {
                  const isActive =
                    item.to === '/'
                      ? location.pathname === '/'
                      : location.pathname.startsWith(item.to);
                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                        isActive
                          ? 'bg-primary-container text-on-primary-container shadow-xs font-bold'
                          : 'text-on-surface-variant hover:bg-surface-container-high hover:text-primary'
                      }`}
                    >
                      <span
                        className="material-symbols-outlined text-xl"
                        style={{ fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0" }}
                      >
                        {item.icon}
                      </span>
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>

            {/* Bottom Rail Section */}
            <div className="space-y-3 pt-3 border-t border-outline-variant/60">
              <a
                href="tel:1122"
                className="w-full flex items-center justify-center gap-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white py-2 px-3 rounded-xl text-xs font-bold shadow-xs active:scale-95 transition-all"
              >
                <span
                  className="material-symbols-outlined text-base"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  call
                </span>
                <span>Call Rescue 1122</span>
              </a>

              <button
                onClick={() => signOut()}
                className="w-full flex items-center justify-center gap-2 text-xs font-semibold text-secondary hover:text-error py-1.5 px-3 rounded-xl hover:bg-error-container/10 transition-colors"
              >
                <span className="material-symbols-outlined text-base">logout</span>
                <span>Sign Out</span>
              </button>

              <div className="space-y-0.5 text-xs text-secondary">
                <div className="flex items-center gap-2 px-2 py-1 text-[11px] text-secondary/80">
                  <span className="material-symbols-outlined text-sm">shield</span>
                  <span>Not a diagnosis • Medical advice</span>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* WORKSPACE CANVAS (Scrollable Main Page Area) */}
        <main className="flex-1 overflow-y-auto bg-background pb-16 lg:pb-6">
          {children}
        </main>
      </div>

      {/* MOBILE BOTTOM NAVIGATION */}
      <nav className="lg:hidden flex items-center justify-around bg-surface-container-lowest border-t border-outline-variant py-2 fixed bottom-0 left-0 right-0 z-50 shadow-md">
        {navItems.map((item) => {
          const isActive =
            item.to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex flex-col items-center gap-0.5 text-[10px] font-semibold py-1 px-2.5 rounded-lg transition-colors ${
                isActive ? 'text-primary font-bold' : 'text-secondary hover:text-on-surface'
              }`}
            >
              <span
                className="material-symbols-outlined text-xl"
                style={{ fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0" }}
              >
                {item.icon}
              </span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
};
