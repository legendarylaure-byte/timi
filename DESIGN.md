---
version: alpha
name: vyom-ai-cloud-timi
description: "AI-Powered Tech Educational Video Platform — Dashboard UI"
colors:
  light:
    bg: "#FFFFFF"
    card: "#FFFFFF"
    primary: "#ec133e"
    secondary: "#bd0f32"
    accent: "#f4718b"
    success: "#059669"
    info: "#2563EB"
    warning: "#D97706"
    text: "#1a1a1a"
    text-muted: "#6B7280"
    border: "#fde7ec"
  dark:
    bg: "#0C1844"
    card: "#1A2248"
    primary: "#FF6969"
    secondary: "#FF4757"
    accent: "#D4B896"
    success: "#34D399"
    info: "#60A5FA"
    warning: "#FBBF24"
    text: "#FFF5E1"
    text-muted: "#8890B0"
    border: "#2A3460"
typography:
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 16px
    lineHeight: 1.5
  heading:
    fontFamily: "Inter, system-ui, sans-serif"
    fontWeight: 700
    lineHeight: 1.2
spacing:
  unit: 4px
  scale: [0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64]
borderRadius:
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  full: 9999px
components:
  button-primary:
    backgroundColor: "{colors.light.primary}"
    color: "#FFFFFF"
    borderRadius: "{borderRadius.md}"
    padding: "12px 24px"
    fontWeight: 700
    hover:
      backgroundColor: "{colors.light.secondary}"
      transform: "scale(1.05)"
  button-ghost:
    color: "{colors.light.primary}"
    backgroundColor: "transparent"
    borderRadius: "{borderRadius.md}"
    padding: "8px 16px"
  card:
    backgroundColor: "{colors.light.card}"
    borderRadius: "{borderRadius.xl}"
    border: "1px solid {colors.light.border}"
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)"
---

## Overview

Vyom Ai Cloud (Timi) is an automated content pipeline that generates educational tech/AI videos. The dashboard is the control center — built with Next.js 15, React 19, TailwindCSS, and Framer Motion. Supports light/dark themes with glassmorphism aesthetic.

## Colors

### Light Theme
| Token | Hex | Usage |
|-------|-----|-------|
| `--light-bg` | `#FFFFFF` | Page background |
| `--light-card` | `#FFFFFF` | Card/surface background |
| `--light-primary` | `#ec133e` | Primary CTAs, links, active states |
| `--light-secondary` | `#bd0f32` | Secondary actions, hover states |
| `--light-accent` | `#f4718b` | Accent highlights, gradient flares |
| `--light-success` | `#059669` | Success indicators |
| `--light-info` | `#2563EB` | Info badges |
| `--light-warning` | `#D97706` | Warning indicators |
| `--light-text` | `#1a1a1a` | Primary body text |
| `--light-muted` | `#6B7280` | Secondary/muted text |
| `--light-border` | `#fde7ec` | Borders, dividers, hairlines |

### Dark Theme
| Token | Hex | Usage |
|-------|-----|-------|
| `--dark-bg` | `#0C1844` | Page background |
| `--dark-card` | `#1A2248` | Card/surface background |
| `--dark-primary` | `#FF6969` | Primary CTAs, links |
| `--dark-secondary` | `#FF4757` | Secondary actions |
| `--dark-accent` | `#D4B896` | Accent highlights |
| `--dark-success` | `#34D399` | Success indicators |
| `--dark-info` | `#60A5FA` | Info badges |
| `--dark-warning` | `#FBBF24` | Warning indicators |
| `--dark-text` | `#FFF5E1` | Primary body text |
| `--dark-muted` | `#8890B0` | Secondary text |
| `--dark-border` | `#2A3460` | Borders, dividers |

### Gradients
- **Primary gradient**: `linear-gradient(135deg, #ec133e → #bd0f32)` (light) / `#FF6969 → #FF4757` (dark)
- **Warm**: `linear-gradient(135deg, #ec133e, #1a1a1a)`
- **Cool**: `linear-gradient(135deg, #bd0f32, #1a1a1a)`
- **Aurora bg (light)**: `#ec133e → #bd0f32 → #f4718b → #FFFFFF → #fde7ec → #ec133e`
- **Aurora bg (dark)**: `#FF6969 → #C80036 → #0C1844 → #1A2248 → #D4B896 → #FF6969`

## Typography

| Style | Family | Size | Weight | Line Height |
|-------|--------|------|--------|-------------|
| Display | Inter | 48px | 800 | 1.1 |
| H1 | Inter | 36px | 700 | 1.2 |
| H2 | Inter | 30px | 700 | 1.25 |
| H3 | Inter | 24px | 600 | 1.3 |
| H4 | Inter | 20px | 600 | 1.35 |
| Body | Inter | 16px | 400 | 1.5 |
| Body Small | Inter | 14px | 400 | 1.5 |
| Caption | Inter | 12px | 500 | 1.4 |
| Mono | system-ui | 14px | 400 | 1.5 |

Fallback stack: `Inter, Poppins, system-ui, sans-serif`

## Layout

- **Grid**: 12-column responsive grid
- **Max content width**: 1280px (`max-w-7xl`)
- **Breakpoints**: 375px (mobile) / 768px (tablet) / 1024px (desktop) / 1440px (wide)
- **Spacing system**: 4px incremental (4, 8, 12, 16, 20, 24, 32, 40, 48, 64)
- **Border radius**: 8px (sm) / 12px (md) / 16px (lg) / 24px (xl)

## Glassmorphism

- `.glass`: `bg-white/80 dark:bg-dark-card/60 backdrop-blur-xl`
- `.glass-strong`: `bg-white/90 dark:bg-dark-card/80 backdrop-blur-2xl`
- `.glass-card`: `bg-white/80 dark:bg-dark-card/70 backdrop-blur-xl border rounded-2xl`

## Shadows

| Token | Light | Dark |
|-------|-------|------|
| `shadow-glow-red` | `0 0 20px rgba(236, 19, 62, 0.4)` | — |
| `shadow-glow-navy` | `0 0 20px rgba(12, 24, 68, 0.4)` | — |
| `shadow-glow-crimson` | `0 0 20px rgba(189, 15, 50, 0.4)` | — |
| `shadow-glow-emerald` | `0 0 20px rgba(16, 185, 129, 0.4)` | — |
| `shadow-glow-blue` | `0 0 20px rgba(37, 99, 235, 0.4)` | — |

## Animation Tokens

| Name | Duration | Timing |
|------|----------|--------|
| `float` | 6s | ease-in-out infinite |
| `float-slow` | 8s | ease-in-out infinite |
| `bounce-slow` | 3s | ease-in-out infinite |
| `spin-slow` | 20s | linear infinite |
| `aurora` | 15s | ease-in-out infinite |
| `shimmer` | 3s | ease-in-out infinite |
| `slide-up` | 0.5s | ease-out |
| `slide-in-right` | 0.4s | ease-out |

## Components

### Button
- Variants: `primary` (gradient fill), `secondary` (outlined), `ghost` (text only)
- Framer Motion: `whileHover={{ scale: 1.02 }}` / `whileTap={{ scale: 0.98 }}`
- States: hover/active with scale transform

### Card
- Base: glass-card with `rounded-2xl`, border, backdrop-blur
- Hover: `card-hover` — `hover:shadow-xl hover:-translate-y-1`

### Status Badge
- Colored indicators for pipeline status, video states
- Uses semantic colors (success, warning, error, info)

### Theme Toggle
- Light/dark mode switch using `class` strategy on `<html>`
- Persisted to `localStorage`
- Respects `prefers-color-scheme`

### Toast / Notification Center
- Slide-in right animation (0.4s)
- Auto-dismiss with configurable duration
- Stacked notifications

## Do's

- Use semantic color tokens everywhere (never raw hex)
- Apply glassmorphism for overlays, cards, and modals
- Use gradient text for headings on hero sections
- Use lucide-react for all icons
- Respect reduced-motion preferences
- Use Framer Motion for micro-interactions (scale on press, fade in on mount)
- Keep cards with backdrop-blur and subtle borders

## Don'ts

- Don't use emoji as icons (use lucide-react SVGs)
- Don't hardcode hex values — always use Tailwind theme tokens
- Don't use white/gray text on light backgrounds
- Don't add decorative-only animations without purpose
- Don't stack too many glass layers (max 2-3 depth)
- Don't use horizontal scroll on mobile
- Don't disable zoom (`user-scalable=no`)
- Don't leave focus rings disabled for keyboard users
