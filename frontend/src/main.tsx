import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import './lib/i18n'; // initialise i18next before rendering
import App from './App';
import { restoreLanguage } from './lib/i18n';

// Restore saved language (sets document.dir for RTL)
restoreLanguage();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
