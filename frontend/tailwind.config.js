/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        gold: {
          50: "#fdf8e7",
          100: "#faf0c4",
          400: "#d4af37",
          500: "#c19a2b",
          600: "#a07d1f",
          700: "#7a5e16",
        },
      },
    },
  },
  plugins: [],
};
