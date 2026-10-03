import type { Config } from "tailwindcss";

// Colors come from the hex CSS variables in app/globals.css. color-mix keeps
// Tailwind opacity modifiers working (e.g. bg-accent/15) with plain hex vars.
const themeColor = (name: string) =>
  `color-mix(in srgb, var(--color-${name}) calc(<alpha-value> * 100%), transparent)`;

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: themeColor("bg"),
        surface: themeColor("surface"),
        surface2: themeColor("surface-2"),
        border: themeColor("border"),
        text: themeColor("text"),
        muted: themeColor("muted"),
        accent: {
          DEFAULT: themeColor("accent"),
          hover: themeColor("accent-hover"),
        },
        success: themeColor("success"),
        danger: themeColor("danger"),
        warning: themeColor("warning"),
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
