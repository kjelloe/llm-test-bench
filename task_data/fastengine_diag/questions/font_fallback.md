# font_fallback

A browser reference screenshot (headless Chromium on a Linux build box) shows the HUD's `font-family: "Courier New", monospace` text heavier and wider than the fastengine client, which maps Courier New to Liberation Mono. The client's font metrics were already checked against the TTF tables. Why do they differ?

A. Chromium scales CSS sizes by the font's unitsPerEm while the client scales by the raster size, so the client's text is about 7% too small.
B. Headless Chromium synthesises bold for monospace fonts at small sizes; launch it with --disable-font-subpixel-positioning to match.
C. The build box runs Chromium at a device scale factor of 1.25, enlarging all text; pass --force-device-scale-factor=1 to the shot.
D. Chromium applies full hinting while raylib draws unhinted glyphs, which thickens the strokes; switch the client to FreeType's hinting.
E. The build box lacks Liberation, so Chromium fell back to DejaVu Sans Mono; the difference is the reference shot's font, not the client's.
