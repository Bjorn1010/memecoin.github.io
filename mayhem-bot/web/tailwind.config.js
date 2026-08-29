/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0c12",
        panel: "#12151e",
        panel2: "#181c28",
        panel3: "#1e2330",
        border: "#242938",
        borderLight: "#2f3547",
        up: "#00d97e",
        upDim: "#0a3b28",
        down: "#ff4d5e",
        downDim: "#3d1620",
        accent: "#8b6cff",
        accentDim: "#241d47",
        warn: "#ffb020",
        muted: "#7b839a",
        dim: "#4b5163",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.4), 0 8px 24px -12px rgba(0,0,0,0.5)",
        glow: "0 0 0 1px rgba(139,108,255,0.3), 0 0 24px -4px rgba(139,108,255,0.35)",
      },
      backgroundImage: {
        "radial-fade": "radial-gradient(60% 50% at 50% 0%, rgba(139,108,255,0.08), transparent)",
      },
    },
  },
  plugins: [],
};
