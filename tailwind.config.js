/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./felix/**/*.{html,js}", "./templates/**/*.{html,js}"],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}