# quality_tier

A port picks Low, Medium or High graphics at start-up. A first version times 60 frames of a test scene before the window shows anything, and still picks High on a VM without a GPU, where llvmpipe renders. Players with slow machines also wait seconds at start-up. What is the better rule?

A. Time more frames, about 300, so the average is stable enough on fast machines; the wait only happens once per start-up anyway.
B. Read the GPU's VRAM size from the OS before the window opens and pick High above 4 GB, Medium above 2 GB, and Low for everything below.
C. Query GL_RENDERER before the window is created, so the tier is chosen in time to size the first frame's render targets correctly.
D. Always start on High and drop a tier whenever a frame takes longer than 33 ms; players then get the best quality their machine holds.
E. After the GL context exists, read glGetString(GL_RENDERER): llvmpipe or SwiftShader means Low; a command-line flag can override it.
