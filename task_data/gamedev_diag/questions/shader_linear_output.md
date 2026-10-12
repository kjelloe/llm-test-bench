# shader_linear_output

A three.js r162 `ShaderMaterial` draws grid lines with `gl_FragColor = vec4(uColor, 1.0)`, where `uColor` is a `THREE.Color` set from the hex `0x3a6ea5`; the renderer's output colour space is sRGB and the shader includes no colour-space chunk. In the browser the lines look clearly darker than that hex. The Unity port (Linear project) draws them with an Unlit material in the same hex and they look brighter than the browser. Why is the browser darker, and how do you match it in Unity?

A. three.js applies ACES Filmic tone mapping to every material by default; add ACES tone mapping to the Unity camera's post-processing stack.
B. WebGL premultiplies the canvas alpha, darkening every fragment; switch the Unity material to a premultiplied blend mode as well.
C. The browser antialiases the thin lines with MSAA against the dark ground; multiply the Unity colour by the line's average pixel coverage.
D. ShaderMaterial uniforms are stored at half precision on the GPU, so the colour is truncated; quantise each channel of the Unity colour to 10 bits.
E. The colour is stored linear and the shader writes it out unconverted; in Unity use the hex's linear value as the material colour.
