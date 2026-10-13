# height_queries

The fastengine HUD must follow the browser HUD's CSS. The CSS has `max-height` media queries at 520, 620 and 460 px, plus `(pointer: coarse)` and `(orientation: portrait)` rules written for phones. The native client is a resizable desktop window, and screenshots are compared with the browser at a fixed shot viewport. What should the port do?

A. Port the height queries and re-check them on every resize, drop the touch and portrait rules, and compare at the shot viewport.
B. Port every rule, including pointer and orientation, so the client follows the CSS exactly at whatever size the player picks.
C. Evaluate the queries once at start-up from the monitor's resolution, since the size of the window itself does not change which of the rules apply.
D. Skip the queries and lay out for the shot viewport only; the window is letterboxed, so the breakpoints are never reached.
E. Scale each pixel breakpoint by the monitor's DPI first, since on a desktop one CSS pixel is one physical pixel of the screen.
