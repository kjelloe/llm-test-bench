# lambert_shader

The browser game uses `MeshLambertMaterial` everywhere. In URP, the Lit shader (even at Smoothness 0, Metallic 0) multiplies diffuse by 0.96 and adds a specular environment term, so colours do not match. Which shader matches Lambert?

A. URP Lit at Smoothness 0 with Environment Reflections and Specular Highlights turned off on the material.
B. URP Unlit, with the lighting baked into the colour by script at startup.
C. URP Simple Lit with specular highlights off: Lambert diffuse plus emission, nothing else.
D. URP Baked Lit, with the scene's lights baked into lightmaps for each level, which removes the extra terms.
E. URP Complex Lit with clear coat disabled and the specular workflow selected.
