/** ASTRA application design system: mild green + cream. Tokens are CSS variables (src/styles/tokens.css). */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--background)", bg2: "var(--background-secondary)", surface: "var(--surface)", surface2: "var(--surface-secondary)",
        primary: "var(--primary)", "primary-dark": "var(--primary-dark)", "primary-light": "var(--primary-light)",
        sage: "var(--sage)", "sage-soft": "var(--sage-soft)", cream: "var(--cream)", ivory: "var(--ivory)",
        ink: "var(--ink)", ink2: "var(--ink-secondary)", muted: "var(--muted)",
        success: "var(--success)", warning: "var(--warning)", danger: "var(--danger)", info: "var(--info)",
      },
      borderColor: { DEFAULT: "var(--border)", strong: "var(--border-strong)" },
      borderRadius: { sm: "var(--radius-sm)", md: "var(--radius-md)", lg: "var(--radius-lg)", xl: "var(--radius-xl)" },
      boxShadow: { soft: "var(--shadow-soft)", card: "var(--shadow-card)" },
      fontFamily: {
        display: ['"Instrument Serif"', "Georgia", "serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
