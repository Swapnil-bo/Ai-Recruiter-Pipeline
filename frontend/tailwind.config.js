import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],

  darkMode: "class",

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

        // Success — emerald
        success: {
          50:  "#ecfdf5",
          100: "#d1fae5",
          200: "#a7f3d0",
          300: "#6ee7b7",
          400: "#34d399",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
          800: "#065f46",
          900: "#064e3b",
          950: "#022c22",
        },

        // Warning — amber
        warning: {
          50:  "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          300: "#fcd34d",
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
          800: "#92400e",
          900: "#78350f",
          950: "#451a03",
        },

        // Danger — red
        danger: {
          50:  "#fef2f2",
          100: "#fee2e2",
          200: "#fecaca",
          300: "#fca5a5",
          400: "#f87171",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
          800: "#991b1b",
          900: "#7f1d1d",
          950: "#450a0a",
        },

        // Cyan — for scraping stage
        cyan: {
          50:  "#ecfeff",
          100: "#cffafe",
          200: "#a5f3fc",
          300: "#67e8f9",
          400: "#22d3ee",
          500: "#06b6d4",
          600: "#0891b2",
          700: "#0e7490",
          800: "#155e75",
          900: "#164e63",
          950: "#083344",
        },

        // Fit score semantic colors
        score: {
          excellent: "#10b981",   // green  — 8.0+
          good:      "#3b82f6",   // blue   — 6.0–7.9
          fair:      "#f59e0b",   // amber  — 4.0–5.9
          weak:      "#ef4444",   // red    — below 4.0
          "excellent-bg": "rgba(16, 185, 129, 0.12)",
          "good-bg":      "rgba(59, 130, 246, 0.12)",
          "fair-bg":      "rgba(245, 158, 11, 0.12)",
          "weak-bg":      "rgba(239, 68, 68, 0.12)",
        },

        // Pipeline stage colors
        stage: {
          scraping:  "#06b6d4",   // cyan
          matching:  "#8b5cf6",   // violet
          scoring:   "#f59e0b",   // amber
          drafting:  "#10b981",   // green
          done:      "#3b82f6",   // blue
          error:     "#ef4444",   // red
          idle:      "#64748b",   // slate
        },

        // Glass morphism
        glass: {
          white:  "rgba(255, 255, 255, 0.05)",
          border: "rgba(255, 255, 255, 0.08)",
          hover:  "rgba(255, 255, 255, 0.10)",
        },
      },

      // ── Typography ───────────────────────────────────────────────────────────
      fontFamily: {
        sans:    ["Inter", "system-ui", "sans-serif"],
        mono:    ["JetBrains Mono", "Fira Code", "Cascadia Code", "monospace"],
        display: ["Cal Sans", "Inter", "sans-serif"],
      },

      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
        "3xs": ["0.5rem",   { lineHeight: "0.75rem"  }],
      },

      fontWeight: {
        hairline: "100",
        thin:     "200",
      },

      lineHeight: {
        "11": "2.75rem",
        "12": "3rem",
      },

      letterSpacing: {
        "widest-2": "0.2em",
      },

      // ── Spacing ──────────────────────────────────────────────────────────────
      spacing: {
        "13":  "3.25rem",
        "15":  "3.75rem",
        "17":  "4.25rem",
        "18":  "4.5rem",
        "19":  "4.75rem",
        "21":  "5.25rem",
        "22":  "5.5rem",
        "26":  "6.5rem",
        "30":  "7.5rem",
        "34":  "8.5rem",
        "38":  "9.5rem",
        "42":  "10.5rem",
        "46":  "11.5rem",
        "50":  "12.5rem",
        "54":  "13.5rem",
        "58":  "14.5rem",
        "62":  "15.5rem",
        "66":  "16.5rem",
        "70":  "17.5rem",
        "74":  "18.5rem",
        "78":  "19.5rem",
        "82":  "20.5rem",
        "86":  "21.5rem",
        "88":  "22rem",
        "92":  "23rem",
        "100": "25rem",
        "104": "26rem",
        "108": "27rem",
        "112": "28rem",
        "116": "29rem",
        "120": "30rem",
        "124": "31rem",
        "128": "32rem",
        "136": "34rem",
        "144": "36rem",
        "160": "40rem",
        "192": "48rem",
        "256": "64rem",
      },

      // ── Sizing ───────────────────────────────────────────────────────────────
      width: {
        "sidebar":       "16rem",
        "sidebar-wide":  "20rem",
        "panel":         "24rem",
        "panel-wide":    "32rem",
        "content":       "48rem",
        "content-wide":  "64rem",
      },

      maxWidth: {
        "8xl":  "88rem",
        "9xl":  "96rem",
        "10xl": "120rem",
      },

      minHeight: {
        "screen-75": "75vh",
        "screen-50": "50vh",
      },

      // ── Border Radius ────────────────────────────────────────────────────────
      borderRadius: {
        "4xl": "2rem",
        "5xl": "2.5rem",
        "6xl": "3rem",
      },

      // ── Border Width ─────────────────────────────────────────────────────────
      borderWidth: {
        "3": "3px",
        "5": "5px",
        "6": "6px",
      },

      // ── Box Shadow ───────────────────────────────────────────────────────────
      boxShadow: {
        // Glow effects
        "glow-primary":   "0 0 20px rgba(59, 130, 246, 0.35)",
        "glow-primary-lg":"0 0 40px rgba(59, 130, 246, 0.50)",
        "glow-accent":    "0 0 20px rgba(139, 92, 246, 0.35)",
        "glow-accent-lg": "0 0 40px rgba(139, 92, 246, 0.50)",
        "glow-green":     "0 0 20px rgba(16, 185, 129, 0.35)",
        "glow-green-lg":  "0 0 40px rgba(16, 185, 129, 0.50)",
        "glow-cyan":      "0 0 20px rgba(6, 182, 212, 0.35)",
        "glow-amber":     "0 0 20px rgba(245, 158, 11, 0.35)",
        "glow-red":       "0 0 20px rgba(239, 68, 68, 0.35)",

        // Card effects
        "card":           "0 4px 24px rgba(0, 0, 0, 0.12)",
        "card-hover":     "0 8px 40px rgba(0, 0, 0, 0.20)",
        "card-active":    "0 2px 12px rgba(0, 0, 0, 0.08)",
        "card-glow":      "0 4px 24px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(59, 130, 246, 0.15)",

        // Elevation system
        "elevation-1":    "0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)",
        "elevation-2":    "0 3px 6px rgba(0,0,0,0.15), 0 2px 4px rgba(0,0,0,0.12)",
        "elevation-3":    "0 10px 20px rgba(0,0,0,0.15), 0 3px 6px rgba(0,0,0,0.10)",
        "elevation-4":    "0 15px 25px rgba(0,0,0,0.15), 0 5px 10px rgba(0,0,0,0.05)",
        "elevation-5":    "0 20px 40px rgba(0,0,0,0.20)",

        // Inner
        "inner-glow":     "inset 0 0 20px rgba(59, 130, 246, 0.15)",
        "inner-dark":     "inset 0 2px 8px rgba(0, 0, 0, 0.40)",

        // Glass
        "glass":          "0 8px 32px rgba(0, 0, 0, 0.20), inset 0 1px 0 rgba(255, 255, 255, 0.06)",
        "glass-hover":    "0 16px 48px rgba(0, 0, 0, 0.30), inset 0 1px 0 rgba(255, 255, 255, 0.10)",
      },

      // ── Drop Shadow (filter) ─────────────────────────────────────────────────
      dropShadow: {
        "glow-sm":  "0 0 6px rgba(59, 130, 246, 0.60)",
        "glow":     "0 0 12px rgba(59, 130, 246, 0.60)",
        "glow-lg":  "0 0 24px rgba(59, 130, 246, 0.60)",
      },

      // ── Animations ───────────────────────────────────────────────────────────
      keyframes: {
        // Entrance
        "fade-in": {
          "0%":   { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-fast": {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "fade-in-scale": {
          "0%":   { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "fade-in-scale-up": {
          "0%":   { opacity: "0", transform: "scale(0.85)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "fade-out": {
          "0%":   { opacity: "1", transform: "translateY(0)" },
          "100%": { opacity: "0", transform: "translateY(-8px)" },
        },

        // Slides
        "slide-in-right": {
          "0%":   { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "slide-in-left": {
          "0%":   { opacity: "0", transform: "translateX(-16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "slide-in-up": {
          "0%":   { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-down": {
          "0%":   { opacity: "0", transform: "translateY(-16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-out-left": {
          "0%":   { opacity: "1", transform: "translateX(0)" },
          "100%": { opacity: "0", transform: "translateX(-16px)" },
        },

        // Glow & pulse
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 8px rgba(59, 130, 246, 0.4)" },
          "50%":      { boxShadow: "0 0 24px rgba(59, 130, 246, 0.8)" },
        },
        "pulse-glow-accent": {
          "0%, 100%": { boxShadow: "0 0 8px rgba(139, 92, 246, 0.4)" },
          "50%":      { boxShadow: "0 0 24px rgba(139, 92, 246, 0.8)" },
        },
        "pulse-glow-green": {
          "0%, 100%": { boxShadow: "0 0 8px rgba(16, 185, 129, 0.4)" },
          "50%":      { boxShadow: "0 0 24px rgba(16, 185, 129, 0.8)" },
        },
        "pulse-scale": {
          "0%, 100%": { transform: "scale(1)" },
          "50%":      { transform: "scale(1.05)" },
        },

        // Loading states
        "shimmer": {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "skeleton": {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },

        // Progress
        "progress-bar": {
          "0%":   { width: "0%" },
          "100%": { width: "100%" },
        },
        "progress-indeterminate": {
          "0%":   { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },

        // Rotation
        "spin-slow": {
          "0%":   { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        "spin-reverse": {
          "0%":   { transform: "rotate(360deg)" },
          "100%": { transform: "rotate(0deg)" },
        },

        // Bounce variants
        "bounce-subtle": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%":      { transform: "translateY(-4px)" },
        },
        "bounce-x": {
          "0%, 100%": { transform: "translateX(0)" },
          "50%":      { transform: "translateX(4px)" },
        },

        // Score badge
        "score-pop": {
          "0%":   { opacity: "0", transform: "scale(0.5)" },
          "70%":  { transform: "scale(1.15)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },

        // Pipeline agent step
        "step-complete": {
          "0%":   { opacity: "0", transform: "scale(0.8) rotate(-10deg)" },
          "60%":  { transform: "scale(1.1) rotate(3deg)" },
          "100%": { opacity: "1", transform: "scale(1) rotate(0deg)" },
        },

        // Typing cursor
        "blink": {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0" },
        },

        // Gradient shift
        "gradient-shift": {
          "0%":   { backgroundPosition: "0% 50%" },
          "50%":  { backgroundPosition: "100% 50%" },
          "100%": { backgroundPosition: "0% 50%" },
        },

        // Wiggle
        "wiggle": {
          "0%, 100%": { transform: "rotate(-3deg)" },
          "50%":      { transform: "rotate(3deg)" },
        },

        // Count up (for score reveal)
        "count-up": {
          "0%":   { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },

        // Notification ping
        "ping-once": {
          "0%":   { transform: "scale(1)", opacity: "1" },
          "75%":  { transform: "scale(1.8)", opacity: "0" },
          "100%": { transform: "scale(1.8)", opacity: "0" },
        },

        // Draw line (for pipeline connector)
        "draw-line": {
          "0%":   { width: "0%" },
          "100%": { width: "100%" },
        },

        // Typewriter
        "typewriter": {
          "0%":   { width: "0%" },
          "100%": { width: "100%" },
        },
      },

      animation: {
        // Entrance
        "fade-in":           "fade-in 0.3s ease-out",
        "fade-in-fast":      "fade-in-fast 0.15s ease-out",
        "fade-in-slow":      "fade-in 0.6s ease-out",
        "fade-in-scale":     "fade-in-scale 0.25s ease-out",
        "fade-in-scale-up":  "fade-in-scale-up 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)",
        "fade-out":          "fade-out 0.2s ease-in",

        // Slides
        "slide-in-right":    "slide-in-right 0.3s ease-out",
        "slide-in-left":     "slide-in-left 0.3s ease-out",
        "slide-in-up":       "slide-in-up 0.3s ease-out",
        "slide-in-down":     "slide-in-down 0.3s ease-out",
        "slide-out-left":    "slide-out-left 0.2s ease-in",

        // Glow & pulse
        "pulse-glow":        "pulse-glow 2s ease-in-out infinite",
        "pulse-glow-accent": "pulse-glow-accent 2s ease-in-out infinite",
        "pulse-glow-green":  "pulse-glow-green 2s ease-in-out infinite",
        "pulse-scale":       "pulse-scale 2s ease-in-out infinite",

        // Loading
        "shimmer":           "shimmer 2s linear infinite",
        "skeleton":          "skeleton 1.5s ease-in-out infinite",
        "progress-bar":      "progress-bar 0.5s ease-out forwards",
        "progress-indeterminate": "progress-indeterminate 1.5s ease-in-out infinite",

        // Rotation
        "spin-slow":         "spin-slow 3s linear infinite",
        "spin-reverse":      "spin-reverse 3s linear infinite",
        "spin-very-slow":    "spin-slow 8s linear infinite",

        // Bounce
        "bounce-subtle":     "bounce-subtle 2s ease-in-out infinite",
        "bounce-x":          "bounce-x 1s ease-in-out infinite",

        // Special
        "score-pop":         "score-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards",
        "step-complete":     "step-complete 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) forwards",
        "blink":             "blink 1s step-end infinite",
        "gradient-shift":    "gradient-shift 4s ease infinite",
        "wiggle":            "wiggle 0.5s ease-in-out",
        "count-up":          "count-up 0.4s ease-out forwards",
        "ping-once":         "ping-once 0.6s ease-out forwards",
        "draw-line":         "draw-line 0.4s ease-out forwards",
        "typewriter":        "typewriter 2s steps(40, end) forwards",
      },

      // ── Background Images ────────────────────────────────────────────────────
      backgroundImage: {
        "gradient-radial":       "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":        "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "gradient-radial-at-t":  "radial-gradient(ellipse at top, var(--tw-gradient-stops))",
        "gradient-radial-at-b":  "radial-gradient(ellipse at bottom, var(--tw-gradient-stops))",
        "gradient-radial-at-l":  "radial-gradient(ellipse at left, var(--tw-gradient-stops))",
        "gradient-radial-at-r":  "radial-gradient(ellipse at right, var(--tw-gradient-stops))",
        "shimmer-gradient":      "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.06) 50%, transparent 100%)",
        "skeleton-gradient":     "linear-gradient(90deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.03) 100%)",
        "card-gradient":         "linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%)",
        "card-gradient-hover":   "linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 1.0) 100%)",
        "hero-gradient":         "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)",
        "hero-gradient-2":       "linear-gradient(160deg, #0f172a 0%, #1a103d 40%, #0c1a2e 100%)",
        "glow-gradient":         "radial-gradient(ellipse at center, rgba(59, 130, 246, 0.15) 0%, transparent 70%)",
        "glow-gradient-accent":  "radial-gradient(ellipse at center, rgba(139, 92, 246, 0.15) 0%, transparent 70%)",
        "noise":                 "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.4'/%3E%3C/svg%3E\")",
        // Stage-specific gradients
        "stage-scraping":        "linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, transparent 70%)",
        "stage-matching":        "linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, transparent 70%)",
        "stage-scoring":         "linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, transparent 70%)",
        "stage-drafting":        "linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, transparent 70%)",
        "stage-done":            "linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, transparent 70%)",
      },

      // ── Backdrop Blur ────────────────────────────────────────────────────────
      backdropBlur: {
        xs:   "2px",
        "4xl": "72px",
      },

      // ── Opacity ──────────────────────────────────────────────────────────────
      opacity: {
        "2":  "0.02",
        "3":  "0.03",
        "4":  "0.04",
        "6":  "0.06",
        "7":  "0.07",
        "8":  "0.08",
        "12": "0.12",
        "15": "0.15",
        "35": "0.35",
        "45": "0.45",
        "55": "0.55",
        "65": "0.65",
        "85": "0.85",
        "98": "0.98",
      },

      // ── Z-Index ──────────────────────────────────────────────────────────────
      zIndex: {
        "60":  "60",
        "70":  "70",
        "80":  "80",
        "90":  "90",
        "100": "100",
      },

      // ── Transitions ──────────────────────────────────────────────────────────
      transitionDuration: {
        "0":   "0ms",
        "400": "400ms",
        "600": "600ms",
        "800": "800ms",
        "900": "900ms",
      },

      transitionTimingFunction: {
        "spring":       "cubic-bezier(0.34, 1.56, 0.64, 1)",
        "spring-soft":  "cubic-bezier(0.25, 1.25, 0.5, 1)",
        "ease-in-expo": "cubic-bezier(0.7, 0, 0.84, 0)",
        "ease-out-expo":"cubic-bezier(0.16, 1, 0.3, 1)",
        "ease-in-out-expo": "cubic-bezier(0.87, 0, 0.13, 1)",
        "bounce":       "cubic-bezier(0.68, -0.55, 0.265, 1.55)",
      },

      // ── Blur ─────────────────────────────────────────────────────────────────
      blur: {
        xs: "2px",
      },

      // ── Scale ────────────────────────────────────────────────────────────────
      scale: {
        "98":  "0.98",
        "102": "1.02",
        "103": "1.03",
        "115": "1.15",
      },

      // ── Cursor ───────────────────────────────────────────────────────────────
      cursor: {
        "grab":     "grab",
        "grabbing": "grabbing",
      },

      // ── Screens (breakpoints) ────────────────────────────────────────────────
      screens: {
        "xs":   "480px",
        "3xl":  "1792px",
        "4xl":  "2048px",
      },

      // ── Grid ─────────────────────────────────────────────────────────────────
      gridTemplateColumns: {
        "sidebar":       "16rem 1fr",
        "sidebar-wide":  "20rem 1fr",
        "dashboard":     "16rem 1fr 24rem",
        "cards-2":       "repeat(2, minmax(0, 1fr))",
        "cards-3":       "repeat(3, minmax(0, 1fr))",
        "cards-auto":    "repeat(auto-fill, minmax(320px, 1fr))",
        "cards-auto-sm": "repeat(auto-fill, minmax(240px, 1fr))",
      },

      // ── Aspect Ratio ─────────────────────────────────────────────────────────
      aspectRatio: {
        "4/3":  "4 / 3",
        "3/2":  "3 / 2",
        "2/3":  "2 / 3",
        "9/16": "9 / 16",
      },
    },
  },

  plugins: [
    typography,

    // ── Custom Utilities Plugin ───────────────────────────────────────────────
    function ({ addUtilities, addComponents, theme, e }) {

      // Glass morphism utilities
      addUtilities({
        ".glass": {
          background:     "rgba(255, 255, 255, 0.03)",
          backdropFilter: "blur(12px)",
          border:         "1px solid rgba(255, 255, 255, 0.08)",
        },
        ".glass-sm": {
          background:     "rgba(255, 255, 255, 0.02)",
          backdropFilter: "blur(6px)",
          border:         "1px solid rgba(255, 255, 255, 0.06)",
        },
        ".glass-md": {
          background:     "rgba(255, 255, 255, 0.05)",
          backdropFilter: "blur(16px)",
          border:         "1px solid rgba(255, 255, 255, 0.10)",
        },
        ".glass-lg": {
          background:     "rgba(255, 255, 255, 0.07)",
          backdropFilter: "blur(24px)",
          border:         "1px solid rgba(255, 255, 255, 0.12)",
        },

        // Gradient text
        ".text-gradient-primary": {
          background:        "linear-gradient(135deg, #60a5fa 0%, #818cf8 100%)",
          "-webkit-background-clip": "text",
          "-webkit-text-fill-color": "transparent",
          "background-clip": "text",
        },
        ".text-gradient-accent": {
          background:        "linear-gradient(135deg, #a78bfa 0%, #ec4899 100%)",
          "-webkit-background-clip": "text",
          "-webkit-text-fill-color": "transparent",
          "background-clip": "text",
        },
        ".text-gradient-success": {
          background:        "linear-gradient(135deg, #34d399 0%, #3b82f6 100%)",
          "-webkit-background-clip": "text",
          "-webkit-text-fill-color": "transparent",
          "background-clip": "text",
        },
        ".text-gradient-fire": {
          background:        "linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)",
          "-webkit-background-clip": "text",
          "-webkit-text-fill-color": "transparent",
          "background-clip": "text",
        },

        // Scrollbar hiding
        ".scrollbar-hide": {
          "-ms-overflow-style": "none",
          "scrollbar-width":    "none",
          "&::-webkit-scrollbar": { display: "none" },
        },

        // Custom thin scrollbar
        ".scrollbar-thin": {
          "scrollbar-width": "thin",
          "scrollbar-color": "rgba(71, 85, 105, 0.5) transparent",
          "&::-webkit-scrollbar": { width: "4px" },
          "&::-webkit-scrollbar-track": { background: "transparent" },
          "&::-webkit-scrollbar-thumb": {
            background:   "rgba(71, 85, 105, 0.5)",
            borderRadius: "2px",
          },
        },

        // Background size for shimmer
        ".bg-size-200": { backgroundSize: "200% 100%" },
        ".bg-size-400": { backgroundSize: "400% 100%" },

        // Truncate multiline
        ".line-clamp-1": { overflow: "hidden", display: "-webkit-box", "-webkit-line-clamp": "1", "-webkit-box-orient": "vertical" },
        ".line-clamp-2": { overflow: "hidden", display: "-webkit-box", "-webkit-line-clamp": "2", "-webkit-box-orient": "vertical" },
        ".line-clamp-3": { overflow: "hidden", display: "-webkit-box", "-webkit-line-clamp": "3", "-webkit-box-orient": "vertical" },
        ".line-clamp-4": { overflow: "hidden", display: "-webkit-box", "-webkit-line-clamp": "4", "-webkit-box-orient": "vertical" },

        // Selection color
        ".selection-primary": {
          "::selection": { background: "rgba(59, 130, 246, 0.3)", color: "white" },
        },

        // Inset border glow on focus
        ".focus-glow": {
          "&:focus-visible": {
            outline:   "none",
            boxShadow: "0 0 0 2px rgba(59, 130, 246, 0.6)",
          },
        },

        // No tap highlight on mobile
        ".no-tap-highlight": {
          "-webkit-tap-highlight-color": "transparent",
        },

        // Full bleed
        ".full-bleed": {
          width:       "100vw",
          marginLeft:  "calc(50% - 50vw)",
          marginRight: "calc(50% - 50vw)",
        },
      });

      // Reusable component classes
      addComponents({
        // Card base
        ".card": {
          background:   "linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%)",
          border:       "1px solid rgba(255, 255, 255, 0.06)",
          borderRadius: "0.75rem",
          padding:      "1.5rem",
          transition:   "all 0.2s ease",
          "&:hover": {
            border:    "1px solid rgba(255, 255, 255, 0.10)",
            boxShadow: "0 8px 40px rgba(0, 0, 0, 0.20)",
          },
        },

        // Badge base
        ".badge": {
          display:       "inline-flex",
          alignItems:    "center",
          padding:       "0.25rem 0.625rem",
          borderRadius:  "9999px",
          fontSize:      "0.75rem",
          fontWeight:    "500",
          lineHeight:    "1rem",
          letterSpacing: "0.025em",
        },

        // Pipeline connector line
        ".pipeline-connector": {
          position:   "relative",
          "&::after": {
            content:    "''",
            position:   "absolute",
            top:        "50%",
            left:       "100%",
            width:      "100%",
            height:     "2px",
            background: "linear-gradient(90deg, rgba(59, 130, 246, 0.5), rgba(139, 92, 246, 0.5))",
            transform:  "translateY(-50%)",
          },
        },

        // Stat card
        ".stat-card": {
          display:        "flex",
          flexDirection:  "column",
          gap:            "0.5rem",
          padding:        "1.25rem",
          background:     "rgba(15, 23, 42, 0.6)",
          border:         "1px solid rgba(255, 255, 255, 0.06)",
          borderRadius:   "0.75rem",
          backdropFilter: "blur(8px)",
        },

        // Input base
        ".input-base": {
          width:          "100%",
          padding:        "0.625rem 1rem",
          background:     "rgba(15, 23, 42, 0.6)",
          border:         "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius:   "0.5rem",
          color:          "white",
          fontSize:       "0.875rem",
          outline:        "none",
          transition:     "all 0.2s ease",
          "&:focus": {
            border:    "1px solid rgba(59, 130, 246, 0.6)",
            boxShadow: "0 0 0 3px rgba(59, 130, 246, 0.15)",
          },
          "&::placeholder": {
            color: "rgba(148, 163, 184, 0.5)",
          },
        },

        // Button base
        ".btn-base": {
          display:        "inline-flex",
          alignItems:     "center",
          justifyContent: "center",
          gap:            "0.5rem",
          padding:        "0.625rem 1.25rem",
          borderRadius:   "0.5rem",
          fontSize:       "0.875rem",
          fontWeight:     "500",
          transition:     "all 0.2s ease",
          cursor:         "pointer",
          border:         "none",
          outline:        "none",
          "&:disabled": {
            opacity: "0.5",
            cursor:  "not-allowed",
          },
        },
      });
    },
  ],
};