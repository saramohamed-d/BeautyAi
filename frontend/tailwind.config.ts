import type { Config } from "tailwindcss";

/**
 * BeautyAI design tokens — the 2026-10 redesign (rose pink, soft blush
 * backgrounds, serif display headings), see docs/design.md.
 *
 * `primary.DEFAULT` (#D6336C) is the darkest pink that still looks like
 * the mock-up's hot pink while passing WCAG AA with white text (4.6:1),
 * so it is used for buttons. `primary.dark` is for pink text on white.
 * `primary.accent` is decoration only (icons, illustrations, outlines).
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#FFF8F9",
        surface: "#FFFFFF",
        ink: "#2A1F2D",
        "ink-muted": "#6E6270",
        border: "#F3E3E8",
        primary: {
          DEFAULT: "#D6336C",
          dark: "#B0255A",
          accent: "#F06A95",
          soft: "#FDECF1",
          line: "#F6B8CB",
        },
        blush: "#FCE4EC",
        lavender: { soft: "#F1E9F7" },
        sage: { DEFAULT: "#4D6A55", soft: "#E2ECE4" },
        sky: { soft: "#E5EFF2" },
        gold: { DEFAULT: "#9A6E24", star: "#BD8C39", soft: "#F6EEDD" },
      },
      fontFamily: {
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
        // Display headings ("Smarter Care."). Arabic falls back to the body face.
        display: ["var(--font-display)", "serif"],
      },
      borderRadius: {
        card: "18px",
        field: "13px",
        tile: "15px",
      },
      boxShadow: {
        app: "0 20px 70px rgba(80, 50, 60, 0.15)",
        card: "0 6px 24px rgba(214, 51, 108, 0.07)",
        pink: "0 8px 20px rgba(214, 51, 108, 0.28)",
      },
    },
  },
  plugins: [],
};

export default config;
