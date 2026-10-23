/**
 * i18n configuration for HealthMate Compass.
 * Supports English (LTR) and Urdu (RTL) with instant document reflow.
 * Import this file once in main.tsx before rendering the app.
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from '../../locales/en.json';
import ur from '../../locales/ur.json';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      ur: { translation: ur },
    },
    lng: 'en',
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
  });

/** Switch language and update the document dir/lang attributes for RTL support. */
export function setLanguage(lang: 'en' | 'ur'): void {
  i18n.changeLanguage(lang);
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ur' ? 'rtl' : 'ltr';
  localStorage.setItem('hmc_lang', lang);
}

/** Restore language from localStorage on app boot. */
export function restoreLanguage(): void {
  const saved = localStorage.getItem('hmc_lang') as 'en' | 'ur' | null;
  if (saved) setLanguage(saved);
}

export default i18n;
