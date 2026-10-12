# fill_culling

fastengine's canvas-2D port fills a path by triangulating it and drawing the triangles through raylib's rlgl batch, between the 3D scene and the rest of the HUD. Paths whose points run counter-clockwise on screen fill correctly; the same shapes drawn clockwise do not show at all. Why, and what is the fix?

A. rlgl's batch has back-face culling on, so one winding is culled; flush the batch, draw the fill with culling off, flush again, then turn culling back on.
B. The ear-clipping triangulation assumes counter-clockwise input and emits nothing for clockwise rings; detect the ring's orientation and handle both cases there.
C. The HUD's camera has Y pointing down, which mirrors every triangle on screen; render the HUD with a Y-up orthographic camera like the 3D scene uses.
D. The depth test is still on from the 3D pass and the clockwise fills land behind the scene; clear the depth buffer before the HUD layer is drawn.
E. The fill colour's alpha is premultiplied twice for clockwise paths, making them transparent; convert colours to straight alpha before drawing.
