/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        lastica: ['Lastica', 'sans-serif'],
        horizon: ['Horizon', 'sans-serif'],
        archivoBlack: ['"Archivo Black"', 'sans-serif'],
        poppins: ['Poppins', 'sans-serif'],
        arialMtPro: ['"Arial MT Pro"', 'Arial', 'sans-serif'],
      },
      colors: {
        navy: '#1E2567',
        royal: '#2F3FA5',
        gold: '#C9A54A',
      },
    },
  },
  plugins: [],
}

