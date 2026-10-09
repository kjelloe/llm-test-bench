# emission_hdr

A material's emission looks far too bright in the Unity port (Linear colour space), although its value comes from the same hex colour as the browser game: `mat.SetColor("_EmissionColor", HexToColor(0x931c1c))`. Why, and what is the fix?

A. `_EmissionColor` is an HDR property that Unity uses as linear; convert the sRGB hex value first with `HexToColor(...).linear`.
B. URP's default Volume adds bloom to every emissive surface; remove the Bloom override from the global Volume profile, or lower its intensity to zero.
C. URP multiplies emission by the main light's intensity, which is above 1 here; divide the colour by the light's intensity.
D. SetColor on an emission property expects 0-255 channel values, not 0-1; build the Color from the hex bytes with a Color32, which converts the range for you.
E. The material is double-sided, so URP adds its emission once per face; switch Render Face back to Front only.
