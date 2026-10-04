// Recharts draws SVG with literal colors, so the palette is mirrored here.
// Keep in sync with the CSS variables in app/globals.css.
export const chartColors = {
  surface: "#0e1f2e",
  text: "#dce8f5",
  textMuted: "#6b8aaa",
  accent: "#0ea5e9",
  border: "#1e3448",
  success: "#10b981",
  warning: "#f59e0b",
  danger: "#f43f5e",
  // bars that should recede next to the accent ones
  barMuted: "#3d5873",
} as const;
