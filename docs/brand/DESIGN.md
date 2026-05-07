---
name: Cognitive Modern
colors:
  surface: '#fbf9f5'
  surface-dim: '#dbdad6'
  surface-bright: '#fbf9f5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f3ef'
  surface-container: '#efeeea'
  surface-container-high: '#eae8e4'
  surface-container-highest: '#e4e2de'
  on-surface: '#1b1c1a'
  on-surface-variant: '#454654'
  inverse-surface: '#30312e'
  inverse-on-surface: '#f2f0ed'
  outline: '#767686'
  outline-variant: '#c6c5d7'
  surface-tint: '#414dd5'
  primary: '#0b19af'
  on-primary: '#ffffff'
  primary-container: '#2e3ac4'
  on-primary-container: '#b5baff'
  inverse-primary: '#bec2ff'
  secondary: '#904d00'
  on-secondary: '#ffffff'
  secondary-container: '#fe932c'
  on-secondary-container: '#663500'
  tertiary: '#6a1a00'
  on-tertiary: '#ffffff'
  tertiary-container: '#8e2c09'
  on-tertiary-container: '#ffaa91'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e0e0ff'
  primary-fixed-dim: '#bec2ff'
  on-primary-fixed: '#000569'
  on-primary-fixed-variant: '#2531bd'
  secondary-fixed: '#ffdcc3'
  secondary-fixed-dim: '#ffb77d'
  on-secondary-fixed: '#2f1500'
  on-secondary-fixed-variant: '#6e3900'
  tertiary-fixed: '#ffdbd1'
  tertiary-fixed-dim: '#ffb59f'
  on-tertiary-fixed: '#3a0a00'
  on-tertiary-fixed-variant: '#842503'
  background: '#fbf9f5'
  on-background: '#1b1c1a'
  surface-variant: '#e4e2de'
typography:
  display-lg:
    fontFamily: Newsreader
    fontSize: 48px
    fontWeight: '400'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Newsreader
    fontSize: 32px
    fontWeight: '400'
    lineHeight: '1.2'
  headline-sm:
    fontFamily: Newsreader
    fontSize: 24px
    fontWeight: '500'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Work Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Work Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Work Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1280px
  gutter: 32px
  margin: 64px
---

## Brand & Style

This design system embodies "Cognitive Modernism"—a philosophy that blends the intellectual rigor of traditional academia with the streamlined efficiency of modern research tools. The aesthetic is designed to reduce cognitive load, replacing over-saturated interfaces with a calm, editorial atmosphere that treats data as literature.

The style leans heavily into **Minimalism** with a **Tactile** twist. It utilizes expansive whitespace to allow complex information to breathe, while employing subtle tonal shifts rather than heavy borders or shadows. The goal is to evoke the feeling of a well-curated library or a premium physical journal: authoritative, quiet, and deeply focused.

## Colors

The palette is anchored by a creamy, non-white base (#FBF9F5) to reduce eye strain during long-form research sessions. 

- **Primary (Deep Indigo):** Used for primary text, critical actions, and branding. It provides high-contrast legibility without the harshness of pure black.
- **Accents (Amber & Terracotta):** These warm tones serve as functional "pop" colors. Amber (#D97706) is used for highlights and informational states, while Terracotta (#9A3412) identifies secondary actions or important discoveries.
- **Neutral Surface:** The background remains airy and light, with subtle shifts toward warmer greys for interface borders and disabled states.

## Typography

This design system utilizes a high-contrast typographic pairing to signal the transition between "reading" and "doing."

- **Serif (Newsreader):** Used for headlines and long-form narrative text. Its classic proportions lend an air of authority and intellectual depth.
- **Sans-Serif (Work Sans):** Used for functional UI elements, labels, and metadata. Its neutral, grounded nature ensures that dense research data remains legible and organized.
- **Hierarchy:** Maintain generous line heights (1.5x+) for body text to ensure maximum readability. Use all-caps with increased tracking for labels to create clear visual distinction from content.

## Layout & Spacing

The layout follows a **Fixed Grid** model for content-heavy pages to maintain a focused, book-like reading experience. 

- **Generous Whitespace:** Margins and gutters are intentionally oversized to prevent the UI from feeling "cramped."
- **Information Density:** Use an 8px base grid. While the interface is airy, data tables and research lists can utilize tighter vertical spacing (4px) provided they are encased in containers with ample external padding.
- **Alignment:** Headlines should be left-aligned to mirror the start of a paragraph, reinforcing the editorial feel.

## Elevation & Depth

This design system avoids heavy shadows and traditional material depth. Instead, it uses **Tonal Layers** and **Low-Contrast Outlines**.

- **Surface Tiers:** Use subtle variations of the creamy base (e.g., 2-3% darker) to distinguish sidebar areas from the main canvas.
- **Soft Shadows:** If elevation is required for modals or popovers, use a highly diffused "Ambient" shadow: `0px 10px 40px rgba(46, 58, 196, 0.04)`. Note the subtle Indigo tint in the shadow to maintain color harmony.
- **Borders:** Use thin (1px) borders in a light terracotta-grey for cards and separators rather than drop shadows.

## Shapes

The shape language is disciplined and "Soft" (4px - 8px radius). This avoids the clinical feel of sharp corners while steering clear of the overly playful nature of pill-shaped buttons.

- **Primary Elements:** Buttons and input fields use a consistent 4px radius.
- **Containers:** Large cards or content sections may use up to 12px (rounded-lg) to create a gentle framing effect.
- **Interactive States:** Hover states should be indicated by subtle background color shifts rather than dramatic shape changes.

## Components

- **Buttons:** Primary buttons use the Deep Indigo background with white text. Secondary buttons are outlined in a thin Indigo stroke or use the Terracotta accent for specific "discovery" actions.
- **Input Fields:** Use a subtle background fill (slightly darker than the page base) with a bottom-only border or a very light 4-sided stroke.
- **Chips/Tags:** Utilize the Amber accent with low opacity (10-15%) for the background and high-contrast text. This highlights metadata without competing with primary headings.
- **Cards:** Cards should be border-heavy rather than shadow-heavy. Use a 1px border and generous internal padding (min 32px).
- **Abstract Indicators:** Use small, geometric glyphs (dots, thin lines) in Terracotta to mark "new" or "unread" research insights, reinforcing the academic annotative style.
- **Citations/Footnotes:** A dedicated component for source-linking should use the Label-MD style, set in the Deep Indigo to signify interactivity.