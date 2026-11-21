# Landing: real content and app screenshots (short design)

Date: 2026-11-21 · Size: small change · Scope: `landing/` only

## Intent
The landing page is for **parents**. In about 30 seconds a parent should understand what they get from mRodzina (money they won't miss, deadlines they won't forget, forms they don't fill in by hand) and click the CTA into the app. Today the page has placeholders: generic carousel one-liners, "Funkcja 1/2/3" cards, and timeline stubs.

## Goals / non-goals / anti-goals
- **Goals:** replace the placeholders with concrete copy grounded in the real benefit catalog (`backend/app/data/benefits_national.json`), and show the real app through screenshots.
- **Non-goals:** the video (filled in later; the placeholder stays), changes to the app, new animations, an official/urzędnik section.
- **Anti-goals:** technical jargon (engine, AI, matching), invented amounts or promises the app doesn't keep, anything that touches the `/jaskolka` link or its calm tone.

## Approaches (Claude's call; the user delegated it)
- A. Zig-zag feature rows (screenshot + text, 5–6 rows): clear, but long and generic.
- **B. "Jak to działa" in 4 steps with screenshots, plus an "A do tego…" strip. Picked:** it tells the parent what they'll do and get, and it's short. (User revision: desktop screenshots instead of phone frames, and one mention of the mobile app.)
- C. Pinned scroll-driven phone with changing screens: the most effort, and a second pinned section next to the timeline would feel heavy.

## Design
**Section order:** Hero (unchanged) → Video (placeholder, unchanged) → „Pomożemy ci z:” carousel → **Jak to działa** (replaces „Funkcje”) → **A do tego…** → Timeline → Final CTA (unchanged).

**Jak to działa: 4 steps.** Each step has a number, a heading, 1–2 sentences, and a **desktop screenshot** in a light CSS browser-window frame (rounded corners, three dots, shadow). On desktop the steps alternate sides; on mobile they stack.
1. *Zaloguj się przez mObywatel*: we already know your family, so you don't retype data. (screenshot: login / onboarding)
2. *Zobacz, co ci przysługuje i dlaczego*: matched benefits, with the reason for each match. (screenshot: dashboard / świadczenia)
3. *Wniosek wypełnia się sam*: you fill in the gaps and sign. (screenshot: application wizard)
4. *Pilnujemy terminów*: the calendar, from pregnancy to age 18. (screenshot: kalendarz)

**A do tego…:** four smaller cards, each with a cropped desktop screenshot (or an icon where there's no screen to show): the „Zapytaj mRodzinę” chat (answers with links to the regulations), **SMS and e-mail notifications** („nic ważnego ci nie umknie”: deadlines, application status, new benefits), the shared family account for both parents, and local benefits from your gmina/województwo.

**Mobile app:** one band, „mRodzina także w telefonie”, with a single phone-framed screenshot of the app at 390 px next to a short line saying you have everything in your pocket too.

Note: SMS/e-mail notifications and the mobile app are marked as product vision [W] in the main spec. On the landing they're presented as features at the user's request.

**Carousel:** about 8 real topics: Urlopy i zasiłki z ZUS · 800+ · Becikowe · Aktywny rodzic · Dobry Start i wyprawka szkolna · Karta Dużej Rodziny · Ulga prorodzinna w PIT · Świadczenia z twojej gminy.

**Timeline:** the same 8 stages, with real examples per stage: ciąża (L4 z kodem B, badania prenatalne); narodziny (akt urodzenia, becikowe, zasiłek macierzyński, 800+ within 3 months with back pay); urlop ojcowski/rodzicielski; 1–3 lata (Aktywny rodzic); przedszkole; szkoła (Dobry Start every year); trzecie dziecko → KDR; 18 lat. Amounts appear only where the catalog has them and they are not marked `verify: true`.

**Nav:** „Film · Jak to działa · Zacznij” (anchors to the sections above).

**Screenshots:** captured with Playwright (headless Chromium) from the locally running app, logged in as the demo persona: desktop at 1440×900 @2x, plus one mobile shot at 390×844 @2x. They're saved as optimized images in `landing/public/screens/`. A small script, `landing/scripts/screenshots.mjs`, can regenerate them when the UI changes. The browser and phone frames are pure CSS, not baked into the images.

## Left to the builder
Exact copy wording (Polish, informal "ty" form, matching the hero), image format and size, which persona state looks best in each screenshot, and lazy-loading.

## Done when
`npm run build` and lint pass in `landing/`, and the page has been checked visually at 390 px and desktop widths.
