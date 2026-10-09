# gamma_project

Colours from a three.js r162 game (colour management on) look washed out or too dark in its Unity port. The Unity project's Color Space is set to Gamma. What is the right fix?

A. Untick sRGB on every texture import, because three.js samples all of its textures and vertex colours as linear data.
B. Use URP Unlit shaders everywhere, so Unity's lighting cannot shift the browser's colours.
C. Convert every colour with `Color.gamma` before assigning it, which matches three.js's output encoding.
D. Enable HDR on the camera and add ACES tonemapping, which three.js r162 applies to every frame by default.
E. Switch the project to Linear colour space, because three.js r162 lights and blends colours in linear space.
