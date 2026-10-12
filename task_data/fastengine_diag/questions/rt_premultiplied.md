# rt_premultiplied

A HUD minimap is rendered into a render target cleared to transparent black, using normal alpha blending for everything drawn into it. The target's texture is then drawn onto the HUD, also with normal alpha blending (SRC_ALPHA, ONE_MINUS_SRC_ALPHA). Its soft edges get dark borders and dark halos that the browser does not show. Why, and what is the fix?

A. Bilinear filtering mixes the transparent black border texels into the soft edge pixels; switch the target's texture to point filtering instead.
B. The target is cleared to black, which shows through every partly transparent pixel; clear it to the HUD panel's own colour instead.
C. The target's colour attachment is stored in sRGB and decoded twice on the way to the screen; create it with a linear colour format.
D. Blending into the transparent target leaves premultiplied colour in its texels; draw the texture with ONE, ONE_MINUS_SRC_ALPHA instead.
E. The minimap is drawn upside down and the edge pixels sample the wrong row; flip the texture coordinates on Y when drawing the target.
