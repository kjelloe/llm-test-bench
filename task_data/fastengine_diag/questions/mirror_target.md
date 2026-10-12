# mirror_target

A port renders a water reflection by drawing the scene from a mirrored camera into a render target with the same pipeline as the screen (ACES tone mapping and sRGB encoding applied), then samples that target in the water shader, whose own output is tone mapped and encoded again. The reflection looks washed out and too bright next to the browser. Why, and what is the fix?

A. The target's texture is sampled as linear although it holds sRGB values; give it an sRGB format so sampling decodes it before the water shader uses it.
B. The render target is 8-bit and clips the reflection's highlights; switch it to a half-float format so values above one survive until tone mapping.
C. The mirrored camera has no oblique near plane, so geometry under the water leaks into the reflection; clip the projection at the water plane.
D. Mipmaps are generated for the reflection target and blur it into a brighter haze; turn off mipmap generation and sample the target with point filtering.
E. three renders into targets linear and untoned; draw the mirror pass without tone mapping or encoding, so the reflection is encoded once at the end.
