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
- Decorative font: **Sniglet** (regular weight), used only for the wordmark
- Body font: **Nunito**

### 2.1 Hero section (fullscreen)

- Fills the entire viewport (100vh), background is the **primary accent
  color** (`#ef4363`).
- All text is **white-ish, using the page background color** (`#f8fbef`).
  Body copy and the CTA are set in a soft, readable font (**Nunito**);
  the decorative font (Sniglet) is reserved for the **mRodzina
  wordmark** only (the "Rodzina" part), since it is hard to read at length.
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

### 2.0 Header

- Logo only at the top-left (draw-in animation), three nav items on the right
  (Film · Jak to działa · Zacznij; Nunito, white). Absolutely positioned over the hero.
- The browser tab favicon is the "m" logo on the brand background
  (`public/favicon.svg`, from `brand/logo-rodzina.svg`).

### 2.2 Sections below the hero

Audience: parents. Spec: `docs/superpowers/specs/2026-11-21-landing-content-design.md`.

1. **Video**: 16:9 placeholder for a YouTube embed (to be filled later).
2. **"Pomożemy ci z:"**: auto-scrolling carousel (pauses on hover) of real
   topics from the benefit catalog (ZUS, 800+, becikowe, Aktywny rodzic, ...).
3. **"Jak to działa?"** (`#jak-to-dziala`): 4 alternating steps, each with a
   desktop screenshot in a CSS browser frame.
4. **"A do tego…"**: chat, SMS/e-mail notifications, shared family account,
   local benefits; then the "mRodzina także w telefonie" band with a phone shot.
5. **Timeline**: figure pinned to the viewport; vertical scroll moves it
   horizontally, from pregnancy to adulthood (18), with real examples.
6. **Final CTA**: "Sprawdź, co możemy dla ciebie zrobić." in a rounded box
   with margin, linking to the same URL as the hero CTA.

Screenshots live in `public/screens/` and are regenerated from the running
app with `npm run screenshots` (see `scripts/screenshots.mjs`).

### 2.3 Background ribbons

- Three thin, opaque ribbons (same shape language as the logo) come out of the
  hero, in the hero's own colour so they are invisible on it, and wander down
  the page (sometimes past the screen edges, with rare loops).
- They are drawn progressively with scroll. Once the hero is fully out of view
  they lighten to a pale pink. All share one colour so crossings merge
  (no alpha overlap).

### Language

- Polish only for now.

### Open questions

- Frontend app URL for the CTA (dev/prod).
