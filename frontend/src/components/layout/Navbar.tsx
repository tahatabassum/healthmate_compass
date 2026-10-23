import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { setLanguage } from '../../lib/i18n';
import { Activity, FileText, MessageSquare, MapPin, Brain, Globe, User } from 'lucide-react';

interface NavbarProps {
  currentPatient: string;
  onPatientChange: (patientName: string) => void;
  patients: Array<{ id: string; full_name: string; relation: string }>;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentPatient,
  onPatientChange,
  patients,
}) => {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const currentLang = i18n.language.startsWith('ur') ? 'ur' : 'en';

  const toggleLanguage = () => {
    const nextLang = currentLang === 'en' ? 'ur' : 'en';
    setLanguage(nextLang);
  };

  const navLinks = [
    { to: '/', label: t('nav.translate', 'Translate'), icon: FileText },
    { to: '/consult', label: t('nav.ai_consult', 'AI Consult'), icon: MessageSquare },
    { to: '/doctors', label: t('nav.find_doctor', 'Find Doctor'), icon: MapPin },
    { to: '/memory', label: t('nav.memory', 'Health Memory'), icon: Brain },
  ];

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200/80 shadow-xs transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-10 h-10 rounded-xl bg-teal-600 flex items-center justify-center text-white shadow-md shadow-teal-600/20 group-hover:scale-105 transition-transform">
              <Activity className="w-6 h-6 stroke-[2.5]" />
            </div>
            <div>
              <span className="font-bold text-lg text-slate-900 tracking-tight block leading-none">
                {t('app.name', 'HealthMate Compass')}
              </span>
              <span className="text-[11px] font-medium text-teal-600 tracking-wider uppercase block mt-0.5">
                Gemma 4 Clinical
              </span>
            </div>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map(({ to, label, icon: Icon }) => {
              const isActive = location.pathname === to;
              return (
                <Link
                  key={to}
                  to={to}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-teal-50 text-teal-700 shadow-xs font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-teal-600' : 'text-slate-400'}`} />
                  {label}
                </Link>
              );
            })}
          </nav>

          {/* Right Actions: Patient Switcher & Language Toggle */}
          <div className="flex items-center gap-2.5">
            {/* Patient Switcher */}
            <div className="relative flex items-center bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700">
              <User className="w-3.5 h-3.5 text-slate-400 mr-1.5" />
              <select
                aria-label="Active Patient Profile"
                value={currentPatient}
                onChange={(e) => onPatientChange(e.target.value)}
                className="bg-transparent font-medium focus:outline-none cursor-pointer pr-1"
              >
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.relation})
                  </option>
                ))}
              </select>
            </div>

            {/* Language Toggle */}
            <button
              onClick={toggleLanguage}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold transition-all shadow-xs"
              title="Switch Language / زبان تبدیل کریں"
            >
              <Globe className="w-3.5 h-3.5 text-teal-600" />
              <span>{currentLang === 'en' ? 'اردو' : 'English'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Bottom Navigation */}
      <div className="md:hidden flex items-center justify-around bg-white border-t border-slate-200 py-2 fixed bottom-0 left-0 right-0 z-50 shadow-lg">
        {navLinks.map(({ to, label, icon: Icon }) => {
          const isActive = location.pathname === to;
          return (
            <Link
              key={to}
              to={to}
              className={`flex flex-col items-center gap-1 text-[11px] font-medium py-1 px-3 rounded-md ${
                isActive ? 'text-teal-600 font-bold' : 'text-slate-500'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span>{label}</span>
            </Link>
          );
        })}
      </div>
    </header>
  );
};
