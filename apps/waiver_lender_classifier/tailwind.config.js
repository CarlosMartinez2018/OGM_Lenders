/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#060e1a',
          900: '#0a1628',
          800: '#0f2040',
          700: '#1a3150',
          600: '#1e3a5f',
          500: '#264a78',
          400: '#3d6494',
          300: '#5b7fb0',
          200: '#8aa5c8',
          100: '#c0d0e4',
          50:  '#eef2f8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card:       '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.05)',
        'card-hover':'0 4px 12px rgba(10,22,40,0.12)',
        modal:      '0 20px 40px rgba(10,22,40,0.18)',
        drawer:     '-4px 0 24px rgba(10,22,40,0.12)',
      },
      borderColor: {
        DEFAULT: '#e2e8f0',
      },
    },
  },
  plugins: [],
}
