import animatePlugin from "tailwindcss-animate";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Palette sobre & lisible — base sombre neutre, accent cyan + touche magenta.
        bg: "#0d0f14",
        panel: "#151823",
        "panel-2": "#1c2030",
        border: "#262c3d",
        "border-bright": "#3a4256",
        text: "#eef1f7",
        muted: "#9aa3b8",
        accent: "#34d8e6",
        "accent-dim": "#1a7e8c",
        magenta: "#ff5fa2",
        phosphor: "#34d399",
        danger: "#ff5f7a",
        success: "#34d399",
        warning: "#34d8e6",
        error: "#ff5f7a",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
        display: ["VT323", "JetBrains Mono", "monospace"],
      },
      boxShadow: {
        glow: "0 0 18px rgba(33,230,255,0.28)",
        "glow-magenta": "0 0 18px rgba(255,61,139,0.3)",
        "glow-green": "0 0 16px rgba(52,255,176,0.22)",
      },
      keyframes: {
        blink: { "0%,49%": { opacity: "1" }, "50%,100%": { opacity: "0" } },
        "pulse-glow": {
          "0%,100%": { opacity: "1", filter: "brightness(1)" },
          "50%": { opacity: "0.7", filter: "brightness(1.4)" },
        },
      },
      animation: {
        blink: "blink 1.05s steps(1) infinite",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
      },
    },
  },
  plugins: [animatePlugin],
};
