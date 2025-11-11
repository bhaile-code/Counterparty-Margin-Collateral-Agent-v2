/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#1A1F3A',  // Navy
          hover: '#0F1426',
        },
        success: '#2ECC71',
        warning: '#F39C12',
        error: '#E74C3C',
        gray: {
          50: '#F8F9FA',
          100: '#ECF0F1',
          200: '#BDC3C7',
          300: '#95A5A6',
          400: '#7F8C8D',
          500: '#4A5F7F',
          600: '#2C3E50',
        }
      },
      fontFamily: {
        mono: ['Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
