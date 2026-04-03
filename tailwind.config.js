/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./flask_app/templates/**/*.html"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Semantic shorthands used in templates
        gain:  '#00C853',
        loss:  '#FF5252',
        gold:  '#F0C060',
        'text-1': '#FFFFFF',
        'text-2': '#D1D4DC',
        'text-3': '#B2B5BE',
        'text-4': '#787B86',

        oracle: {
          // Backgrounds
          void:     '#0B0C0F',
          base:     '#101010',
          surface:  '#131722',
          card:     '#1C1C1C',
          elevated: '#1E222D',
          ink:      '#0B0C0F',

          // Borders
          border:         '#2A2E39',
          'border-mid':   '#363C4E',
          'border-strong': '#4A5060',

          // Accents
          primary:  '#00C853',
          accent:   '#00C853',
          gold:     '#F0C060',
          rose:     '#FF5252',

          // Semantic market
          gain:     '#00C853',
          loss:     '#FF5252',
          warn:     '#F0C060',
          info:     '#5AB5E8',

          // Text hierarchy
          'text-1': '#FFFFFF',
          'text-2': '#D1D4DC',
          'text-3': '#B2B5BE',
          'text-4': '#787B86',
          'text-5': '#434651',
        }
      },

      fontFamily: {
        sans: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'Menlo', 'monospace'],
      },

      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '1rem' }],
      },

      borderRadius: {
        'xl':  '12px',
        '2xl': '16px',
        '3xl': '20px',
        '4xl': '24px',
      },

      boxShadow: {
        'glow-green': '0 0 20px rgba(0,200,83,0.25)',
        'glow-gold':  '0 0 20px rgba(240,192,96,0.25)',
        'glow-rose':  '0 0 20px rgba(255,82,82,0.25)',
        'card':       '0 4px 24px rgba(0,0,0,0.5)',
        'card-lg':    '0 8px 48px rgba(0,0,0,0.65)',
        '3xl':        '0 16px 64px rgba(0,0,0,0.7)',
      },

      animation: {
        'pulse-dot': 'pulseDot 1.5s ease-in-out infinite',
        'fade-in':   'fadeIn 0.3s ease-out',
        'slide-up':  'slideUp 0.3s ease-out',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
      },

      keyframes: {
        pulseDot: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.3' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 16px rgba(0,200,83,0.15)' },
          '50%':      { boxShadow: '0 0 32px rgba(0,200,83,0.35)' },
        },
      },

      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },

      transitionDuration: {
        '250': '250ms',
      },
    },
  },
  plugins: [],
}
