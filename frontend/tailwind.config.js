/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      colors: {
        ink: "#0f1720",
        slate: {
          850: "#172033",
        },
        accent: "#0ea5e9",
        good: "#10b981",
        bad: "#ef4444",
        warn: "#f59e0b",
      },
    },
  },
  plugins: [],
}
