# emission_keyword

An editor script generates URP Lit materials for team-coloured parts. It sets `_EmissionColor` to black and enables the `_EMISSION` keyword, planning to set the real emission colour per team at runtime. At runtime no emission shows, and the saved material no longer has the `_EMISSION` keyword. Why, and what is the fix?

A. URP strips shader keywords at build time unless the shader is listed in Always Included Shaders; add URP Lit to that list in Project Settings > Graphics before building.
B. Keywords set on `sharedMaterial` are never written to the asset; set the keyword through `renderer.material` in the script.
C. `_EMISSION` only takes effect when the material's global illumination flag is Baked; set globalIlluminationFlags to Baked.
D. URP's material validation turns `_EMISSION` off when the emission colour is black; save the material with a non-black (e.g. white) emission.
E. The SRP Batcher ignores emission set on the material itself; set `_EmissionColor` per renderer through a MaterialPropertyBlock instead of the material.
