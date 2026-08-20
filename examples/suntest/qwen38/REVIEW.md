# REVIEW — "Open Ocean" (qwen3.8:27b, single-prompt output)

Independent assessment of `index.html` / `SPEC.md`, from a fresh read plus a live
headless-browser check (reused the project's own Playwright + SwiftShader
verification method from `SPEC.md §11`) to confirm claims empirically rather than
from code-reading alone. Evidence screenshots referenced below are in
`preview/review-evidence/`.

---

## Pros

- Clean, well-organized single file — sensible section comments, ES-module import
  map, no build step, matches what the README promises structurally.
- `SPEC.md` is unusually rigorous for a one-prompt output: it documents *why*, not
  just *what* — e.g. the exposure-vs-elevation curve (§8.2) is backed by an actual
  measured headless-render finding (B−R zenith delta at two exposure values), and
  it calls out non-obvious three.js r160 API gotchas (mirror-based `Water`, `fog`
  captured at construction time, jsDelivr missing `examples/textures/`) that would
  genuinely cost real debugging time to rediscover.
- Deterministic seeded PRNG (`mulberry32`) for the procedural terrain —
  reproducible rocks, not "regenerate and hope."
- Real resilience thinking: a procedural, tileable water-normal-map fallback if
  the CDN texture 404s, and an inlined SVG favicon specifically to keep the
  console error-free (their own verification method checks for zero console
  errors, so this isn't decorative — it's there because it was tested for).
- It documented its own verification method (headless Playwright + pixel
  sampling + a differential render against the official three.js example) — I was
  able to reuse the exact same approach to sanity-check it myself, which is the
  mark of a genuinely review-able spec.

## Cons / issues found

1. **The core showcased feature — the sand→rock→grass terrain — is essentially
   invisible in every shipped preview, and this is not just a bad camera angle.**
   All three `preview/*.png` use sun azimuths (160°/205°) that backlight the
   island relative to the fixed camera, so it reads as a flat silhouette. I
   re-ran it live with the sun swung to a strongly front-lit angle (elevation
   45–60°, azimuth 0–15°) — the island is *still* nearly flat blue-teal
   (`preview/review-evidence/frontlit-45-15.png`). Even orbiting the camera to
   look straight at the lit face up close
   (`preview/review-evidence/closeup-frontlit.png`) shows only a faint tan sand
   band; the "grass" green (`0x4f6b3a`, meant to dominate the upper 50% of the
   main island per `grassAmount=1`) barely registers at all. Direct sunlight
   doesn't visibly differentiate the lit vs. unlit face the way you'd expect from
   a `DirectionalLight` at intensity 1.5–3.5. This points to the sky-environment
   IBL (or the fog/exposure combo) dominating the material far more than
   intended — the single most work-intensive visual feature in the spec
   (procedural vertex-colored terrain) doesn't actually read as intended under
   any tested condition.
2. **The verification method can't catch #1.** `SPEC.md §11`'s island check is
   "a distinct darker patch above the horizon" — that passes whether the terrain
   shading is correct, washed-out, or flat-broken. It validates *presence*, not
   *correctness*, of the one feature most worth checking.
3. **"Self-contained" is oversold.** README calls this a self-contained single
   file, but `index.html` hard-depends on two live third-party fetches (jsDelivr
   for all of three.js core+addons, GitHub raw for the water texture) with no
   offline path for the framework itself — only the texture has a fallback. If
   jsDelivr is unreachable, it's a black screen, full stop. Odd inconsistency
   given the project clearly *knows* CDN reliability is an issue (that's why the
   texture fallback exists).
4. **`dirLight.target` is never positioned** (`index.html:207-208`) — it's added
   to the scene but left at the default `(0,0,0)`, while the island sits at
   `(0,-4,-170)`. The light aims at the world origin, not the island, ~19° off.
   Shadow-camera framing happens to be generous enough to cover it anyway, but
   it's a real inaccuracy vs. "aim the sun at what it's supposed to light."
5. **Dead/inconsistent code**: `renderer.toneMappingExposure = 0.55` (line 147)
   is set once, then unconditionally overwritten by `onSunChange()` on the very
   next lines (line 372) before any frame renders — it can never take effect,
   and its value (0.55) doesn't even match the documented curve max of 0.5 in
   `SPEC.md §8.2`. Harmless, but it's a paper-cut a reviewer should catch.
6. **No WebGL-unavailable / context-lost handling** — for something meant to be
   shared as a demo, the failure mode is a silent black screen with a console
   error, no message to the user.
7. Minor: no perf scaling for weaker GPUs (fixed 512×512 mirror reflection pass
   + shadows always on, doubling per-frame render cost), despite a mobile media
   query existing elsewhere; sliders have no `aria-live` region for their value
   labels.

## What I would have done differently

- Picked (or generated) at least one default/reference view that actually
  front-lights the island, so the terrain work is visible in the shipped
  evidence — right now 0 of 3 preview images demonstrate it, and this only
  surfaced by rendering it live and checking.
- Made the verification check for the *feature*, not just its silhouette: sample
  hue bands on the lit face (expect tan near the base, green near the top) and
  check for a shadow-darkened streak on the water near the island's base,
  instead of only checking "is there a dark patch."
- Vendored three.js locally (still zero build step — one more static `.js`
  file) so the "self-contained" claim actually holds, keeping only the texture
  on a CDN-with-fallback as it already is.
- Pointed `dirLight.target` at the island's position rather than leaving it at
  the origin.
- Deleted the dead `toneMappingExposure = 0.55` initializer (or made it match
  the documented 0.5 baseline).
- Added a plain "WebGL unavailable" fallback message.

## Bottom line

Genuinely impressive single-prompt output on engineering craft and
documentation discipline — the exposure-curve debugging story in `SPEC.md` is
legitimately good empirical work. But the one thing it was supposed to prove
out — procedural PBR terrain lit by a dynamic sun — doesn't actually read
correctly when you go looking for it, and the built-in verification wasn't
strict enough to catch that gap.

---

*Method: read `SPEC.md`, `README.md`, `index.html` in full; viewed the three
shipped `preview/*.png`; served the app locally and drove it with Playwright +
Chromium (SwiftShader software rendering, matching `SPEC.md §11`'s own method)
at azimuths not covered by the shipped presets to check the terrain-lighting
claim empirically. No console/page errors observed in any run.*
