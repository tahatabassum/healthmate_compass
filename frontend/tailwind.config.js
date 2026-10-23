/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  // RTL support: logical properties are used throughout the components;
  // Tailwind itself does not need a special RTL plugin when we use
  // CSS logical properties (margin-inline-start, padding-block-end, etc.)
  darkMode: 'class',
  theme: {
    extend: {
      // ── Clinical Calm design system tokens ─────────────────────────────────
      // Source: /design/clinical_calm/DESIGN.md
      colors: {
        // Material You surface tokens
        surface:                   '#f8f9ff',
        'surface-dim':             '#cbdbf5',
        'surface-bright':          '#f8f9ff',
        'surface-container-lowest':'#ffffff',
        'surface-container-low':   '#eff4ff',
        'surface-container':       '#e5eeff',
        'surface-container-high':  '#dce9ff',
        'surface-container-highest':'#d3e4fe',
        'on-surface':              '#0b1c30',
        'on-surface-variant':      '#3e4947',
        'inverse-surface':         '#213145',
        'inverse-on-surface':      '#eaf1ff',
        outline:                   '#6e7977',
        'outline-variant':         '#bdc9c6',
        'surface-tint':            '#006a63',
        'surface-variant':         '#d3e4fe',
        // Primary teal
        primary:                   '#005c55',
        'on-primary':              '#ffffff',
        'primary-container':       '#0f766e',
        'on-primary-container':    '#a3faef',
        'inverse-primary':         '#80d5cb',
        'primary-fixed':           '#9cf2e8',
        'primary-fixed-dim':       '#80d5cb',
        'on-primary-fixed':        '#00201d',
        'on-primary-fixed-variant':'#00504a',
        // Secondary slate
        secondary:                 '#565e74',
        'on-secondary':            '#ffffff',
        'secondary-container':     '#dae2fd',
        'on-secondary-container':  '#5c647a',
        'secondary-fixed':         '#dae2fd',
        'secondary-fixed-dim':     '#bec6e0',
        'on-secondary-fixed':      '#131b2e',
        'on-secondary-fixed-variant':'#3f465c',
        // Tertiary green
        tertiary:                  '#005f26',
        'on-tertiary':             '#ffffff',
        'tertiary-container':      '#007a33',
        'on-tertiary-container':   '#a1ffad',
        'tertiary-fixed':          '#7ffc97',
        'tertiary-fixed-dim':      '#62df7d',
        'on-tertiary-fixed':       '#002109',
        'on-tertiary-fixed-variant':'#005320',
        // Error
        error:                     '#ba1a1a',
        'on-error':                '#ffffff',
        'error-container':         '#ffdad6',
        'on-error-container':      '#93000a',
        // Background aliases
        background:                '#f8f9ff',
        'on-background':           '#0b1c30',

        // ── Semantic design tokens (from DESIGN.md) ──────────────────────
        // Typography hierarchy
        'trust-navy':              '#0F172A',
        'slate-body':              '#334155',
        'secondary-slate':         '#64748B',
        'muted-slate':             '#94A3B8',
        'app-bg':                  '#F8FAFC',
        'card-surface':            '#FFFFFF',
        'divider':                 '#E2E8F0',

        // Medical status (always paired with icon + text, never color alone)
        'status-normal-text':      '#16A34A',
        'status-normal-bg':        '#DCFCE7',
        'status-low-text':         '#2563EB',
        'status-low-bg':           '#DBEAFE',
        'status-high-text':        '#D97706',
        'status-high-bg':          '#FEF3C7',
        'status-critical-text':    '#DC2626',
        'status-critical-bg':      '#FEE2E2',

        // Interactive teal (primary actions)
        'teal':                    '#0F766E',
        'teal-hover':              '#115E59',
        'teal-tint':               '#F0FDFA',
        'teal-subtle':             '#CCFBF1',
      },

      fontFamily: {
        sans:  ['Inter', 'ui-sans-serif', 'system-ui'],
        // For Urdu content: applied via lang="ur" selector in global CSS
        urdu:  ['Noto Nastaliq Urdu', 'Urdu Typesetting', 'serif'],
      },

      fontSize: {
        // Design token type scale
        'headline-xl':  ['2.25rem', { lineHeight: '2.75rem', letterSpacing: '-0.02em', fontWeight: '700' }],
        'headline-xl-m':['1.75rem', { lineHeight: '2.25rem', letterSpacing: '-0.01em', fontWeight: '700' }],
        'headline-lg':  ['1.75rem', { lineHeight: '2.25rem', letterSpacing: '-0.01em', fontWeight: '600' }],
        'headline-lg-m':['1.375rem',{ lineHeight: '1.875rem', fontWeight: '600' }],
        'headline-md':  ['1.25rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        'headline-sm':  ['1rem',    { lineHeight: '1.5rem',  fontWeight: '600' }],
        'body-lg':      ['1rem',    { lineHeight: '1.625rem', fontWeight: '400' }],
        'body-md':      ['0.875rem',{ lineHeight: '1.375rem', fontWeight: '400' }],
        'body-sm':      ['0.75rem', { lineHeight: '1.125rem', fontWeight: '400' }],
        'label-lg':     ['0.875rem',{ lineHeight: '1.25rem',  fontWeight: '600' }],
        'label-md':     ['0.75rem', { lineHeight: '1rem',     fontWeight: '500', letterSpacing: '0.01em' }],
        'label-sm':     ['0.625rem',{ lineHeight: '0.875rem', fontWeight: '600', letterSpacing: '0.02em' }],
      },

      borderRadius: {
        // Design token radius scale (from DESIGN.md)
        sm:      '0.25rem',
        DEFAULT: '0.5rem',
        md:      '0.75rem',
        lg:      '1rem',
        xl:      '1.5rem',
        full:    '9999px',
      },

      spacing: {
        // Design token spacing
        'gutter':          '1rem',
        'gutter-desktop':  '1.5rem',
        'margin':          '1rem',
        'margin-desktop':  '2rem',
        'space-xs':        '0.25rem',
        'space-sm':        '0.5rem',
        'space-md':        '1rem',
        'space-lg':        '1.5rem',
        'space-xl':        '2rem',
        // Sidebar width (desktop)
        'sidebar':         '260px',
        // Bottom nav height (mobile)
        'bottom-nav':      '64px',
        // Minimum tap target
        'tap':             '44px',
      },

      boxShadow: {
        // Elevation levels from DESIGN.md
        'level-1': '0 1px 3px 0 rgba(15,23,42,0.04), 0 1px 2px -1px rgba(15,23,42,0.02)',
        'level-2': '0 4px 6px -1px rgba(15,23,42,0.06), 0 2px 4px -2px rgba(15,23,42,0.04)',
        'level-3': '0 20px 25px -5px rgba(15,23,42,0.08), 0 8px 10px -6px rgba(15,23,42,0.03)',
        'emergency': '0 1px 3px 0 rgba(220,38,38,0.08), 0 1px 2px -1px rgba(220,38,38,0.04)',
      },

      screens: {
        // Design breakpoints
        'xs':  '360px',
        'sm':  '390px',
        'md':  '768px',
        'lg':  '1024px',
        'xl':  '1280px',
        '2xl': '1440px',
      },
    },
  },
  plugins: [],
}
