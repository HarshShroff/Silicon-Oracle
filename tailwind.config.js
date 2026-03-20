/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./flask_app/templates/**/*.html"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Top-level aliases for command_center shorthand classes
        gain:  '#4ade80',
        loss:  '#f87171',
        'text-1': '#e2e8f0',
        'text-2': '#94a3b8',
        'text-3': '#64748b',
        'text-4': '#475569',
        oracle: {
          void:     '#040410',
          base:     '#070711',
          surface:  '#0d0d1a',
          card:     '#0f1729',
          elevated: '#111827',
          border:   '#1e2d3d',
          'border-strong': '#334155',
          // brand violet
          primary:  '#a78bfa',   // violet-400  — text, icons, highlights
          accent:   '#7c3aed',   // violet-600  — CTA buttons
          dim:      '#4c1d95',   // violet-900  — hover fills
          muted:    '#2e1065',   // violet-950  — subtle tints
          // semantic market colours
          gain:     '#4ade80',
          loss:     '#f87171',
          warn:     '#fbbf24',
          info:     '#38bdf8',
          // text hierarchy
          'text-1': '#e2e8f0',
          'text-2': '#94a3b8',
          'text-3': '#64748b',
          'text-4': '#475569',
          'text-5': '#334155',
        }
      },
      fontFamily: {
        sans: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '1rem' }],
      },
      animation: {
        'pulse-dot': 'pulseDot 1.5s ease-in-out infinite',
        'fade-in':   'fadeIn 0.3s ease-out',
        'slide-up':  'slideUp 0.3s ease-out',
      },
      keyframes: {
        pulseDot: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.35' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
