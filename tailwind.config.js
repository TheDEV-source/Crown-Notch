/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        obsidian: "rgba(15, 15, 18, 0.88)",
      },
    },
  },
  plugins: [],
};
