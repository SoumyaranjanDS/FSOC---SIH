---
name: Technical Precision System
colors:
  surface: '#f9f9ff'
  surface-dim: '#d3daea'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e7eefe'
  surface-container-high: '#e2e8f8'
  surface-container-highest: '#dce2f3'
  on-surface: '#151c27'
  on-surface-variant: '#3e484d'
  inverse-surface: '#2a313d'
  inverse-on-surface: '#ebf1ff'
  outline: '#6e797e'
  outline-variant: '#bdc8ce'
  surface-tint: '#006780'
  primary: '#00647c'
  on-primary: '#ffffff'
  primary-container: '#007f9d'
  on-primary-container: '#fafdff'
  inverse-primary: '#6cd3f7'
  secondary: '#545f73'
  on-secondary: '#ffffff'
  secondary-container: '#d5e0f8'
  on-secondary-container: '#586377'
  tertiary: '#5a5c5d'
  on-tertiary: '#ffffff'
  tertiary-container: '#737576'
  on-tertiary-container: '#fcfdfe'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b7eaff'
  primary-fixed-dim: '#6cd3f7'
  on-primary-fixed: '#001f28'
  on-primary-fixed-variant: '#004e61'
  secondary-fixed: '#d8e3fb'
  secondary-fixed-dim: '#bcc7de'
  on-secondary-fixed: '#111c2d'
  on-secondary-fixed-variant: '#3c475a'
  tertiary-fixed: '#e1e3e4'
  tertiary-fixed-dim: '#c5c7c8'
  on-tertiary-fixed: '#191c1d'
  on-tertiary-fixed-variant: '#454748'
  background: '#f9f9ff'
  on-background: '#151c27'
  surface-variant: '#dce2f3'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-base:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 12px
  panel-padding: 12px
---

## Brand & Style

The design system is engineered for high-stakes technical environments where clarity, speed of data acquisition, and visual precision are paramount. The personality is academic and utilitarian, evoking the feeling of a well-organized research paper or a sophisticated laboratory instrument.

The design style is **Minimalist / Modern Corporate**, characterized by a rigorous adherence to hierarchy and an absence of decorative flourishes. It prioritizes information density without sacrificing legibility. Every pixel must serve a functional purpose; there are no gradients, blurs, or unnecessary textures. The interface should feel "invisible," allowing the researcher's simulation data and complex models to remain the primary focus.

## Colors

The palette is intentionally restrained to maximize the impact of technical highlights and status indicators.

- **Backgrounds**: Use `#FFFFFF` for primary content areas and `#F9FAFB` for sidebars, toolbars, and background surfaces to create subtle structural separation.
- **Primary Accent**: `#0891B2` (Teal/Blue) is reserved for primary actions, active states, and critical data points. It should be used sparingly to prevent visual fatigue.
- **Borders**: A consistent `#E5E7EB` is used for all structural divisions and component strokes, providing a crisp "drafting" feel.
- **Typography**: Primary text is set in `#1E293B` for high contrast against white backgrounds, while secondary metadata uses `#6B7280`.

## Typography

This design system utilizes **Inter** for all UI elements to ensure maximum legibility at small sizes. A secondary monospaced font, **JetBrains Mono**, is introduced specifically for numerical data, coordinates, and code snippets to ensure vertical alignment in tables and data grids.

- **Headlines**: Use Semibold (600) weight with slight negative letter-spacing for a modern, compact look.
- **Body**: The standard size is 14px for general content and 13px for dense sidebars/property panels. 
- **Labels**: Small, uppercase labels with tracked-out letter spacing should be used for section headers within panels.
- **Numerical Data**: All simulation outputs and variable values must use the `data-mono` style to prevent "jumping" text during real-time updates.

## Layout & Spacing

The layout follows a **Rigid Grid** philosophy, appropriate for high-density engineering tools. 

- **Grid**: A 12-column system is used for dashboard layouts, but the internal workspace typically utilizes a "Holy Grail" panel layout: a central fluid canvas for visualizations flanked by fixed-width property panels (typically 280px or 320px).
- **Rhythm**: A 4px base unit governs all spacing. For data-dense property panels, use `8px` (sm) and `12px` (gutter) to keep related controls tightly grouped. 
- **Density**: High density is preferred. Vertical spacing between form fields should be kept at 12px to allow more controls to be visible above the fold.

## Elevation & Depth

To maintain the "clean and academic" aesthetic, depth is communicated through **Tonal Layering** and **Low-Contrast Outlines** rather than shadows.

- **Surfaces**: Most components are flat on the background. Use `#F9FAFB` for the lowest layer and `#FFFFFF` for active workspace cards or panels.
- **Outlines**: Every interactive element (cards, inputs, dropdowns) must have a 1px border (`#E5E7EB`).
- **Active State**: Only use a shadow for temporary overlays like dropdown menus or modals. These shadows should be extremely subtle (e.g., `0 4px 6px -1px rgb(0 0 0 / 0.05)`) to avoid disrupting the minimalist plane.
- **Depth Hierarchy**:
  - Level 0: Global background (`#F9FAFB`).
  - Level 1: Main content areas, sidebars, and header (`#FFFFFF` with `#E5E7EB` borders).
  - Level 2: Modals and Popovers (Floating with a 1px border and minimal shadow).

## Shapes

The shape language is structured and precise. 

- **Radius**: A standard **4px** (`soft`) radius is applied to all buttons, input fields, and containers. This provides a professional touch that is less aggressive than sharp 90-degree corners but avoids the "consumer" feel of pill shapes.
- **Interactive Elements**: Buttons and form fields should never be fully rounded (pill-shaped). 
- **Consistency**: Maintain a uniform radius across all components to reinforce the systematic, engineered nature of the tool.

## Components

### Buttons
- **Primary**: Solid `#0891B2` with white text. No gradients.
- **Secondary**: White background, `#E5E7EB` border, `#1E293B` text.
- **Tertiary/Ghost**: No background or border. Teal text for actions, Gray text for navigation.
- **Sizing**: Compact height (32px) for toolbar buttons; standard (40px) for primary page actions.

### Form Controls
- **Inputs**: 1px `#E5E7EB` border. On focus, the border changes to `#0891B2` with a 2px "soft" teal ring (10% opacity).
- **Checkboxes/Radios**: Small scale (14px). Use `#0891B2` for the selected state.
- **Labels**: Positioned above the input in `body-sm` bold.

### Data Displays
- **Metric Cards**: Simple white cards with a 1px border. The label is in `label-caps` and the value in `data-mono` at a larger scale.
- **Data Tables**: No vertical borders. Horizontal borders only (`#E5E7EB`). Header row uses a light gray background (`#F9FAFB`).

### Property Panels
- Use collapsible sections with 12px internal padding. Section headers should be slightly tinted (`#F9FAFB`) to provide clear visual anchoring when scrolling through long lists of parameters.

### Visualization Callouts
- Tooltips used in 3D or graph views should be dark (`#1E293B`) with white text to stand out against the light UI, utilizing the `data-mono` font for precision coordinates.