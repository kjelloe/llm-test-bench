# css_alpha_linear

A HUD panel styled `background: rgba(0, 0, 0, 0.5)` over the 3D view is ported to a Unity project in Linear colour space as a UI Image coloured black with alpha 0.5. Side by side, the Unity panel is clearly lighter than the browser's. Why, and what is the fix?

A. Unity UI uses premultiplied alpha, so black at 0.5 is counted at half strength twice; divide the colour by its alpha before you assign it.
B. Browsers blend in sRGB, this project in linear, so the same alpha darkens less; raise it to about 1-(1-a)^1.8 (0.71) and check a pixel.
C. Screen Space Overlay canvases are drawn before post-processing, which lifts all the dark values on screen; move the canvas to Screen Space Camera instead.
D. Unity converts vertex alpha with the sRGB curve, so 0.5 ends up near 0.21; pass the alpha through Mathf.GammaToLinearSpace in reverse.
E. The default UI material samples a white sprite with bilinear filtering, which lightens solid fills; set that sprite's filter mode to Point.
