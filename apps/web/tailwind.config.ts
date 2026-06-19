import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        ap: {
          blue: "#1F8FE3",
          "blue-hover": "#4FB0EF",
          "blue-deep": "#0E6BB8",
          "blue-soft": "rgba(31,143,227,0.12)",
          black: "#0A0F1A",
          surface: "#0F1623",
          surface2: "#15202F",
          surface3: "#1D2A3C",
          text: "#F5F7FA",
          "text-muted": "#9CA3B0",
          "text-faint": "#566377",
          success: "#3ECF8E",
          danger: "#FF4D5E",
          warning: "#FFB020",
          info: "#5AC8D4",
        },
      },
    },
  },
} satisfies Config;
