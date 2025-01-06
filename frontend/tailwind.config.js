/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class', // We'll toggle dark mode by applying a "dark" class to the html body
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      // We use grayscale theme
      colors: {
        gray: {
          50:  '#fafafa',
          100: '#f4f4f5',
          200: '#e4e4e7',
          300: '#d4d4d8',
          400: '#a1a1aa',
          500: '#71717a',
          600: '#52525b',
          700: '#3f3f46',
          800: '#27272a',
          900: '#18181b'
        }
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: 'none',
          },
        },
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'share-click': {
          '0%, 100%': { backgroundColor: 'rgb(55 65 81)' }, // bg-gray-700
          '50%': { backgroundColor: 'rgb(31 41 55)' }, // bg-gray-800
        }
      },
      animation: {
        'fade-in': 'fade-in 0.25s ease-out',
        'share-click': 'share-click 1s ease-in-out'
      }
    }
  },
  plugins: [
    require('@tailwindcss/typography'),
  ]
}; 