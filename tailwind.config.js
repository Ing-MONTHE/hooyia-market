/**
 * ═══════════════════════════════════════════════════════════════
 * HooYia Market — Tailwind CSS Config v3.0
 * ═══════════════════════════════════════════════════════════════
 *
 * Ce fichier étend le thème Tailwind avec les tokens du design
 * system HooYia Market. Toutes les valeurs sont alignées avec
 * les variables CSS de custom.css.
 *
 * USAGE BUILD :
 *   Développement : npm run tw:dev   (watch + rebuild auto)
 *   Production    : npm run tw:build (minifié + purgé)
 *
 * PURGE CSS :
 *   Tailwind scanne les fichiers déclarés dans "content" et
 *   supprime toutes les classes non utilisées en production.
 *   → Résultat : un CSS final très léger (~10-20kb).
 * ═══════════════════════════════════════════════════════════════
 */

/** @type {import('tailwindcss').Config} */
module.exports = {

  /* ── Fichiers à scanner pour la purge CSS ── */
  content: [
    './templates/**/*.html',  /* Tous les templates Django */
    './static/js/**/*.js',    /* JS qui injecte des classes dynamiquement */
  ],

  /* ── Dark mode désactivé (non prévu dans la v1) ── */
  darkMode: 'class',

  theme: {
    extend: {

      /* ── COULEURS ──
         Alignées exactement avec les variables CSS de custom.css.
         Usage Tailwind : bg-brand-600, text-accent, border-line...  */
      colors: {
        brand: {
          50:  '#eff4ff',  /* bg-brand-50  : hover léger, badge bg */
          100: '#dce7fd',  /* bg-brand-100 : badge, highlight */
          200: '#b8d0fb',  /* border-brand-200 : bordure bleue légère */
          500: '#1E3A8A',  /* bg-brand-500 : boutons, liens */
          600: '#0D1F5C',  /* bg-brand-600 : titres, footer texte */
          700: '#091747',  /* bg-brand-700 : footer fond */
        },
        accent: {
          light:   '#ffedd5', /* bg-accent-light : badge promo */
          DEFAULT: '#F97316', /* bg-accent : CTA principal */
          dark:    '#ea6000', /* bg-accent-dark : hover CTA */
        },
        bg: {
          DEFAULT: '#F4F7FC', /* bg-bg : fond global des pages */
        },
        surface: {
          DEFAULT: '#ffffff', /* bg-surface : cartes, inputs */
          2:       '#f9fafb', /* bg-surface-2 : hover, alternance */
          3:       '#f0f3fa', /* bg-surface-3 : sections légères */
        },
        ink: {
          DEFAULT:   '#0F1923', /* text-ink : texte principal */
          secondary: '#4A5568', /* text-ink-secondary : descriptions */
          muted:     '#8898AA', /* text-ink-muted : dates, placeholders */
        },
        line: {
          DEFAULT: '#E2E8F0', /* border-line : bordure par défaut */
          strong:  '#d1dae8', /* border-line-strong : bordure marquée */
        },
        /* Couleurs sémantiques pour les statuts et alertes */
        status: {
          success:      '#10b981',
          'success-bg': '#ecfdf5',
          warning:      '#f59e0b',
          'warning-bg': '#fffbeb',
          error:        '#ef4444',
          'error-bg':   '#fef2f2',
          info:         '#1E3A8A',
          'info-bg':    '#dce7fd',
        },
      },

      /* ── TYPOGRAPHIE ──
         Police unique : Poppins pour titres ET corps.
         Simplicité et cohérence visuelle maximale. */
      fontFamily: {
        sans:    ['Poppins', 'system-ui', 'sans-serif'], /* Override la police par défaut Tailwind */
        display: ['Poppins', 'system-ui', 'sans-serif'], /* Titres hero, grands displays */
        body:    ['Poppins', 'system-ui', 'sans-serif'], /* Texte courant */
      },

      /* ── TAILLES DE TEXTE ──
         Échelle personnalisée alignée avec le design (en rem). */
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],    /* 11px — labels très petits */
        xs:    ['0.75rem',   { lineHeight: '1.125rem' }], /* 12px — badges, captions */
        sm:    ['0.8125rem', { lineHeight: '1.25rem' }],  /* 13px — labels, btn-sm */
        base:  ['0.9375rem', { lineHeight: '1.5rem' }],   /* 15px — texte courant */
        lg:    ['1.0625rem', { lineHeight: '1.625rem' }], /* 17px — sous-titres */
        xl:    ['1.1875rem', { lineHeight: '1.75rem' }],  /* 19px — h4 */
        '2xl': ['1.375rem',  { lineHeight: '1.875rem' }], /* 22px — h3 */
        '3xl': ['1.625rem',  { lineHeight: '2.125rem' }], /* 26px — h2 */
        '4xl': ['2rem',      { lineHeight: '2.5rem' }],   /* 32px — h1 desktop */
        '5xl': ['2.5rem',    { lineHeight: '3rem' }],     /* 40px — hero */
        '6xl': ['3rem',      { lineHeight: '3.5rem' }],   /* 48px — hero large */
      },

      /* ── BORDER RADIUS ──
         Cohérent avec le style Poppins (arrondi mais pas excessif). */
      borderRadius: {
        sm:      '0.375rem',  /* 6px  — badges, petits éléments */
        DEFAULT: '0.5rem',    /* 8px  — boutons, inputs */
        md:      '0.75rem',   /* 12px — cartes */
        lg:      '1rem',      /* 16px — modales, panneaux */
        xl:      '1.25rem',   /* 20px — sections */
        '2xl':   '1.5rem',    /* 24px — hero cards */
      },

      /* ── OMBRES ──
         Toutes dans les tons bleu marine — cohérence avec la charte.
         Plus douces que les ombres Tailwind par défaut. */
      boxShadow: {
        card:      '0 1px 3px rgba(13,31,92,0.06), 0 1px 2px rgba(13,31,92,0.04)', /* Carte au repos */
        'card-md': '0 4px 16px rgba(13,31,92,0.09)',  /* Carte au hover */
        'card-lg': '0 8px 32px rgba(13,31,92,0.13)',  /* Modale, dropdown */
        accent:    '0 4px 14px rgba(249,115,22,0.35)', /* Bouton primary */
      },

      /* ── ESPACEMENTS SUPPLÉMENTAIRES ──
         Valeurs intermédiaires absentes de l'échelle Tailwind par défaut. */
      spacing: {
        '4.5': '1.125rem', /* 18px — entre sm(16) et md(20) */
        '13':  '3.25rem',  /* 52px */
        '18':  '4.5rem',   /* 72px — sections */
        '22':  '5.5rem',   /* 88px */
      },

      /* ── LARGEUR MAX ── */
      maxWidth: {
        container: '1400px', /* Largeur max du contenu — même valeur que .container CSS */
      },

      /* ── COURBES D'ACCÉLÉRATION ── */
      transitionTimingFunction: {
        'out-expo':    'cubic-bezier(0.16, 1, 0.3, 1)',    /* Sortie rapide — dropdowns */
        'in-out-quad': 'cubic-bezier(0.45, 0, 0.55, 1)',   /* Standard — hovers */
      },

      /* ── KEYFRAMES ──
         Animations utilisées dans les composants Django templates. */
      keyframes: {
        /* Apparition depuis le bas — cartes, sections au scroll */
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        /* Apparition depuis le haut — dropdowns navbar */
        'slide-down': {
          from: { opacity: '0', transform: 'translateY(-8px) scale(0.97)' },
          to:   { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        /* Entrée toast depuis la droite */
        'toast-in': {
          from: { opacity: '0', transform: 'translateX(110%)' },
          to:   { opacity: '1', transform: 'translateX(0)' },
        },
        /* Sortie toast vers la droite */
        'toast-out': {
          from: { opacity: '1', transform: 'translateX(0)' },
          to:   { opacity: '0', transform: 'translateX(110%)' },
        },
        /* Apparition modale — scale + fade */
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.94) translateY(10px)' },
          to:   { opacity: '1', transform: 'scale(1) translateY(0)' },
        },
      },

      /* ── ANIMATIONS (classes utilitaires) ──
         Usage : class="animate-fade-in" dans les templates */
      animation: {
        'fade-in':    'fade-in 0.2s ease-out both',
        'slide-down': 'slide-down 0.15s ease-out both',
        'toast-in':   'toast-in 0.28s cubic-bezier(0.16,1,0.3,1) both',
        'toast-out':  'toast-out 0.2s ease-in both',
        'scale-in':   'scale-in 0.2s cubic-bezier(0.16,1,0.3,1) both',
      },

    },
  },

  plugins: [],
}