import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],

  theme: {
    extend: {

      // ── Brand Colors ────────────────────────────────────────────────────────
      colors: {
        // Primary — electric blue
        primary: {
          50:  "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
          950: "#172554",
        },

        // Accent — violet
        accent: {
          50:  "#f5f3ff",
          100: "#ede9fe",
          200: "#ddd6fe",
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
          800: "#5b21b6",
          900: "#4c1d95",
          950: "#2e1065",
        },

        // Surface — dark UI backgrounds
        surface: {
          50:  "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
          950: "#020617",
        },

        // Fit score colors
        score: {
          excellent: "#10b981",   // green  — 8.0+
          good:      "#3b82f6",   // blue   — 6.0–7.9
          fair:      "#f59e0b",   // amber  — 4.0–5.9
          weak:      "#ef4444",   // red    — below 4.0
        },

        // Pipeline stage colors
        stage: {
          scraping:  "#06b6d4",   // cyan
          matching:  "#8b5cf6",   // violet
          scoring:   "#f59e0b",   // amber
          drafting:  "#10b981",   // green
          done:      "#3b82f6",   // blue
          error:     "#ef4444",   // red
        },
      },

      // ── Typography ───────────────────────────────────────────────────────────
      fontFamily: {
        sans:  ["Inter", "system-ui", "sans-serif"],
        mono:  ["JetBrains Mono", "Fira Code", "monospace"],
        display: ["Cal Sans", "Inter", "sans-serif"],
      },

      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },

      // ── Spacing ──────────────────────────────────────────────────────────────
      spacing: {
        "18": "4.5rem",
        "88": "22rem",
        "112": "28rem",
        "128": "32rem",
      },

      // ── Border Radius ────────────────────────────────────────────────────────
      borderRadius: {
        "4xl": "2rem",
      },

      // ── Box Shadow ───────────────────────────────────────────────────────────
      boxShadow: {
        "glow-primary": "0 0 20px rgba(59, 130, 246, 0.35)",
        "glow-accent":  "0 0 20px rgba(139, 92, 246, 0.35)",
        "glow-green":   "0 0 20px rgba(16, 185, 129, 0.35)",
        "card":         "0 4px 24px rgba(0, 0, 0, 0.12)",
        "card-hover":   "0 8px 40px rgba(0, 0, 0, 0.20)",
      },

      // ── Animations ───────────────────────────────────────────────────────────
      keyframes: {
        "fade-in": {
          "0%":   { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-scale": {
          "0%":   { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-in-right": {
          "0%":   { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "slide-in-left": {
          "0%":   { opacity: "0", transform: "translateX(-16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 8px rgba(59, 130, 246, 0.4)" },
          "50%":      { boxShadow: "0 0 24px rgba(59, 130, 246, 0.8)" },
        },
        "shimmer": {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "progress-bar": {
          "0%":   { width: "0%" },
          "100%": { width: "100%" },
        },
        "spin-slow": {
          "0%":   { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
      },

      animation: {
        "fade-in":        "fade-in 0.3s ease-out",
        "fade-in-scale":  "fade-in-scale 0.25s ease-out",
        "slide-in-right": "slide-in-right 0.3s ease-out",
        "slide-in-left":  "slide-in-left 0.3s ease-out",
        "pulse-glow":     "pulse-glow 2s ease-in-out infinite",
        "shimmer":        "shimmer 2s linear infinite",
        "progress-bar":   "progress-bar 0.5s ease-out",
        "spin-slow":      "spin-slow 3s linear infinite",
      },

      // ── Background ───────────────────────────────────────────────────────────
      backgroundImage: {
        "gradient-radial":    "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":     "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "shimmer-gradient":   "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.06) 50%, transparent 100%)",
        "card-gradient":      "linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%)",
        "hero-gradient":      "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)",
      },

      // ── Backdrop Blur ────────────────────────────────────────────────────────
      backdropBlur: {
        xs: "2px",
      },

      // ── Transitions ──────────────────────────────────────────────────────────
      transitionDuration: {
        "0": "0ms",
        "400": "400ms",
      },
    },
  },

  plugins: [
    typography,
  ],
};