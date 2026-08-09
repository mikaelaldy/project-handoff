/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./web/index.html"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Plus Jakarta Sans", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        light: {
          bg: "#FFFFFF",
          surface: "#F8FAFC",
          card: "#FFFFFF",
          border: "#E2E8F0",
          borderHover: "#CBD5E1",
          heading: "#0F172A",
          body: "#475569",
          muted: "#64748B",
          amber: "#D97706",
          amberLight: "#FEF3C7",
          cyan: "#0284C7",
          cyanLight: "#E0F2FE",
          emerald: "#059669",
          emeraldLight: "#D1FAE5",
          violet: "#7C3AED",
          violetLight: "#EDE9FE",
          rose: "#E11D48",
        },
      },
    },
  },
  plugins: [],
};