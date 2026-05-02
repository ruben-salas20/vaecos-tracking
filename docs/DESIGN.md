---
name: Logistics Intelligence Design System
colors:
  surface: '#f9f9fe'
  surface-dim: '#d9dade'
  surface-bright: '#f9f9fe'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f8'
  surface-container: '#ededf2'
  surface-container-high: '#e8e8ed'
  surface-container-highest: '#e2e2e7'
  on-surface: '#1a1c1f'
  on-surface-variant: '#5d3f3b'
  inverse-surface: '#2e3034'
  inverse-on-surface: '#f0f0f5'
  outline: '#926f6a'
  outline-variant: '#e7bdb7'
  surface-tint: '#c0000a'
  primary: '#bc000a'
  on-primary: '#ffffff'
  primary-container: '#e2241f'
  on-primary-container: '#fffbff'
  inverse-primary: '#ffb4aa'
  secondary: '#5f5e60'
  on-secondary: '#ffffff'
  secondary-container: '#e2dfe1'
  on-secondary-container: '#636264'
  tertiary: '#5b5c60'
  on-tertiary: '#ffffff'
  tertiary-container: '#747479'
  on-tertiary-container: '#fefcff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdad5'
  primary-fixed-dim: '#ffb4aa'
  on-primary-fixed: '#410001'
  on-primary-fixed-variant: '#930005'
  secondary-fixed: '#e4e2e4'
  secondary-fixed-dim: '#c8c6c8'
  on-secondary-fixed: '#1b1b1d'
  on-secondary-fixed-variant: '#474649'
  tertiary-fixed: '#e3e2e7'
  tertiary-fixed-dim: '#c6c6cb'
  on-tertiary-fixed: '#1a1b1f'
  on-tertiary-fixed-variant: '#46464b'
  background: '#f9f9fe'
  on-background: '#1a1c1f'
  surface-variant: '#e2e2e7'
typography:
  display:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.5'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.01em
  code:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1.4'
    letterSpacing: 0.05em
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
  xl: 40px
  gutter: 16px
  margin: 24px
---

## Brand & Style

This design system is engineered for the high-stakes world of global logistics and data intelligence. The brand personality is **authoritative, precise, and urgent**. It evokes the feeling of a mission-control center where data is converted into actionable movement. 

The aesthetic follows a **Corporate / Modern** style with a focus on **Data-Centric Minimalism**. By utilizing high-contrast transitions between deep charcoal surfaces and vibrant action reds, the interface directs focus toward critical pathing and system statuses. The goal is to provide a "glass cockpit" experience: dense with information but structured for immediate cognitive processing.

## Colors

The color palette is anchored by **Vibrant Red**, used exclusively for primary actions, critical alerts, and directional indicators. This is balanced against a sophisticated range of **Grayscale Neutrals** that define the structural hierarchy.

- **Primary Action:** The red is reserved for the "critical path"—buttons that confirm shipments, initiate tracking, or highlight errors.
- **Surface & Navigation:** Deep blacks (#000000) and Charcoal Grays (#1C1C1E) are used for sidebars and top navigation to provide a robust frame for content.
- **Semantic Logic:** Success (Green) represents completed deliveries or "in-tolerance" metrics; Warning (Amber) signifies delays or pending approvals; Error (Red) is used for system failures or blocked logistics chains.

## Typography

This design system utilizes **Inter** for all applications. Inter’s tall x-height and neutral character make it ideal for data-heavy tables and complex dashboards.

- **Headlines:** Use Bold (700) and SemiBold (600) weights with tighter letter spacing to mirror the heavy, impactful feel of the logo's logotype.
- **Numerical Data:** For tracking numbers, timestamps, and coordinates, use the **label-md** or **code** styles to ensure maximum legibility at small sizes.
- **Hierarchy:** High contrast in weight (Bold vs. Regular) is preferred over excessive variation in font size to maintain a compact, high-density layout.

## Layout & Spacing

The layout philosophy is built on a **12-column Fluid Grid** designed for professional monitors. A strict **4px baseline grid** ensures vertical rhythm across dense data tables and side-panels.

- **Density:** The system defaults to a "Comfortable" density for general management, but allows for a "Compact" toggle in data-heavy views (e.g., global shipping manifests).
- **Alignment:** All elements should align to the 4px increments. Internal padding for cards and containers should be a minimum of 16px (md) to prevent visual clutter.

## Elevation & Depth

To maintain a "high-tech" and precise feel, the design system avoids heavy, soft shadows. Instead, it utilizes **Tonal Layering** and **Low-Contrast Outlines**.

- **Surface Tiers:** Backgrounds use the lightest neutral, while interactive cards and panels use pure white or slightly darker grays to create separation.
- **Borders:** Containers are defined by 1px solid strokes (#E5E5EA). 
- **Active Elevation:** Only the most critical floating elements (modals, dropdowns) use a tight, high-precision shadow with 10% opacity to suggest they are sitting directly above the workspace.

## Shapes

The shape language is **Soft** (Level 1). This choice balances the industrial "hard" nature of logistics with the modern "soft" nature of intelligent software.

- **Standard Radius:** 4px (0.25rem) is the default for buttons, input fields, and small cards.
- **Container Radius:** Larger panels or modals may use up to 8px (0.5rem) to soften the overall interface.
- **The "Arrow" Motif:** Drawing from the logo, iconography and certain UI indicators (like status pips or chevron buttons) should utilize sharp angles to reinforce the concept of direction and movement.

## Components

### Buttons
- **Primary:** Solid Red (#FF3B30) with white text. High-impact, used for the main intent.
- **Secondary:** Charcoal Gray (#1C1C1E) with white text. Used for persistent navigation actions.
- **Tertiary/Ghost:** 1px gray border or no border. Used for secondary management tasks.

### Status Chips
Status chips are critical for logistics. They use a "Lightened Semantic" background with "Dark Semantic" text (e.g., a pale green background with dark green text for "Delivered").

### Input Fields
Fields feature a 1px border and 4px corner radius. When focused, the border changes to the Primary Red with a subtle 2px outer glow. Labels are always positioned above the field in the **label-md** typography style.

### Logistics Cards
Cards are the primary container for shipment data. They must include a clear header, a status chip in the top right, and a "Progress Bar" component when applicable to show transit completion.

### Data Tables
Tables are the heart of the "Intelligence" aspect. They should feature "Zebra Striping" using the lightest neutral gray and provide "Sort" and "Filter" icons that appear on hover for each column header.