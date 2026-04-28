# CodeSense Pro Design System

A premium, cinematic dark design system for AI-powered code evaluation platforms. Inspired by industry leaders like Cursor, Linear, and Vercel.

## 1. Visual Theme & Atmosphere
*   **Philosophy**: Developer-native, high-precision, AI-forward.
*   **Aesthetic**: "The Dark Workbench". Deep obsidian surfaces, subtle glassmorphism, and neon-spectral accents.
*   **Density**: High-information density with generous purposeful whitespace around interactive elements.

## 2. Color Palette & Roles

| Role | Color Name | Hex | Usage |
|------|------------|-----|-------|
| Background | Void | `#050505` | Base page background |
| Surface | Obsidian | `#0A0A0A` | Primary card/container background |
| Elevated | Stealth | `#141414` | Hover states, modals, secondary tiles |
| Border | Wire | `#222222` | Default component borders |
| Primary | Cyber Emerald | `#10b981` | Success states, growth, primary CTAs |
| Secondary | Flux Purple | `#8b5cf6` | Analysis, AI features, logic sections |
| Accent | Pulse Blue | `#3b82f6` | Info states, links, interactive highlights |
| Danger | Redline | `#ef4444` | Errors, deletions, critical warnings |
| Text (High) | Cloud | `#f9fafb` | Primary headings and body text |
| Text (Med) | Mist | `#9ca3af` | Secondary text, labels |
| Text (Low) | Shadow | `#4b5563` | Placeholders, disabled states |

## 3. Typography Rules

*   **Body/UI**: `Geist`, `Inter`, or system-sans.
    *   `font-feature-settings: "cv02", "cv03", "cv04", "ss01"` for maximum legibility.
*   **Data/Monospace**: `JetBrains Mono`, `Fira Code`.
    *   Used for: Scores, IDs, status tags, and code.

## 4. Component Stylings

### Cards
*   **Background**: `var(--obsidian)`
*   **Border**: `1px solid var(--wire)`
*   **Shadow**: None. Use border contrast for depth.
*   **Hover**: Border transitions to linear-gradient (Emerald to Purple) with 20% opacity glow.

### Buttons (Pro)
*   **Primary**: Solid Cyber Emerald or Spectral Gradient.
*   **Secondary**: Ghost buttons with `backdrop-filter: blur` and `1px solid var(--wire)`.
*   **Transitions**: 200ms ease-out on all states.

## 5. Layout Principles
*   **The Grid**: 8px baseline grid.
*   **Glassmorphism**: Navigation and sidebars must use `rgba(10, 10, 10, 0.7)` with `backdrop-filter: blur(12px)`.
*   **Monospace Accents**: Any numeric or identifier data should clearly use the Monospace font.

## 6. Depth & Elevation
1.  **Level 0 (Void)**: Global background.
2.  **Level 1 (Obsidian)**: Primary cards, content area.
3.  **Level 2 (Stealth)**: Popovers, nested containers, tooltips.

---
*Created by CodeSense Design Subagent. System version: 1.0.0-PRO*
