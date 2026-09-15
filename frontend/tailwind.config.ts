import type { Config } from "tailwindcss";

/**
 * BeautyAI design tokens.
 *
 * Deliberately not the generic "warm cream + terracotta" AI-default:
 * a dusty-rose primary (used only for CTAs/active states), a champagne
 * gold reserved for ratings/small accents, and sage green reserved
 * exclusively for confirmation/success states — one accent per job,
 * nothing decorative. See docs/design.md for the full rationale.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#FBF7F4",
        surface: "#FFFFFF",
        ink: "#2B2420",
        "ink-muted": "#8A7A72",
        primary: {
          DEFAULT: "#9C5B6E",
          dark: "#7E4657",
          soft: "#F3E1E6",
        },
        gold: {
          DEFAULT: "#BE9B5E",
          soft: "#F3EAD9",
        },
        sage: {
          DEFAULT: "#6E8B74",
          soft: "#E4ECE4",
        },
        border: "#ECE3DD",
      },
      fontFamily: {
        sans: ["var(--font-cairo)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        xl2: "1.25rem",
      },
    },
  },
  plugins: [],
};

export default config;
