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
        // One brand green carries the whole app (buttons, links, active
        // nav, logo mark) instead of a separate neon accent fighting it,
        // the way an established product's palette actually works.
        primary: "#22a35d",
        dark: "#0b120f",
        card: "#101913",
        accent: "#22a35d",
        ink: "#0b120f",
        pitch: "#101913",
        turf: "#18231c",
        line: "#273226",
        chalk: "#f3f1e9",
        // Vivid enough to read as text on the dark surfaces below AND to
        // carry black text on top of a solid button — one green doing
        // both jobs, the way a real brand's single accent colour does.
        signal: "#22a35d",
        leaf: "#3bbf79",
        gold: "#b4902f",
        danger: "#b3372c",
      },
    },
  },
  plugins: [],
}