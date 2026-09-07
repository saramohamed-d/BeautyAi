import type { Config } from "tailwindcss";

// Design decision: Tailwind's `dir`-aware utilities (rtl:/ltr: variants
// via logical properties) plus the built-in `dir` support let one
// component tree serve both English (LTR) and Arabic (RTL) without
// separate stylesheets. Full RTL utility usage lands in Sprint 3-4 when
// real layouts are built; Sprint 0 just wires up the config.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        arabic: ["var(--font-arabic)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
