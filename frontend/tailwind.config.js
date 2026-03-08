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
        'accent-dim': 'rgba(34, 211, 238, 0.15)',
        success: '#4ade80',
        warning: '#facc15',
        danger: '#f87171',
      },
      backdropBlur: {
        glass: '16px',
      },
      animation: {
        'voice-bar': 'voice-bar 0.6s ease-in-out infinite',
        'breathe': 'breathe 4s ease-in-out infinite',
        'status-breathe': 'status-breathe 3s ease-in-out infinite',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
