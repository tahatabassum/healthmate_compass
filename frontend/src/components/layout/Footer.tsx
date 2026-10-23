import React from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldAlert, PhoneCall } from 'lucide-react';

export const Footer: React.FC = () => {
  const { t } = useTranslation();

  return (
    <footer className="bg-slate-900 text-slate-400 py-8 px-4 sm:px-6 lg:px-8 mt-auto border-t border-slate-800">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Prominent Medical Disclaimer */}
        <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div className="text-xs text-slate-300 leading-relaxed">
              <span className="font-semibold text-white uppercase tracking-wider block mb-0.5">
                Medical Disclaimer:
              </span>
              {t(
                'disclaimer.text',
                'HealthMate gives clinical information, not a medical diagnosis. Always consult a qualified physician for medical decisions.'
              )}
            </div>
          </div>

          <a
            href="tel:1122"
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-red-600/90 hover:bg-red-600 text-white text-xs font-bold shrink-0 transition-colors shadow-xs"
          >
            <PhoneCall className="w-3.5 h-3.5 animate-pulse" />
            <span>Emergency: Rescue 1122</span>
          </a>
        </div>

        {/* Bottom Credits & Tech Details */}
        <div className="flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400 gap-4 pt-4 border-t border-slate-800/60">
          <p>© 2026 HealthMate Compass • Himmatkaar x HacktoberFest'26 Faisalabad</p>
          <p className="flex items-center gap-3">
            <span>Powered by Gemma 4 (Gemini API)</span>
            <span>•</span>
            <span>Google Places</span>
            <span>•</span>
            <span>Supabase pgvector</span>
          </p>
        </div>
      </div>
    </footer>
  );
};
