/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Archivo"', '"Arial Black"', "Impact", "system-ui", "sans-serif"],
      },
      colors: {
        primary: "#f2545b",
        dark: "#07130e",
        card: "#0e2419",
        accent: "#f2545b",
        ink: "#07130e",
        pitch: "#0e2419",
        turf: "#163626",
        line: "#24503a",
        chalk: "#f3efe4",
        signal: "#f2545b",
        leaf: "#34c077",
        gold: "#f2c14e",
      },
    },
  },
  plugins: [],
}