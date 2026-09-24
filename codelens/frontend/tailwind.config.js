/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // GitHub dark theme palette
        gh: {
          bg: '#0d1117',
          surface: '#161b22',
          surface2: '#21262d',
          border: '#30363d',
          text: '#c9d1d9',
          muted: '#8b949e',
          link: '#58a6ff',
          green: '#238636',
          greenHover: '#2ea043',
          danger: '#da3633',
          orange: '#d29922',
          purple: '#8b949e',
          // Syntax highlights
          keyword: '#ff7b72',
          string: '#a5d6ff',
          comment: '#8b949e',
          number: '#79c0ff',
          func: '#d2a8ff',
        }
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['"SFMono-Regular"', 'Menlo', 'Monaco', 'Consolas', '"Liberation Mono"', '"Courier New"', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-in-out',
        'slide-in': 'slideIn 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
}
