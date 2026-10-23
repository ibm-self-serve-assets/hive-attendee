/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        hive: {
          navy: '#031040',
          blue: '#2850B8',
          accent: '#6FA1FE',
          border: '#CCDDFF',
          pale: '#E6EEFF',
          surface: '#F4F7FC',
        }
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
