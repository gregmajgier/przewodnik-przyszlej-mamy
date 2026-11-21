# Landing Page Vision

> Living document. Sections are added as the vision is described.

## 1. Logo animation

**Source asset:** `brand/logo-rodzina.svg`

The logo is a single continuous ribbon: one SVG `<path>` with a white stroke
(24px, round caps/joins) and no fill, on the brand background (`#EF4363`).
The path starts at the bottom-left (`M 100 397`) and ends at the bottom-right
(`412 397`), looping through the three "heads" in between.

### Behavior

- The ribbon **draws itself in**, entering from the **bottom-left corner**
  and tracing the path until the full logo is formed.
- Motion style: **pure drawing** (stroke reveal). No additional drift or
  translation of the whole shape.
- End state: the logo **stays static** in its final form. No looping, no
  follow-up motion.

### Scope

- This is a **reusable animation**, not a one-off intro. It plays **every time
  the logo appears** on the page, wherever that is.
- It should be built as a shared component so all logo placements get the same
  behavior.

### Implementation notes

- Technique: `stroke-dasharray` / `stroke-dashoffset` animated from the full
  path length to 0 (path start is already the bottom-left, so no path
  changes are needed).
- Path length should be measured at runtime (`getTotalLength()`) rather than
  hardcoded.
- Respect `prefers-reduced-motion`: render the final static logo with no
  animation.

### Open questions

- Duration and easing.
- Whether the animation replays on every re-render / scroll-in or only on
  first mount.
- Logo size and colors per placement (e.g. white on pink vs. pink on white).

## 2. Page layout

Brand tokens (from `brand/colors_and_fonts.md`):

- Background color: `#f8fbef`
- Main font color: `#191919`
- Primary accent color: `#ef4363`
- Decorative font: **Momo Signature**

### 2.1 Hero section (fullscreen)

- Fills the entire viewport (100vh), background is the **primary accent
  color** (`#ef4363`).
- All text is **white-ish, using the page background color** (`#f8fbef`),
  set in the **decorative font** (Momo Signature).
- Copy, centered, top to bottom:
  1. "Mamo! Tato! Masz wiele na głowie..."
  2. "Pozwól, że" followed by the **mRodzina wordmark**, then "pomoże."
- **mRodzina wordmark:** our logo (the ribbon, which acts as the "m")
  followed directly by the text "Rodzina", so together they read as the
  brand name **mRodzina**. "Rodzina" is the same size as the surrounding
  copy; the logo is slightly smaller, sized like a lowercase "m" next to
  the text. The logo plays the draw-in animation from
  section 1 when it appears.
- Below the copy: a CTA button.
  - Background: `#f8fbef` (white-ish), rounded corners (border radius).
  - Text color: primary accent (`#ef4363`).
  - Label: "Zobacz, co możemy dla ciebie zrobić."
  - Links to our **frontend application** (`frontend/`).
- At the bottom of the viewport: a **bouncing arrow** hinting that the page
  can be scrolled down.

### 2.2 Project info section

- Below the hero, there will be information about the project.
- **Deferred.** Not defined yet; leave empty for now.

### Language

- Polish only for now.

### Open questions

- Frontend app URL for the CTA (dev/prod).
