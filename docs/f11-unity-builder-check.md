# F11 check for the Unity builder (2026-10-16)

We built a task from your incident F11 ("translucent CSS `rgba()` panels and chips look lighter in a Linear Unity
project"): `cs_css_alpha_linear` in llm-test-bench. Only 1 of 9 models passes it, so before we treat it as a fair test we
would like you to confirm it matches what you saw. A self-contained copy: `python3 bench.py --export-task cs_css_alpha_linear
--export-dir <dir>` (the reference solution is left out).

**What the task asserts**

1. The browser blends CSS `rgba()` in sRGB-encoded values: `out = a*css + (1-a)*backdrop` per channel, 0-255. The tests
   compare with pixels read back from a Chromium screenshot (160 panel/backdrop pairs), within one level per channel.
2. A Unity project in Linear colour space, with ordinary alpha blending (SrcAlpha, OneMinusSrcAlpha) onto an sRGB target,
   blends in linear light: decode both colours with the exact sRGB curve, blend, encode back.
3. The alpha to give the Unity material instead of the CSS alpha is the one that gives the browser result's luminance
   (Rec. 709 weights in linear light), clamped to [0, 1]. It is exact for gray on gray; for colour a single alpha cannot
   match every channel, so the test checks luminance within 3 levels.

**Our predictions, to compare with your measured pixels** (rule of thumb = your note: `1-(1-a)^1.8` for dark overlays,
`a^2.2` for bright over dark):

| CSS panel | over | browser draws | Unity Linear, same alpha | alpha to use (ours) | your rule of thumb |
|---|---|---|---|---|---|
| rgba(10,20,40,0.65) | rgb(70,110,160) | rgb(31,52,82) | rgb(42,69,103) | 0.818 → rgb(31,52,81) | 0.849 → rgb(28,48,75) |
| rgba(10,20,40,0.65) | rgb(200,210,220) | rgb(77,87,103) | rgb(125,132,140) | 0.864 → rgb(81,86,96) | 0.849 → rgb(85,90,100) |
| rgba(0,0,0,0.5) | rgb(128,128,128) | rgb(64,64,64) | rgb(92,92,92) | 0.762 → rgb(64,64,64) | 0.713 → rgb(70,70,70) |
| rgba(0,0,0,0.35) | rgb(34,120,60) | rgb(22,78,39) | rgb(26,98,48) | 0.591 → rgb(19,78,37) | 0.539 → rgb(21,83,40) |
| rgba(255,255,255,0.12) | rgb(20,30,50) | rgb(48,57,75) | rgb(100,101,107) | 0.028 → rgb(52,57,69) | 0.009 → rgb(34,41,57) |
| rgba(255,255,255,0.2) | rgb(70,110,160) | rgb(107,139,179) | rgb(137,154,184) | 0.116 → rgb(115,138,175) | 0.029 → rgb(84,118,164) |
| rgba(255,80,0,0.5) | rgb(20,30,50) | rgb(138,55,25) | rgb(188,61,34) | 0.267 → rgb(142,49,42) | 0.218 → rgb(130,46,44) |

**Questions**

1. Is point 2 how your HUD is drawn: a Linear project, UI/sprite materials with standard alpha blending onto an sRGB
   framebuffer (not a gamma-space UI canvas, not "UI blending in gamma" or a custom blend)?
2. Do your measured pixels agree with the "Unity Linear, same alpha" column, i.e. the panels were lighter by about that
   much?
3. Did the corrected alpha you shipped land closer to our "alpha to use" or to the rule of thumb? Over bright backdrops
   with white chips the two differ most (0.028 vs 0.009, 0.116 vs 0.029).
4. If you have a few measured (CSS colour, alpha, backdrop, Unity pixel) samples, could you send them? We would add them
   as a second fixture set next to Chromium's.
