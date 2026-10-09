# css_border_tint

A Unity uGUI port draws each panel's 2 px CSS border as a slightly larger Image in the border colour placed behind the face Image. The face is translucent (`rgba(0, 0, 0, 0.6)` in the CSS). In Unity the whole panel looks tinted with the border colour, unlike the browser. Why, and what fixes it?

A. uGUI blends in gamma space while CSS blends in linear; switch the Canvas to linear blending in the project settings.
B. The face Image is maskable, so it inherits the border's colour; turn Maskable off on the face Image.
C. The Canvas Scaler resamples the border into the face; switch it to Constant Pixel Size.
D. CSS draws borders outside the box; set Preserve Aspect on the border Image to match.
E. The border fill shows through the translucent face; draw the border as four edge strips instead.
