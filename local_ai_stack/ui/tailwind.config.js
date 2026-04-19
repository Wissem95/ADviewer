/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#1e1e2e",
        panel: "#181825",
        border: "#313244",
        text: "#cdd6f4",
        muted: "#6c7086",
        accent: "#89b4fa",
        success: "#a6e3a1",
        warning: "#f9e2af",
        error: "#f38ba8",
      },
    },
  },
  plugins: [],
};
