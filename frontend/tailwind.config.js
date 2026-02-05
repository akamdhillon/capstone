/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        mirror: '#000000',
        accent: '#22d3ee',
        success: '#4ade80',
        warning: '#facc15',
        danger: '#f87171',
      },
      backdropBlur: {
        glass: '12px',
      },
    },
  },
  plugins: [],
}
