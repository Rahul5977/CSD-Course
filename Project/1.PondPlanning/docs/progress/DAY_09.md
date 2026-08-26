# DAY_09 — 2026-08-27
**Phase:** P8 · **Gate:** G8

## What worked
- `make report` → `docs/report/REPORT.pdf` (13 pages; python-markdown + headless Chrome; figures appendix inlined).
- Design brief (`docs/design/BRIEF.md`) and a design-system bundle in `web/design/`: tokens, a component stylesheet, seven `@dsCard` cards (colour, type, buttons, quantity, badges, progress, panel), and three prototypes — landing page, workspace, the six-state sheet — screenshotted headlessly as `p8-proto-*.jpg`.
- The React app rebuilt on the tokens: shared primitives (`ui.tsx`: Panel, Qty, Badge, Progress, Callout, Empty, Skeleton, Facts), every panel rewritten with its six states, a top bar with the village selector and status badges, a landing page at `/` with live village count, a two-route entry (`/`, `/app`), the service worker caching both.
- Lighthouse (desktop, after fixing contrast, heading order, robots.txt, favicon and the empty-tile 404s): landing **100 / 100 / 100**, workspace **100 / 96 / 100** (accessibility / best practices / SEO). Reports in `docs/figures/p8-lighthouse-*.html`.
- Verified end to end in the browser: site click → catchment (38.3 ha, ±26 %) → design (50 000 m³, 126 × 126 m, confidence low) with every state visible; nginx serves `/app` from the rebuilt image.

## What broke
- A class collision: the design system's `.site` (site row) matched `<footer class="site">` and turned the landing footer into a three-column row grid. Measured in the browser with `getComputedStyle` after two blind CSS guesses failed; renamed to `.foot`. Lesson: check the DOM, not the stylesheet.
- The Vite dev proxy did not forward WebSocket upgrades, so `waitForJob` hung on the socket instead of falling back to polling — invisible in Docker (nginx upgrades fine). `ws: true` added.
- The `Qty` band printed the API's full `method` sentence; moved to the tooltip.

## Screenshot
`docs/figures/p8-landing.jpg`, `p8-app-workspace.jpg`, `p8-app-design.jpg`, `p8-phone-390.jpg`, `p8-proto-*.jpg`

## Decisions made
- Two routes without a router library: `/` and `/app` resolved in `main.tsx`; nginx `try_files` already serves both. A router is one more dependency to defend for two static paths.
- The design system is mirrored, not imported: `web/design/{tokens,components}.css` are copied verbatim to `web/src/{tokens,ui}.css`. the AI design tool gets a self-contained bundle; the app has no build-time coupling to it.
- the AI design tool push is the user's step (`/design-sync` is reserved for explicit invocation); the bundle is ready in `web/design/`.

## Tomorrow's three tasks
1. Run `/design-sync` to push `web/design/` to a the AI design tool project and iterate on the prototypes there if wanted.
2. Rehearse `docs/DEMO.md` from the landing page.
3. `make tunnel` on demo day.
