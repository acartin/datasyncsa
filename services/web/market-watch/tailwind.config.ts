import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        border: "var(--border)",
        "border-2": "var(--border-2)",
        "border-strong": "var(--border-strong)",
        input: "var(--input)",
        ring: "var(--ring)",
        background: "var(--background)",
        foreground: "var(--foreground)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        "surface-3": "var(--surface-3)",
        "surface-hover": "var(--surface-hover)",
        "surface-selected": "var(--surface-selected)",
        ink: {
          primary: "var(--ink-primary)",
          secondary: "var(--ink-secondary)",
          muted: "var(--ink-muted)"
        },
        semantic: {
          red: "var(--red)",
          amber: "var(--amber)",
          green: "var(--green)",
          blue: "var(--blue)"
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)"
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)"
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)"
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)"
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)"
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)"
        }
      },
      fontFamily: {
        sans: ["var(--font-sans)", "sans-serif"],
        serif: ["var(--font-serif)", "serif"],
        mono: ["var(--font-mono)", "monospace"]
      },
      fontSize: {
        "page-title": ["var(--font-size-page-title)", { lineHeight: "var(--line-height-page-title)" }],
        "page-subtitle": ["var(--font-size-page-subtitle)", { lineHeight: "var(--line-height-page-subtitle)" }],
        "section-title": ["var(--font-size-section-title)", { lineHeight: "var(--line-height-section-title)" }],
        "card-title": ["var(--font-size-card-title)", { lineHeight: "var(--line-height-card-title)" }],
        body: ["var(--font-size-body)", { lineHeight: "var(--line-height-body)" }],
        "body-sm": ["var(--font-size-body-sm)", { lineHeight: "var(--line-height-body-sm)" }],
        label: ["var(--font-size-label)", { lineHeight: "var(--line-height-label)" }],
        meta: ["var(--font-size-meta)", { lineHeight: "var(--line-height-meta)" }],
        "grid-header": ["var(--font-size-grid-header)", { lineHeight: "var(--line-height-grid-header)" }],
        "grid-cell": ["var(--font-size-grid-cell)", { lineHeight: "var(--line-height-grid-cell)" }],
        "kpi-value": ["var(--font-size-kpi-value)", { lineHeight: "var(--line-height-kpi-value)" }],
        "kpi-label": ["var(--font-size-kpi-label)", { lineHeight: "var(--line-height-kpi-label)" }]
      },
      spacing: {
        control: "var(--control-height)",
        "control-sm": "var(--control-height-sm)",
        "control-lg": "var(--control-height-lg)",
        "grid-row": "var(--grid-row-height)",
        toolbar: "var(--toolbar-height)"
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)"
      }
    }
  },
  plugins: []
};

export default config;
