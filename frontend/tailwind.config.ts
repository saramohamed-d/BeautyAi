import type { Config } from "tailwindcss";

/**
 * BeautyAI design tokens — taken from the approved interactive demo
 * (beauty_ai_final_interactive_demo.html) and adjusted for contrast.
 *
 * The demo's bright pink (#e98da0) only reaches 2.4:1 against white text,
 * so it is kept as `primary.accent` for decoration only (progress fills,
 * selected outlines, logo). Buttons and text links use `primary.DEFAULT`
 * / `primary.dark`, which pass WCAG AA with white / on white.
 * See docs/design.md.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#FBF7F5",
        surface: "#FFFFFF",
        ink: "#322D32",
        "ink-muted": "#6F676C",
        border: "#EEE7E5",
        primary: {
          DEFAULT: "#B9546B",
          dark: "#9E4459",
          accent: "#E98DA0",
          soft: "#F8E4E8",
          line: "#E9A8B5",
        },
        lavender: { soft: "#E9E3F3" },
        sage: { DEFAULT: "#4D6A55", soft: "#E2ECE4" },
        sky: { soft: "#E5EFF2" },
        gold: { DEFAULT: "#9A6E24", star: "#BD8C39", soft: "#F6EEDD" },
      },
      fontFamily: {
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "18px",
        field: "13px",
        tile: "15px",
      },
      boxShadow: {
        app: "0 20px 70px rgba(80, 50, 60, 0.15)",
      },
    },
  },
  plugins: [],
};

export default config;
