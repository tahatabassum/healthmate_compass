import React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, PhoneCall } from 'lucide-react';

interface EmergencyBannerProps {
  instructionEn?: string;
  instructionUr?: string;
  matchedTerm?: string;
  onDismiss?: () => void;
}

export const EmergencyBanner: React.FC<EmergencyBannerProps> = ({
  instructionEn,
  instructionUr,
  matchedTerm,
  onDismiss,
}) => {
  const { t, i18n } = useTranslation();
  const isUrdu = i18n.language.startsWith('ur');

  return (
    <div className="bg-red-50 border-2 border-red-500 rounded-2xl p-4 sm:p-5 shadow-lg shadow-red-500/10 mb-6 animate-in fade-in slide-in-from-top-4 duration-300">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-red-600 text-white flex items-center justify-center shrink-0 shadow-md shadow-red-600/30">
            <AlertTriangle className="w-6 h-6 animate-bounce" />
          </div>
          <div>
            <h3 className="font-bold text-red-900 text-base flex items-center gap-2">
              <span>{t('emergency.banner_title', 'This sounds like a medical emergency!')}</span>
              {matchedTerm && (
                <span className="text-xs bg-red-200 text-red-800 font-mono px-2 py-0.5 rounded-full font-normal">
                  {matchedTerm}
                </span>
              )}
            </h3>
            <p className="text-sm text-red-800 mt-1 leading-relaxed">
              {isUrdu && instructionUr
                ? instructionUr
                : instructionEn ||
                  t(
                    'emergency.instruction',
                    'Please call Rescue 1122 immediately or visit the nearest hospital emergency room.'
                  )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <a
            href="tel:1122"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-red-600 hover:bg-red-700 active:scale-95 text-white font-bold text-sm shadow-md shadow-red-600/30 transition-all"
          >
            <PhoneCall className="w-4 h-4 animate-pulse" />
            <span>{t('emergency.call_now', 'Call Rescue 1122')}</span>
          </a>
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="text-xs text-red-600 hover:text-red-800 font-medium px-2 py-1"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
