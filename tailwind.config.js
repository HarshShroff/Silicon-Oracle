/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./flask_app/templates/**/*.html"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        oracle: {
          primary: '#6366f1',
          secondary: '#8b5cf6',
          dark: '#0f172a',
          darker: '#020617',
          card: '#1e293b',
          border: '#334155',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}